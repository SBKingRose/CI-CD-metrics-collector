from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
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
        Build.state.in_(["FAILED", "ERROR"]),
        Build.completed_on.isnot(None)
    ).order_by(Build.completed_on.desc()).limit(limit).all()
    
    results = []
    for b in failures:
        # Try to find a failure record for a failed step
        step = next((s for s in b.steps if s.state in ["FAILED", "ERROR"]), None) if b.steps else None
        failure_record = None
        if step:
            failure_record = db.query(BuildFailure).filter(BuildFailure.step_id == step.id).first()
        
        # Check for cross-repo pattern matches
        cross_repo_count = 0
        if failure_record and failure_record.error_pattern:
            # Count how many other repos have this error pattern
            from sqlalchemy import func
            cross_repo_count = db.query(func.count(func.distinct(BuildFailure.build_id))).join(
                Build, Build.id == BuildFailure.build_id
            ).filter(
                Build.repository_id != repo_id,
                BuildFailure.error_pattern == failure_record.error_pattern
            ).scalar() or 0
        
        results.append({
            "build_id": b.id,
            "build_number": b.build_number,
            "commit_hash": b.commit_hash,
            "completed_at": b.completed_on.isoformat() if b.completed_on else None,
            "step": step.step_name if step else None,
            "error_message": failure_record.error_message[:300] if failure_record and failure_record.error_message else (step.log_excerpt[:300] if step and step.log_excerpt else None),
            "error_pattern": failure_record.error_pattern if failure_record else None,
            "cross_repo_count": cross_repo_count
        })
    
    return results

