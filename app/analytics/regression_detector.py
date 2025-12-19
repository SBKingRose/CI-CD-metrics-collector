from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models import Build, BuildStep, Repository


class RegressionDetector:
    def __init__(self, db: Session):
        self.db = db
    
    def detect_build_duration_regression(self, repository_id: int, days_baseline: int = 14) -> Optional[Dict]:
        """Detect if build duration has regressed compared to baseline"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_baseline)
        
        # Get baseline builds (older than cutoff)
        baseline_builds = self.db.query(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                Build.completed_on < cutoff_date,
                Build.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.desc()).limit(50).all()
        
        # Get recent builds
        recent_builds = self.db.query(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                Build.completed_on >= cutoff_date,
                Build.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.desc()).limit(50).all()
        
        # If we don't have enough history older than cutoff, fall back to a within-window split
        # so hackathon demos still produce meaningful output.
        if len(baseline_builds) < 5 or len(recent_builds) < 5:
            window_builds = self.db.query(Build).filter(
                and_(
                    Build.repository_id == repository_id,
                    Build.state == "SUCCESSFUL",
                    Build.duration_seconds.isnot(None)
                )
            ).order_by(Build.completed_on.desc()).limit(40).all()
            if len(window_builds) < 10:
                return None
            midpoint = len(window_builds) // 2
            recent_builds = window_builds[:midpoint]
            baseline_builds = window_builds[midpoint:]
        
        baseline_median = np.median([b.duration_seconds for b in baseline_builds])
        recent_median = np.median([b.duration_seconds for b in recent_builds])
        
        if recent_median > baseline_median * 1.2:  # 20% regression threshold
            regression_pct = ((recent_median - baseline_median) / baseline_median) * 100
            
            # Find the commit that might have caused it
            recent_build = recent_builds[0]
            
            return {
                "type": "build_duration_regression",
                "repository_id": repository_id,
                "baseline_median": baseline_median,
                "recent_median": recent_median,
                "regression_percent": regression_pct,
                "commit_hash": recent_build.commit_hash,
                "baseline_count": len(baseline_builds),
                "recent_count": len(recent_builds),
                "note": "Computed using an internal split of recent history due to limited baseline history."
            }
        
        return None
    
    def detect_step_regression(self, repository_id: int, step_name: str, days_baseline: int = 14) -> Optional[Dict]:
        """Detect if a specific step has regressed"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_baseline)
        
        # Get baseline step durations
        baseline_steps = self.db.query(BuildStep).join(Build).filter(
            and_(
                Build.repository_id == repository_id,
                BuildStep.step_name == step_name,
                Build.state == "SUCCESSFUL",
                Build.completed_on < cutoff_date,
                BuildStep.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.desc()).limit(50).all()
        
        # Get recent step durations
        recent_steps = self.db.query(BuildStep).join(Build).filter(
            and_(
                Build.repository_id == repository_id,
                BuildStep.step_name == step_name,
                Build.state == "SUCCESSFUL",
                Build.completed_on >= cutoff_date,
                BuildStep.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.desc()).limit(50).all()
        
        if len(baseline_steps) < 5 or len(recent_steps) < 5:
            return None
        
        baseline_median = np.median([s.duration_seconds for s in baseline_steps])
        recent_median = np.median([s.duration_seconds for s in recent_steps])
        
        if recent_median > baseline_median * 1.2:
            regression_pct = ((recent_median - baseline_median) / baseline_median) * 100
            
            # Get the build that might have caused it
            recent_step = recent_steps[0]
            
            return {
                "type": "step_regression",
                "repository_id": repository_id,
                "step_name": step_name,
                "baseline_median": baseline_median,
                "recent_median": recent_median,
                "regression_percent": regression_pct,
                "commit_hash": recent_step.build.commit_hash,
                "build_id": recent_step.build_id
            }
        
        return None
    
    def detect_resource_waste(self, repository_id: int) -> List[Dict]:
        """Detect over-provisioned steps (memory/time limits much higher than usage)"""
        waste_findings = []
        
        # Try memory-based waste detection first
        steps_with_memory = self.db.query(BuildStep).join(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                BuildStep.peak_memory_mb.isnot(None),
                BuildStep.memory_limit_mb.isnot(None)
            )
        ).all()
        
        if steps_with_memory:
            step_groups = {}
            for step in steps_with_memory:
                if step.step_name not in step_groups:
                    step_groups[step.step_name] = []
                step_groups[step.step_name].append(step)
            
            for step_name, step_list in step_groups.items():
                if len(step_list) < 5:
                    continue
                
                avg_peak = np.mean([s.peak_memory_mb for s in step_list if s.peak_memory_mb])
                avg_limit = np.mean([s.memory_limit_mb for s in step_list if s.memory_limit_mb])
                
                if avg_limit > avg_peak * 2:  # Limit is 2x higher than peak
                    waste_ratio = avg_limit / avg_peak if avg_peak > 0 else 0
                    
                    waste_findings.append({
                        "type": "memory_waste",
                        "repository_id": repository_id,
                        "step_name": step_name,
                        "avg_peak_mb": avg_peak,
                        "avg_limit_mb": avg_limit,
                        "waste_ratio": waste_ratio,
                        "recommended_limit_mb": int(avg_peak * 1.5)  # 50% buffer
                    })
        
        # Fallback: Time-based waste detection (more reliable with Bitbucket API)
        steps_with_time = self.db.query(BuildStep).join(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                BuildStep.duration_seconds.isnot(None),
                BuildStep.max_time_seconds.isnot(None)
            )
        ).all()
        
        if steps_with_time:
            step_groups = {}
            for step in steps_with_time:
                if step.step_name not in step_groups:
                    step_groups[step.step_name] = []
                step_groups[step.step_name].append(step)
            
            for step_name, step_list in step_groups.items():
                if len(step_list) < 5:
                    continue
                
                avg_duration = np.mean([s.duration_seconds for s in step_list if s.duration_seconds])
                avg_max_time = np.mean([s.max_time_seconds for s in step_list if s.max_time_seconds])
                
                if avg_max_time > avg_duration * 2:  # Max time is 2x higher than actual
                    waste_ratio = avg_max_time / avg_duration if avg_duration > 0 else 0
                    
                    waste_findings.append({
                        "type": "time_waste",
                        "repository_id": repository_id,
                        "step_name": step_name,
                        "avg_duration_seconds": avg_duration,
                        "avg_max_time_seconds": avg_max_time,
                        "waste_ratio": waste_ratio,
                        "recommended_max_time_seconds": int(avg_duration * 1.5)  # 50% buffer
                    })
        
        return waste_findings
    
    def detect_cross_repo_step_regression(self, step_name: str, days_baseline: int = 14) -> Optional[Dict]:
        """Detect if a specific step has regressed across multiple repositories"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_baseline)
        
        # Get all repositories
        repos = self.db.query(Repository).all()
        
        regressed_repos = []
        for repo in repos:
            baseline_steps = self.db.query(BuildStep).join(Build).filter(
                and_(
                    Build.repository_id == repo.id,
                    BuildStep.step_name == step_name,
                    Build.state == "SUCCESSFUL",
                    Build.completed_on < cutoff_date,
                    BuildStep.duration_seconds.isnot(None)
                )
            ).order_by(Build.completed_on.desc()).limit(50).all()
            
            recent_steps = self.db.query(BuildStep).join(Build).filter(
                and_(
                    Build.repository_id == repo.id,
                    BuildStep.step_name == step_name,
                    Build.state == "SUCCESSFUL",
                    Build.completed_on >= cutoff_date,
                    BuildStep.duration_seconds.isnot(None)
                )
            ).order_by(Build.completed_on.desc()).limit(50).all()
            
            if len(baseline_steps) >= 5 and len(recent_steps) >= 5:
                baseline_median = np.median([s.duration_seconds for s in baseline_steps])
                recent_median = np.median([s.duration_seconds for s in recent_steps])
                
                if recent_median > baseline_median * 1.2:
                    regression_pct = ((recent_median - baseline_median) / baseline_median) * 100
                    regressed_repos.append({
                        "repository_id": repo.id,
                        "repository_name": repo.name,
                        "regression_percent": regression_pct,
                        "baseline_median": baseline_median,
                        "recent_median": recent_median
                    })
        
        if len(regressed_repos) >= 2:  # At least 2 repos showing regression
            avg_regression = np.mean([r["regression_percent"] for r in regressed_repos])
            return {
                "type": "cross_repo_step_regression",
                "step_name": step_name,
                "regressed_repos": regressed_repos,
                "repo_count": len(regressed_repos),
                "avg_regression_percent": avg_regression
            }
        
        return None

