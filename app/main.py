from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Repository, Diagnostic, Build, Deployment, BuildFailure, BuildStep
from app.analytics.metrics_calculator import MetricsCalculator
from app.analytics.regression_detector import RegressionDetector
from app.diagnostics import DiagnosticEngine
from app.collector import DataCollector
from pydantic import BaseModel
from datetime import datetime
import json
import os

app = FastAPI(title="Release Intelligence Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DiagnosticResponse(BaseModel):
    id: int
    repository_id: Optional[int]
    diagnostic_type: str
    severity: str
    title: str
    message: str
    diagnostic_metadata: dict
    created_at: datetime


class BuildTrendResponse(BaseModel):
    date: str
    median_duration: float
    p90_duration: float
    count: int


@app.get("/")
def root():
    return {"message": "Release Intelligence Platform API"}


@app.get("/api/repositories", response_model=List[dict])
def get_repositories(db: Session = Depends(get_db)):
    """Get all repositories"""
    repos = db.query(Repository).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "workspace": r.workspace
        }
        for r in repos
    ]


@app.get("/api/repositories/{repo_id}/build-duration-trends", response_model=List[BuildTrendResponse])
def get_build_duration_trends(repo_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get build duration trends for a repository"""
    calculator = MetricsCalculator(db)
    trends = calculator.calculate_build_duration_trends(repo_id, days)
    return trends


@app.get("/api/repositories/{repo_id}/pr-velocity")
def get_pr_velocity(repo_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get PR velocity metrics"""
    calculator = MetricsCalculator(db)
    return calculator.calculate_pr_velocity(repo_id, days)


@app.get("/api/repositories/{repo_id}/deployment-frequency")
def get_deployment_frequency(repo_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get deployment frequency"""
    calculator = MetricsCalculator(db)
    return calculator.calculate_deployment_frequency(repo_id, days)


@app.get("/api/repositories/{repo_id}/deployment-frequency-by-env")
def get_deployment_frequency_by_env(repo_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get deployment frequency per environment"""
    calculator = MetricsCalculator(db)
    return calculator.calculate_deployment_frequency_by_environment(repo_id, days)


@app.get("/api/repositories/{repo_id}/build-minutes")
def get_build_minutes(repo_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get build minutes consumed"""
    calculator = MetricsCalculator(db)
    return calculator.calculate_build_minutes(repo_id, days)


@app.get("/api/repositories/{repo_id}/slow-pipelines")
def get_slow_pipelines(repo_id: Optional[int] = None, percentile: float = 90, db: Session = Depends(get_db)):
    """Get slow pipelines"""
    calculator = MetricsCalculator(db)
    return calculator.get_slow_pipelines(repo_id, percentile)


@app.get("/api/repositories/{repo_id}/dev-deploy-slowdown")
def get_dev_deploy_slowdown(repo_id: int, days: int = 14, db: Session = Depends(get_db)):
    """Dev deploy slowdown for trunk-based flow (branch=main heuristic)"""
    calculator = MetricsCalculator(db)
    return calculator.get_dev_deploy_slowdown(repo_id, days=days)


@app.get("/api/repositories/{repo_id}/recent-failures")
def get_recent_failures(repo_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get recent failed builds with error summaries"""
    failures = db.query(Build).filter(
        Build.repository_id == repo_id,
        Build.state == "FAILED",
        Build.completed_on.isnot(None)
    ).order_by(Build.completed_on.desc()).limit(limit).all()
    
    results = []
    for b in failures:
        # Try to find a failure record for a failed step
        step = next((s for s in b.steps if s.state == "FAILED"), None) if b.steps else None
        failure_record = None
        if step:
            failure_record = db.query(BuildFailure).filter(BuildFailure.step_id == step.id).first()
        
        results.append({
            "build_id": b.id,
            "commit_hash": b.commit_hash,
            "completed_at": b.completed_on.isoformat() if b.completed_on else None,
            "step": step.step_name if step else None,
            "error_message": failure_record.error_message[:300] if failure_record and failure_record.error_message else None
        })
    
    return results


@app.get("/api/repositories/{repo_id}/latest-images")
def get_latest_images(repo_id: int, db: Session = Depends(get_db)):
    """Get latest deployment per environment (image name best-effort; also returns build number if linked)"""
    deployments = db.query(Deployment).filter(
        Deployment.repository_id == repo_id
    ).order_by(Deployment.deployed_at.desc()).all()
    
    # Group by environment, get latest
    env_images = {}
    for dep in deployments:
        if dep.environment not in env_images:
            build_number = None
            if dep.build_id:
                b = db.query(Build).filter(Build.id == dep.build_id).first()
                build_number = b.build_number if b else None
            env_images[dep.environment] = {
                "docker_image": dep.docker_image,
                "deployed_at": dep.deployed_at.isoformat() if dep.deployed_at else None,
                "commit_hash": dep.commit_hash,
                "build_number": build_number
            }
    
    return env_images


@app.get("/api/repositories/{repo_id}/latest-build")
def get_latest_build(repo_id: int, db: Session = Depends(get_db)):
    """Latest pipeline execution with failure summary (if any)"""
    b = db.query(Build).filter(Build.repository_id == repo_id).order_by(Build.completed_on.desc().nullslast()).first()
    if not b:
        return None
    failed_step = next((s for s in b.steps if s.state == "FAILED"), None) if b.steps else None
    failure = None
    if failed_step:
        failure = db.query(BuildFailure).filter(BuildFailure.step_id == failed_step.id).first()
    return {
        "build_id": b.id,
        "build_number": b.build_number,
        "state": b.state,
        "duration_seconds": b.duration_seconds,
        "branch": b.branch,
        "commit_hash": b.commit_hash,
        "completed_at": b.completed_on.isoformat() if b.completed_on else None,
        "failed_step": failed_step.step_name if failed_step else None,
        "error_excerpt": (failure.error_message[:500] if (failure and failure.error_message) else (failed_step.log_excerpt[:500] if (failed_step and failed_step.log_excerpt) else None))
    }


@app.get("/api/diagnostics", response_model=List[DiagnosticResponse])
def get_diagnostics(repository_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get all diagnostics"""
    query = db.query(Diagnostic).filter(Diagnostic.acknowledged == False)
    
    if repository_id:
        query = query.filter(Diagnostic.repository_id == repository_id)
    
    diagnostics = query.order_by(Diagnostic.created_at.desc()).limit(50).all()
    
    return [
        DiagnosticResponse(
            id=d.id,
            repository_id=d.repository_id,
            diagnostic_type=d.diagnostic_type,
            severity=d.severity,
            title=d.title,
            message=d.message,
            diagnostic_metadata=d.diagnostic_metadata or {},
            created_at=d.created_at
        )
        for d in diagnostics
    ]


@app.get("/api/metrics/summary")
def get_metrics_summary(days: int = 30, db: Session = Depends(get_db)):
    """Get summary metrics across all repositories"""
    calculator = MetricsCalculator(db)
    
    repos = db.query(Repository).all()
    
    summary = {
        "total_repositories": len(repos),
        "pr_velocity": calculator.calculate_pr_velocity(days=days),
        "deployment_frequency": calculator.calculate_deployment_frequency(days=days),
        "build_minutes": calculator.calculate_build_minutes(days=days),
        "slow_pipelines": calculator.get_slow_pipelines(percentile=90)
    }
    
    return summary


@app.post("/api/collect")
def trigger_collection(db: Session = Depends(get_db)):
    """Trigger data collection"""
    try:
        collector = DataCollector(db)
        collector.collect_all()
        return {"status": "success", "message": "Data collection completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diagnostics/generate")
def generate_diagnostics(db: Session = Depends(get_db)):
    """Generate and save diagnostics"""
    try:
        engine = DiagnosticEngine(db)
        diagnostics = engine.generate_diagnostics()
        engine.save_diagnostics(diagnostics)
        return {"status": "success", "count": len(diagnostics)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repositories/{repo_id}/regressions")
def get_regressions(repo_id: int, db: Session = Depends(get_db)):
    """Get regression analysis for a repository"""
    detector = RegressionDetector(db)
    
    build_regression = detector.detect_build_duration_regression(repo_id)
    waste_findings = detector.detect_resource_waste(repo_id)
    
    return {
        "build_regression": build_regression,
        "resource_waste": waste_findings
    }


@app.get("/api/metrics/build-minutes-28")
def get_build_minutes_28(db: Session = Depends(get_db)):
    """Get build minutes aggregated from 28th to 28th for the latest closed window"""
    try:
        calculator = MetricsCalculator(db)
        data = calculator.calculate_build_minutes_28_to_28()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics/build-minutes-28-file")
def get_build_minutes_28_file():
    """Get build minutes per repo from build_stats.json file (mocked for demo)"""
    stats_path = os.path.join(os.path.dirname(__file__), '..', '..', 'build_stats.json')
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Parse the file
        repo_minutes = {}
        total_minutes = 0.0
        for entry in data[1:]:
            repo = entry["Repository"]
            # Parse "Build Minutes Used" like "6d 14h 23m 0s"
            parts = entry["Build Minutes Used"].split()
            mins = 0
            for part in parts:
                if part.endswith('d'):
                    mins += int(part[:-1]) * 24 * 60
                elif part.endswith('h'):
                    mins += int(part[:-1]) * 60
                elif part.endswith('m'):
                    mins += int(part[:-1])
                elif part.endswith('s'):
                    pass  # ignore seconds for minute-level chart
            repo_minutes[repo] = mins
            total_minutes += mins
        return {"by_repo": repo_minutes, "total_minutes": total_minutes}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/metrics/build-stats-file")
def get_build_stats_file():
    """Get build stats per repo from build_stats.json file (always returns mock if missing)"""
    stats_path = os.path.join(os.path.dirname(__file__), '..', '..', 'build_stats.json')
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        # Mock data if file missing
        data = [
            ["Repository", "Builds", "Build Duration", "Build Minutes Used"],
            {"Repository": "emr-dev/woundhub", "Builds": 31, "Build Duration": "0d 4h 50m 51s", "Build Minutes Used": "0d 7h 32m 59s"},
            {"Repository": "emr-dev/clinical-service", "Builds": 146, "Build Duration": "3d 1h 29m 48s", "Build Minutes Used": "6d 14h 23m 0s"}
        ]
    stats = {}
    for entry in data[1:]:
        repo = entry["Repository"]
        stats[repo] = {
            "builds": entry.get("Builds", 0),
            "build_duration": entry.get("Build Duration", "0d 0h 0m 0s"),
            "build_minutes_used": entry.get("Build Minutes Used", "0d 0h 0m 0s")
        }
    return stats


@app.get("/api/vulnerabilities/{repo_slug}")
def get_vulnerabilities(repo_slug: str):
    """Get vulnerabilities for a repo from trivy-report.json (mocked if missing)"""
    trivy_path = os.path.join(os.path.dirname(__file__), '..', '..', 'trivy-report.json')
    vulns = []
    cross_repo = []
    try:
        with open(trivy_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if "pnpm-lock.yaml" in line:
                for j in range(i+4, len(lines)):
                    if "form-data" in lines[j]:
                        parts = lines[j].split('|')
                        lib = parts[1].strip()
                        cve = parts[2].strip()
                        severity = parts[3].strip()
                        status = parts[4].strip()
                        installed = parts[5].strip()
                        fixed = parts[6].strip()
                        title = parts[7].strip()
                        vulns.append({
                            "library": lib,
                            "cve": cve,
                            "severity": severity,
                            "status": status,
                            "installed_version": installed,
                            "fixed_version": fixed,
                            "title": title,
                            "url": "https://avd.aquasec.com/nvd/" + cve.lower()
                        })
                        break
        if repo_slug == "woundhub":
            cross_repo = ["woundtech-ui", "clinical-service", "audit-service"]
    except Exception:
        # Always return mock for demo
        if repo_slug == "woundhub":
            vulns = [{
                "library": "form-data",
                "cve": "CVE-2025-7783",
                "severity": "CRITICAL",
                "status": "fixed",
                "installed_version": "4.0.2",
                "fixed_version": "2.5.4, 3.0.4, 4.0.4",
                "title": "form-data: Unsafe random function in form-data",
                "url": "https://avd.aquasec.com/nvd/cve-2025-7783"
            }]
            cross_repo = ["woundtech-ui", "clinical-service", "audit-service"]
    return {"repo": repo_slug, "vulnerabilities": vulns, "cross_repo": cross_repo}


@app.get("/api/resource-usage/{repo_slug}")
def get_resource_usage(repo_slug: str):
    """Mock CPU and memory utilization for a repo"""
    import random
    # For demo, randomize but keep woundhub high
    if repo_slug == "woundhub":
        cpu = 85.2
        mem = 92.7
        limit = 2048
        peak = 950
    else:
        cpu = round(random.uniform(10, 60), 1)
        mem = round(random.uniform(20, 80), 1)
        limit = 1024
        peak = round(mem * 10)
    return {
        "repo": repo_slug,
        "cpu_utilization_pct": cpu,
        "memory_utilization_pct": mem,
        "memory_limit_mb": limit,
        "memory_peak_mb": peak,
        "recommendation": f"Memory limit is {round(limit/peak,1)}× higher than peak usage; reduce to save build minutes."
    }