@app.get("/api/repositories/{repo_id}/last-5-pipelines")
def get_last_5_pipelines(repo_id: int, db: Session = Depends(get_db)):
    """Get last 5 pipelines with status and error summaries"""
    pipelines = db.query(Build).filter(
        Build.repository_id == repo_id
    ).order_by(Build.created_on.desc()).limit(5).all()
    
    results = []
    for b in pipelines:
        # Get failed step if any
        failed_step = next((s for s in b.steps if s.state in ["FAILED", "ERROR"]), None) if b.steps else None
        failure_record = None
        if failed_step:
            failure_record = db.query(BuildFailure).filter(BuildFailure.step_id == failed_step.id).first()
        
        # Check for cross-repo pattern matches
        cross_repo_count = 0
        if failure_record and failure_record.error_pattern:
            from sqlalchemy import func
            cross_repo_count = db.query(func.count(func.distinct(BuildFailure.build_id))).join(
                Build, Build.id == BuildFailure.build_id
            ).filter(
                Build.repository_id != repo_id,
                BuildFailure.error_pattern == failure_record.error_pattern
            ).scalar() or 0
        
        results.append({
            "build_id": b.id,
            "build_number": b.build_number,
            "state": b.state,
            "commit_hash": b.commit_hash,
            "created_at": b.created_on.isoformat() if b.created_on else None,
            "completed_at": b.completed_on.isoformat() if b.completed_on else None,
            "duration_seconds": b.duration_seconds,
            "failed_step": failed_step.step_name if failed_step else None,
            "error_message": failure_record.error_message[:500] if failure_record and failure_record.error_message else (failed_step.log_excerpt[:500] if failed_step and failed_step.log_excerpt else None),
            "error_pattern": failure_record.error_pattern if failure_record else None,
            "cross_repo_count": cross_repo_count,
            "log_url": f"https://bitbucket.org/{b.repository.workspace}/{b.repository.slug}/pipelines/results/{b.build_number}" if b.repository else None
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
    
    # Org-wide PR velocity
    pr_velocity = calculator.calculate_pr_velocity(days=days)
    
    # Org-wide deployment frequency (sum across all repos)
    deployment_freq = calculator.calculate_deployment_frequency(days=days)
    total_deployments = sum(deployment_freq.values()) if isinstance(deployment_freq, dict) else deployment_freq.get("count", 0)
    
    # Org-wide slow pipelines
    slow_pipelines = calculator.get_slow_pipelines(percentile=90)
    slow_count = len(slow_pipelines)
    
    # Get build stats from build_stats.json
    build_stats = {}
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    stats_path = os.path.abspath(os.path.join(project_root, 'build_stats.json'))
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for entry in data[1:]:
                if isinstance(entry, dict):
                    repo = entry.get("Repository", "")
                    if repo:
                        build_stats[repo] = {
                            "builds": entry.get("Builds", 0),
                            "build_duration": entry.get("Build Duration", "0d 0h 0m 0s"),
                            "build_minutes_used": entry.get("Build Minutes Used", "0d 0h 0m 0s"),
                            "build_minutes_decimal": 0.0  # Will be calculated if needed
                        }
    except:
        pass
    
    summary = {
        "total_repositories": len(repos),
        "pr_velocity": pr_velocity,
        "deployment_frequency": {"total": total_deployments, "by_repo": deployment_freq if isinstance(deployment_freq, dict) else {}},
        "build_minutes": calculator.calculate_build_minutes(days=days),
        "build_minutes_28_file": get_build_minutes_28_file(),
        "build_stats": build_stats,
        "slow_pipelines": {"total": slow_count, "by_repo": {}}
    }
    
    # Group slow pipelines by repo
    for sp in slow_pipelines:
        repo_id = sp.get("repository_id")
        if repo_id:
            if repo_id not in summary["slow_pipelines"]["by_repo"]:
                summary["slow_pipelines"]["by_repo"][repo_id] = []
            summary["slow_pipelines"]["by_repo"][repo_id].append(sp)
    
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

@app.get("/api/metrics/pr-velocity-org")
def get_pr_velocity_org(days: int = 30, db: Session = Depends(get_db)):
    """Get PR velocity across all repositories (org-wide)"""
    calculator = MetricsCalculator(db)
    return calculator.calculate_pr_velocity(days=days)

@app.get("/api/metrics/pr-velocity-by-repo")
def get_pr_velocity_by_repo(days: int = 30, db: Session = Depends(get_db)):
    """Get PR velocity per repository"""
    calculator = MetricsCalculator(db)
    repos = db.query(Repository).all()
    result = {}
    for repo in repos:
        velocity = calculator.calculate_pr_velocity(repo.id, days=days)
        result[repo.slug] = {
            "name": repo.name,
            "median_hours": velocity.get("median_hours"),
            "p90_hours": velocity.get("p90_hours"),
            "count": velocity.get("count", 0)
        }
    return result

@app.get("/api/metrics/deployment-frequency-org")
def get_deployment_frequency_org(days: int = 30, db: Session = Depends(get_db)):
    """Get total deployment frequency across all repositories"""
    calculator = MetricsCalculator(db)
    freq = calculator.calculate_deployment_frequency(days=days)
    total = sum(freq.values()) if isinstance(freq, dict) else freq.get("count", 0)
    return {"total": total}

@app.get("/api/metrics/deployment-frequency-by-repo")
def get_deployment_frequency_by_repo(days: int = 30, db: Session = Depends(get_db)):
    """Get deployment frequency per repository"""
    calculator = MetricsCalculator(db)
    repos = db.query(Repository).all()
    result = {}
    for repo in repos:
        freq = calculator.calculate_deployment_frequency(repo.id, days=days)
        result[repo.slug] = {
            "name": repo.name,
            "count": freq.get("count", 0)
        }
    return result

@app.get("/api/metrics/slow-pipelines-org")
def get_slow_pipelines_org(db: Session = Depends(get_db)):
    """Get total slow pipelines count across all repositories"""
    calculator = MetricsCalculator(db)
    slow = calculator.get_slow_pipelines(percentile=90)
    return {"total": len(slow)}

@app.get("/api/metrics/slow-pipelines-by-repo")
def get_slow_pipelines_by_repo(db: Session = Depends(get_db)):
    """Get slow pipelines count per repository with worst regression"""
    calculator = MetricsCalculator(db)
    repos = db.query(Repository).all()
    result = {}
    for repo in repos:
        slow = calculator.get_slow_pipelines(repo.id, percentile=90)
        worst = None
        if slow:
            # Find worst regression (highest delta%)
            worst = max(slow, key=lambda x: x.get("delta_vs_median_pct", 0) or 0)
        result[repo.slug] = {
            "name": repo.name,
            "count": len(slow),
            "worst_regression": {
                "delta_pct": worst.get("delta_vs_median_pct") if worst else None,
                "commit": worst.get("commit_hash", "")[:8] if worst else None
            } if worst else None
        }
    return result


@app.get("/api/metrics/build-minutes-28-file")
def get_build_minutes_28_file():
    """Get build minutes per repo from build_stats.json file (mocked for demo)"""
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    stats_path = os.path.abspath(os.path.join(project_root, 'build_stats.json'))
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Parse the file
        repo_minutes = {}
        total_minutes = 0.0
        for entry in data[1:]:
            if isinstance(entry, dict):
                repo = entry.get("Repository", "")
                if repo:
                    # Parse "Build Minutes Used" like "6d 14h 23m 0s"
                    build_minutes_str = entry.get("Build Minutes Used", "0d 0h 0m 0s")
                    parts = build_minutes_str.split()
                    mins = 0.0
                    for part in parts:
                        if part.endswith('d'):
                            mins += float(part[:-1]) * 24 * 60
                        elif part.endswith('h'):
                            mins += float(part[:-1]) * 60
                        elif part.endswith('m'):
                            mins += float(part[:-1])
                        elif part.endswith('s'):
                            mins += float(part[:-1]) / 60.0  # Convert seconds to minutes
                    repo_minutes[repo] = round(mins, 2)
                    total_minutes += mins
        # Round to 2 decimal places
        repo_minutes_rounded = {k: round(v, 2) for k, v in repo_minutes.items()}
        return {"by_repo": repo_minutes_rounded, "total_minutes": round(total_minutes, 2)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/metrics/build-stats-file")
def get_build_stats_file():
    """Get build stats per repo from build_stats.json file (always returns mock if missing)"""
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    stats_path = os.path.abspath(os.path.join(project_root, 'build_stats.json'))
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
        if isinstance(entry, dict):
            repo = entry.get("Repository", "")
            if repo:
                # Parse build minutes to decimal
                build_minutes_str = entry.get("Build Minutes Used", "0d 0h 0m 0s")
                parts = build_minutes_str.split()
                mins = 0
                for part in parts:
                    if part.endswith('d'):
                        mins += int(part[:-1]) * 24 * 60
                    elif part.endswith('h'):
                        mins += int(part[:-1]) * 60
                    elif part.endswith('m'):
                        mins += int(part[:-1])
                    elif part.endswith('s'):
                        mins += int(part[:-1]) / 60.0
                
                stats[repo] = {
                    "builds": entry.get("Builds", 0),
                    "build_duration": entry.get("Build Duration", "0d 0h 0m 0s"),
                    "build_minutes_used": entry.get("Build Minutes Used", "0d 0h 0m 0s"),
                    "build_minutes_decimal": round(mins, 2)
                }
    return stats

@app.get("/api/repositories/{repo_slug}/build-stats")
def get_repo_build_stats(repo_slug: str):
    """Get build stats for a specific repository from build_stats.json"""
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    stats_path = os.path.abspath(os.path.join(project_root, 'build_stats.json'))
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find matching repo (handle both "emr-dev/repo" and "repo" formats)
        for entry in data[1:]:
            if isinstance(entry, dict):
                repo_full = entry.get("Repository", "")
                if repo_slug in repo_full or repo_full.endswith(f"/{repo_slug}"):
                    build_minutes_str = entry.get("Build Minutes Used", "0d 0h 0m 0s")
                    parts = build_minutes_str.split()
                    mins = 0.0
                    for part in parts:
                        if part.endswith('d'):
                            mins += float(part[:-1]) * 24 * 60
                        elif part.endswith('h'):
                            mins += float(part[:-1]) * 60
                        elif part.endswith('m'):
                            mins += float(part[:-1])
                        elif part.endswith('s'):
                            mins += float(part[:-1]) / 60.0
                    
                    return {
                        "repository": repo_full,
                        "builds": entry.get("Builds", 0),
                        "build_duration": entry.get("Build Duration", "0d 0h 0m 0s"),
                        "build_minutes_used": entry.get("Build Minutes Used", "0d 0h 0m 0s"),
                        "build_minutes_decimal": round(mins, 2)
                    }
    except Exception as e:
        pass
    return {"error": "Repository not found in build_stats.json"}

@app.get("/api/repositories/{repo_id}/latest-deployment")
def get_latest_deployment(repo_id: int, db: Session = Depends(get_db)):
    """Get latest build deployed for a repository (across all environments)"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get latest deployment
    latest_dep = db.query(Deployment).filter(
        Deployment.repository_id == repo_id
    ).order_by(Deployment.deployed_at.desc().nullslast()).first()
    
    if not latest_dep:
        return {"repository": repo.slug, "latest_deployment": None}
    
    build_number = None
    if latest_dep.build_id:
        build = db.query(Build).filter(Build.id == latest_dep.build_id).first()
        build_number = build.build_number if build else None
    
    return {
        "repository": repo.slug,
        "latest_deployment": {
            "environment": latest_dep.environment,
            "build_number": build_number,
            "commit_hash": latest_dep.commit_hash,
            "deployed_at": latest_dep.deployed_at.isoformat() if latest_dep.deployed_at else None,
            "docker_image": latest_dep.docker_image
        }
    }

@app.get("/api/repositories/{repo_id}/build-numbers-by-environment")
def get_build_numbers_by_environment(repo_id: int, db: Session = Depends(get_db)):
    """Get latest build number deployed in each environment"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get latest deployment per environment
    from sqlalchemy import func
    deployments = db.query(
        Deployment.environment,
        func.max(Deployment.deployed_at).label('latest_deployed_at'),
        Deployment.build_id
    ).filter(
        Deployment.repository_id == repo_id
    ).group_by(Deployment.environment, Deployment.build_id).all()
    
    # Get the actual latest deployment per environment
    result = {}
    for env, latest_at, build_id in deployments:
        if env not in result or (latest_at and result[env].get("deployed_at") and latest_at > result[env]["deployed_at"]):
            build = db.query(Build).filter(Build.id == build_id).first() if build_id else None
            result[env] = {
                "environment": env,
                "build_number": build.build_number if build else None,
                "commit_hash": build.commit_hash if build else None,
                "deployed_at": latest_at.isoformat() if latest_at else None
            }
    
    return {"repository": repo.slug, "by_environment": result}

@app.get("/api/repositories/{repo_id}/slow-pipeline-analysis")
def get_slow_pipeline_analysis(repo_id: int, db: Session = Depends(get_db)):
    """Get slow pipeline analysis with commit info (Repo X slower by Y% after commit Z)"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    calculator = MetricsCalculator(db)
    slow_pipelines = calculator.get_slow_pipelines(repo_id, percentile=90)
    
    results = []
    for sp in slow_pipelines:
        build_id = sp.get("build_id")
        if build_id:
            build = db.query(Build).filter(Build.id == build_id).first()
            if build:
                delta_pct = sp.get("delta_vs_median_pct", 0)
                slower_by_pct = abs(delta_pct) if delta_pct > 0 else 0
                commit_short = build.commit_hash[:8] if build.commit_hash else "unknown"
                
                results.append({
                    "build_id": build.id,
                    "build_number": build.build_number,
                    "commit_hash": build.commit_hash,
                    "duration_seconds": build.duration_seconds,
                    "median_duration_seconds": sp.get("median_duration_seconds"),
                    "delta_pct": delta_pct,
                    "slower_by_pct": slower_by_pct,
                    "created_at": build.created_on.isoformat() if build.created_on else None,
                    "message": f"{repo.name} is slower by {slower_by_pct:.1f}% after commit {commit_short}"
                })
    
    return {
        "repository": repo.slug,
        "repository_name": repo.name,
        "analysis": results,
        "message": f"Found {len(results)} slow pipelines above P90 threshold"
    }

@app.get("/api/repositories/{repo_id}/pipeline-comparisons")
def get_pipeline_comparisons(repo_id: int, limit: int = 20, db: Session = Depends(get_db)):
    """Get successful pipelines with comparison to previous pipeline (how much faster/slower)"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get successful builds ordered by completion time (newest first)
    builds = db.query(Build).filter(
        Build.repository_id == repo_id,
        Build.state == "SUCCESSFUL",
        Build.completed_on.isnot(None),
        Build.duration_seconds.isnot(None)
    ).order_by(Build.completed_on.desc()).limit(limit).all()
    
    if not builds:
        return {
            "repository": repo.slug,
            "repository_name": repo.name,
            "pipelines": [],
            "message": "No successful pipelines found"
        }
    
    results = []
    for i, build in enumerate(builds):
        # Compare to previous build (next in list since we're descending)
        prev_build = builds[i + 1] if i + 1 < len(builds) else None
        
        comparison = None
        if prev_build and prev_build.duration_seconds:
            delta_seconds = build.duration_seconds - prev_build.duration_seconds
            delta_pct = (delta_seconds / prev_build.duration_seconds) * 100 if prev_build.duration_seconds > 0 else 0
            
            if delta_pct > 0:
                comparison = f"Slower by {abs(delta_pct):.1f}% ({abs(delta_seconds):.1f}s) compared to previous pipeline"
            elif delta_pct < 0:
                comparison = f"Faster by {abs(delta_pct):.1f}% ({abs(delta_seconds):.1f}s) compared to previous pipeline"
            else:
                comparison = "Same duration as previous pipeline"
        else:
            comparison = "No previous pipeline to compare"
        
        commit_short = build.commit_hash[:8] if build.commit_hash else "unknown"
        prev_commit_short = prev_build.commit_hash[:8] if prev_build and prev_build.commit_hash else None
        
        results.append({
            "build_id": build.id,
            "build_number": build.build_number,
            "commit_hash": build.commit_hash,
            "commit_short": commit_short,
            "duration_seconds": build.duration_seconds,
            "duration_minutes": round(build.duration_seconds / 60, 2) if build.duration_seconds else None,
            "completed_at": build.completed_on.isoformat() if build.completed_on else None,
            "previous_build_number": prev_build.build_number if prev_build else None,
            "previous_commit": prev_commit_short,
            "previous_duration_seconds": prev_build.duration_seconds if prev_build else None,
            "comparison": comparison,
            "delta_pct": ((build.duration_seconds - prev_build.duration_seconds) / prev_build.duration_seconds * 100) if prev_build and prev_build.duration_seconds else None
        })
    
    return {
        "repository": repo.slug,
        "repository_name": repo.name,
        "pipelines": results,
        "message": f"Found {len(results)} successful pipelines"
    }

@app.get("/api/repositories/{repo_id}/last-pipeline-deployment-time")
def get_last_pipeline_deployment_time(repo_id: int, db: Session = Depends(get_db)):
    """Get the last pipeline deployment time for a repository"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get latest successful pipeline (any state, but prefer SUCCESSFUL)
    latest_build = db.query(Build).filter(
        Build.repository_id == repo_id,
        Build.completed_on.isnot(None)
    ).order_by(
        Build.completed_on.desc()
    ).first()
    
    if not latest_build:
        return {
            "repository": repo.slug,
            "last_deployment_time": None,
            "build_number": None,
            "commit_hash": None,
            "duration_seconds": None
        }
    
    return {
        "repository": repo.slug,
        "last_deployment_time": latest_build.completed_on.isoformat() if latest_build.completed_on else None,
        "build_number": latest_build.build_number,
        "commit_hash": latest_build.commit_hash,
        "duration_seconds": latest_build.duration_seconds,
        "state": latest_build.state
    }


@app.get("/api/repositories/{repo_slug}/latest-failure-analysis")
def get_latest_failure_analysis(repo_slug: str, db: Session = Depends(get_db)):
    """Get latest failed pipeline analysis with error details, cross-repo matches, and fix suggestions"""
    from app.analytics.error_analyzer import ErrorAnalyzer
    
    analyzer = ErrorAnalyzer(db)
    analysis = analyzer.analyze_latest_failure(repo_slug)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    return analysis

@app.get("/api/repositories/{repo_id}/latest-failure-analysis-by-id")
def get_latest_failure_analysis_by_id(repo_id: int, db: Session = Depends(get_db)):
    """Get latest failed pipeline analysis by repository ID"""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    from app.analytics.error_analyzer import ErrorAnalyzer
    analyzer = ErrorAnalyzer(db)
    analysis = analyzer.analyze_latest_failure(repo.slug)
    
    if not analysis:
        return {
            "status": "OK",
            "message": "Latest pipeline succeeded",
            "repository": repo.slug
        }
    
    return analysis


def _parse_trivy_table_format(content: str) -> List[Dict]:
    """Parse trivy table format report (text) into structured data"""
    vulns = []
    lines = content.split('\n')
    
    # Find the table section - look for header row with "Library" and "Vulnerability"
    in_table = False
    header_found = False
    current_row_parts = None
    current_url = ""
    
    for i, line in enumerate(lines):
        # Look for table header row
        if ("│  Library  │" in line) or ("Library" in line and "Vulnerability" in line and "│" in line):
            header_found = True
            in_table = True
            continue
        
        # Skip separator lines (┌, ├)
        if line.strip().startswith("┌") or (line.strip().startswith("├") and not in_table):
            continue
        
        # Stop at end of table
        if line.strip().startswith("└") and in_table:
            # Process any pending row before stopping
            if current_row_parts:
                library = current_row_parts[0] if len(current_row_parts) > 0 else ""
                cve = current_row_parts[1] if len(current_row_parts) > 1 else ""
                if library and cve:
                    severity = current_row_parts[2] if len(current_row_parts) > 2 else ""
                    status = current_row_parts[3] if len(current_row_parts) > 3 else "unknown"
                    installed_version = current_row_parts[4] if len(current_row_parts) > 4 else ""
                    fixed_version = current_row_parts[5] if len(current_row_parts) > 5 else ""
                    title = current_row_parts[6] if len(current_row_parts) > 6 else ""
                    
                    vulns.append({
                        "library": library,
                        "cve": cve,
                        "severity": severity,
                        "status": status,
                        "installed_version": installed_version,
                        "fixed_version": fixed_version,
                        "title": title,
                        "url": current_url
                    })
            break
        
        # Parse data rows
        if in_table and header_found and "│" in line:
            # Split by │ and clean up parts
            parts = [p.strip() for p in line.split('│')]
            # Remove empty first/last elements from split (they come from leading/trailing │)
            if parts and not parts[0]:
                parts = parts[1:]
            if parts and not parts[-1]:
                parts = parts[:-1]
            
            # Check if this is a continuation line (mostly empty except for URL in last column)
            # Example: │           │               │          │        │                   │                     │ https://... │
            is_continuation = False
            if len(parts) >= 7 and current_row_parts:
                # Check if first 6 columns are mostly empty (just whitespace)
                non_empty_count = sum(1 for p in parts[:6] if p and p.strip())
                # Check if there's a URL in the last column
                has_url = any("https://" in p for p in parts[6:])
                if non_empty_count == 0 and has_url:
                    is_continuation = True
                    # Extract URL from continuation line
                    for p in parts[6:]:
                        if "https://" in p:
                            current_url = p.strip()
                            break
            
            # If it's a data row (not continuation)
            if not is_continuation and len(parts) >= 4:
                # Save previous row if exists
                if current_row_parts:
                    library = current_row_parts[0] if len(current_row_parts) > 0 else ""
                    cve = current_row_parts[1] if len(current_row_parts) > 1 else ""
                    if library and cve:
                        severity = current_row_parts[2] if len(current_row_parts) > 2 else ""
                        status = current_row_parts[3] if len(current_row_parts) > 3 else "unknown"
                        installed_version = current_row_parts[4] if len(current_row_parts) > 4 else ""
                        fixed_version = current_row_parts[5] if len(current_row_parts) > 5 else ""
                        title = current_row_parts[6] if len(current_row_parts) > 6 else ""
                        
                        vulns.append({
                            "library": library,
                            "cve": cve,
                            "severity": severity,
                            "status": status,
                            "installed_version": installed_version,
                            "fixed_version": fixed_version,
                            "title": title,
                            "url": current_url
                        })
                
                # Start new row
                current_row_parts = parts
                current_url = ""
                
                # Check if URL is in this row
                if len(parts) > 7:
                    for p in parts[7:]:
                        if "https://" in p:
                            current_url = p.strip()
                            break
                elif any("https://" in p for p in parts):
                    for p in parts:
                        if "https://" in p:
                            url_start = p.find("https://")
                            current_url = p[url_start:].split()[0] if url_start >= 0 else ""
                            break
    
    # Process last row if exists
    if current_row_parts:
        library = current_row_parts[0] if len(current_row_parts) > 0 else ""
        cve = current_row_parts[1] if len(current_row_parts) > 1 else ""
        if library and cve:
            severity = current_row_parts[2] if len(current_row_parts) > 2 else ""
            status = current_row_parts[3] if len(current_row_parts) > 3 else "unknown"
            installed_version = current_row_parts[4] if len(current_row_parts) > 4 else ""
            fixed_version = current_row_parts[5] if len(current_row_parts) > 5 else ""
            title = current_row_parts[6] if len(current_row_parts) > 6 else ""
            
            vulns.append({
                "library": library,
                "cve": cve,
                "severity": severity,
                "status": status,
                "installed_version": installed_version,
                "fixed_version": fixed_version,
                "title": title,
                "url": current_url
            })
    
    return vulns

def _find_cross_repo_vulnerabilities(current_repo: str, vulns: List[Dict], fixtures_dir: str) -> Dict[str, List[str]]:
    """Find which vulnerabilities exist in other repositories"""
    cross_repo_map = {}
    
    # Get all repo directories
    if not os.path.exists(fixtures_dir):
        return cross_repo_map
    
    for vuln in vulns:
        cve_id = vuln.get("cve") or vuln.get("id") or vuln.get("VulnerabilityID", "")
        if not cve_id:
            continue
        
        affected_repos = []
        
        # Check all other repos
        for item in os.listdir(fixtures_dir):
            repo_path = os.path.join(fixtures_dir, item)
            if os.path.isdir(repo_path) and item != current_repo:
                trivy_path = os.path.join(repo_path, 'trivy-report.json')
                if os.path.exists(trivy_path):
                    try:
                        with open(trivy_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Try JSON first
                            try:
                                data = json.loads(content)
                                if isinstance(data, dict) and "Results" in data:
                                    # Check all vulnerabilities in JSON format
                                    found_in_this_repo = False
                                    for result in data.get("Results", []):
                                        for other_vuln in result.get("Vulnerabilities", []):
                                            if other_vuln.get("VulnerabilityID") == cve_id:
                                                affected_repos.append(item)
                                                found_in_this_repo = True
                                                break
                                        if found_in_this_repo:
                                            break
                                elif isinstance(data, list):
                                    # Simple list format
                                    for other_vuln in data:
                                        if (other_vuln.get("cve") == cve_id or 
                                            other_vuln.get("id") == cve_id or
                                            other_vuln.get("VulnerabilityID") == cve_id):
                                            affected_repos.append(item)
                                            break
                            except json.JSONDecodeError:
                                # Table format - check if CVE is in content
                                if cve_id in content:
                                    affected_repos.append(item)
                    except:
                        pass
        
        if affected_repos:
            cross_repo_map[cve_id] = affected_repos
    
    return cross_repo_map

@app.get("/api/vulnerabilities/{repo_slug}")
def get_vulnerabilities(repo_slug: str, db: Session = Depends(get_db)):
    """Get vulnerabilities for a repo from fixtures/{repo_slug}/trivy-report.json (JSON or table format)"""
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    fixtures_dir = os.path.abspath(os.path.join(project_root, 'fixtures'))
    
    # Handle both "emr-dev/repo" and "repo" formats
    repo_name = repo_slug
    if '/' in repo_slug:
        repo_name = repo_slug.split('/')[-1]  # Get last part after /
    
    trivy_path = os.path.abspath(os.path.join(fixtures_dir, repo_name, 'trivy-report.json'))
    
    vulns = []
    cross_repo_map = {}
    
    # Try to load repo-specific file
    if os.path.exists(trivy_path):
        try:
            with open(trivy_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Try JSON first
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and "Results" in data:
                        # Full Trivy JSON format
                        for result in data.get("Results", []):
                            vulnerabilities = result.get("Vulnerabilities", [])
                            if vulnerabilities:
                                for vuln in vulnerabilities:
                                    vulns.append({
                                        "library": vuln.get("PkgName", ""),
                                        "cve": vuln.get("VulnerabilityID", ""),
                                        "severity": vuln.get("Severity", ""),
                                        "status": vuln.get("Status", "unknown"),
                                        "installed_version": vuln.get("InstalledVersion", ""),
                                        "fixed_version": vuln.get("FixedVersion", ""),
                                        "title": vuln.get("Title", ""),
                                        "url": vuln.get("PrimaryURL", "")
                                    })
                    elif isinstance(data, list):
                        # Simple list format
                        vulns = data
                except json.JSONDecodeError:
                    # Parse table format (text)
                    vulns = _parse_trivy_table_format(content)
        except Exception as e:
            import traceback
            return {
                "error": f"Failed to parse trivy-report.json: {str(e)}", 
                "vulnerabilities": [], 
                "cross_repo": {},
                "repo_slug": repo_slug,
                "repo_name": repo_name,
                "searched_path": trivy_path,
                "traceback": traceback.format_exc()
            }
    else:
        return {
            "error": f"File not found: {trivy_path}", 
            "vulnerabilities": [], 
            "cross_repo": {}, 
            "repo_slug": repo_slug, 
            "repo_name": repo_name, 
            "searched_path": trivy_path,
            "fixtures_dir": fixtures_dir
        }
    
    # Cross-repo vulnerability matching (use repo_name for matching, not full slug)
    if vulns:
        cross_repo_map = _find_cross_repo_vulnerabilities(repo_name, vulns, fixtures_dir)
    
    # Format response with cross-repo info
    vulns_with_cross_repo = []
    for vuln in vulns:
        cve_id = vuln.get("cve") or vuln.get("id") or vuln.get("VulnerabilityID", "")
        if cve_id:
            affected_repos = cross_repo_map.get(cve_id, [])
            vuln["cross_repo_count"] = len(affected_repos)
            vuln["cross_repo_names"] = affected_repos
        else:
            vuln["cross_repo_count"] = 0
            vuln["cross_repo_names"] = []
        vulns_with_cross_repo.append(vuln)
    
    return {"repo": repo_slug, "repo_name": repo_name, "vulnerabilities": vulns_with_cross_repo, "cross_repo": cross_repo_map}


@app.get("/api/resource-usage/{repo_slug}")
def get_resource_usage(repo_slug: str):
    """Get CPU and memory utilization for a repo from fixtures/{repo_slug}/metrics.json"""
    # Get project root directory (parent of app directory) - use absolute path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(app_dir)
    fixtures_dir = os.path.abspath(os.path.join(project_root, 'fixtures'))
    
    # Handle both "emr-dev/repo" and "repo" formats
    repo_name = repo_slug
    if '/' in repo_slug:
        repo_name = repo_slug.split('/')[-1]
    
    metrics_path = os.path.abspath(os.path.join(fixtures_dir, repo_name, 'metrics.json'))
    
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Parse metrics JSON (adjust based on actual format from Bitbucket)
                # Expected format: {"cpu": {...}, "memory": {...}, "steps": [...]}
                cpu_pct = data.get("cpu", {}).get("utilization_pct", 0)
                mem_pct = data.get("memory", {}).get("utilization_pct", 0)
                mem_limit = data.get("memory", {}).get("limit_mb", 0)
                mem_peak = data.get("memory", {}).get("peak_mb", 0)
                
                waste_ratio = round(mem_limit / mem_peak, 1) if mem_peak > 0 else 0
                recommendation = f"Memory limit is {waste_ratio}× higher than peak usage; reduce to save build minutes." if waste_ratio > 2 else "Memory usage is within acceptable limits."
                
                return {
                    "repo": repo_slug,
                    "cpu_utilization_pct": cpu_pct,
                    "memory_utilization_pct": mem_pct,
                    "memory_limit_mb": mem_limit,
                    "memory_peak_mb": mem_peak,
                    "recommendation": recommendation,
                    "source": "fixtures"
                }
        except Exception as e:
            return {"error": f"Failed to parse metrics.json: {str(e)}", "repo": repo_slug}
    else:
        # Fallback: return mock data
        import random
        cpu = round(random.uniform(10, 60), 1)
        mem = round(random.uniform(20, 80), 1)
        limit = 1024
        peak = round(mem * 10)
        waste_ratio = round(limit / peak, 1) if peak > 0 else 0
        return {
            "repo": repo_slug,
            "cpu_utilization_pct": cpu,
            "memory_utilization_pct": mem,
            "memory_limit_mb": limit,
            "memory_peak_mb": peak,
            "recommendation": f"Memory limit is {waste_ratio}× higher than peak usage; reduce to save build minutes." if waste_ratio > 2 else "Memory usage is within acceptable limits.",
            "source": "mock"
        }

