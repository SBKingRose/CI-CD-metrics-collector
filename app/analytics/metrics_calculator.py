from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models import Build, PullRequest, Deployment, Repository, BuildStep
import numpy as np


class MetricsCalculator:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_pr_velocity(self, repository_id: Optional[int] = None, days: int = 30) -> Dict:
        """Calculate PR velocity metrics (median and P90)"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = self.db.query(PullRequest).filter(
            and_(
                PullRequest.state == "MERGED",
                PullRequest.merged_at >= cutoff_date
            )
        )
        
        if repository_id:
            query = query.filter(PullRequest.repository_id == repository_id)
        
        prs = query.all()
        
        if not prs:
            return {"median_hours": None, "p90_hours": None, "count": 0}
        
        # Calculate time to merge for each PR
        merge_times = []
        for pr in prs:
            if pr.created_at and pr.merged_at:
                delta = pr.merged_at - pr.created_at
                merge_times.append(delta.total_seconds() / 3600)  # Convert to hours
        
        if not merge_times:
            return {"median_hours": None, "p90_hours": None, "count": len(prs)}
        
        median = np.median(merge_times)
        p90 = np.percentile(merge_times, 90)
        
        return {
            "median_hours": float(median),
            "p90_hours": float(p90),
            "count": len(prs)
        }
    
    def calculate_deployment_frequency(self, repository_id: Optional[int] = None, days: int = 30) -> Dict:
        """Calculate deployment frequency per repository"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = self.db.query(
            Deployment.repository_id,
            func.count(Deployment.id).label('count')
        ).filter(
            Deployment.deployed_at >= cutoff_date
        )
        
        if repository_id:
            query = query.filter(Deployment.repository_id == repository_id)
        
        query = query.group_by(Deployment.repository_id)
        
        results = query.all()
        
        if repository_id:
            return {"count": results[0].count if results else 0}
        else:
            return {
                repo_id: count
                for repo_id, count in [(r.repository_id, r.count) for r in results]
            }
    
    def calculate_build_duration_trends(self, repository_id: int, days: int = 30) -> List[Dict]:
        """Calculate build duration trends over time"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        builds = self.db.query(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                Build.completed_on >= cutoff_date,
                Build.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.asc()).all()
        
        # Group by day
        daily_stats = {}
        for build in builds:
            day = build.completed_on.date()
            if day not in daily_stats:
                daily_stats[day] = []
            daily_stats[day].append(build.duration_seconds)
        
        trends = []
        for day, durations in sorted(daily_stats.items()):
            trends.append({
                "date": day.isoformat(),
                "median_duration": float(np.median(durations)),
                "p90_duration": float(np.percentile(durations, 90)),
                "count": len(durations)
            })
        
        return trends
    
    def calculate_build_minutes(self, repository_id: Optional[int] = None, days: int = 30) -> Dict:
        """
        Calculate total build minutes consumed.
        Uses step-weighted minutes when step durations are available:
          minutes = sum(step_duration_seconds * size_factor) / 60
        Falls back to pipeline duration_seconds when step data is missing.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Step-weighted aggregation
        step_rows = self.db.query(
            Build.repository_id,
            func.sum((BuildStep.duration_seconds) * func.coalesce(BuildStep.size_factor, 1)).label("weighted_seconds"),
        ).join(BuildStep, BuildStep.build_id == Build.id).filter(
            and_(
                Build.completed_on >= cutoff_date,
                BuildStep.duration_seconds.isnot(None),
            )
        )
        if repository_id:
            step_rows = step_rows.filter(Build.repository_id == repository_id)
        step_rows = step_rows.group_by(Build.repository_id).all()
        step_map = {rid: (ws or 0.0) for rid, ws in step_rows}

        # Fallback pipeline-level aggregation
        pipe_rows = self.db.query(
            Build.repository_id,
            func.sum(Build.duration_seconds).label("total_seconds"),
        ).filter(
            and_(
                Build.completed_on >= cutoff_date,
                Build.duration_seconds.isnot(None),
            )
        )
        if repository_id:
            pipe_rows = pipe_rows.filter(Build.repository_id == repository_id)
        pipe_rows = pipe_rows.group_by(Build.repository_id).all()
        pipe_map = {rid: (ts or 0.0) for rid, ts in pipe_rows}

        # Prefer weighted seconds if present for that repo, else fall back
        def _minutes_for_repo(rid: int) -> float:
            secs = step_map.get(rid, 0.0)
            if secs <= 0.0:
                secs = pipe_map.get(rid, 0.0)
            return float(secs) / 60.0

        if repository_id:
            return {"total_minutes": _minutes_for_repo(repository_id)}

        repo_ids = set(pipe_map.keys()) | set(step_map.keys())
        return {rid: _minutes_for_repo(rid) for rid in repo_ids}

    def calculate_build_minutes_28_to_28(self, repository_id: Optional[int] = None, reference_date: Optional[datetime] = None) -> Dict:
        """
        Calculate build minutes for the closed monthly window that runs from the 28th of a month
        through the 28th of the next month. If reference_date is provided, the method will find
        the most recent 28th <= reference_date as the period end, otherwise uses now().

        Returns a dict with keys:
          - total_minutes: float (sum across all repos)
          - by_repo: {repo_id: minutes}
          - period_start: ISO datetime
          - period_end: ISO datetime
        """
        # Determine reference date in UTC
        ref = reference_date or datetime.now(timezone.utc)

        # Helper to get previous month
        def prev_month(year: int, month: int):
            if month == 1:
                return year - 1, 12
            return year, month - 1

        # Find the period end: the most recent 28th on or before ref
        end_year = ref.year
        end_month = ref.month
        if ref.day < 28:
            end_year, end_month = prev_month(end_year, end_month)
        period_end = datetime(end_year, end_month, 28, tzinfo=timezone.utc)
        # period start is 28th of previous month
        start_year, start_month = prev_month(period_end.year, period_end.month)
        period_start = datetime(start_year, start_month, 28, tzinfo=timezone.utc)
        # end exclusive -> add one day to include entire 28th
        period_end_excl = period_end + timedelta(days=1)

        # Step-weighted aggregation within window
        step_rows = self.db.query(
            Build.repository_id,
            func.sum((BuildStep.duration_seconds) * func.coalesce(BuildStep.size_factor, 1)).label("weighted_seconds"),
        ).join(BuildStep, BuildStep.build_id == Build.id).filter(
            and_(
                Build.completed_on >= period_start,
                Build.completed_on < period_end_excl,
                BuildStep.duration_seconds.isnot(None),
            )
        )
        if repository_id:
            step_rows = step_rows.filter(Build.repository_id == repository_id)
        step_rows = step_rows.group_by(Build.repository_id).all()
        step_map = {rid: (ws or 0.0) for rid, ws in step_rows}

        # Fallback pipeline-level aggregation within window
        pipe_rows = self.db.query(
            Build.repository_id,
            func.sum(Build.duration_seconds).label("total_seconds"),
        ).filter(
            and_(
                Build.completed_on >= period_start,
                Build.completed_on < period_end_excl,
                Build.duration_seconds.isnot(None),
            )
        )
        if repository_id:
            pipe_rows = pipe_rows.filter(Build.repository_id == repository_id)
        pipe_rows = pipe_rows.group_by(Build.repository_id).all()
        pipe_map = {rid: (ts or 0.0) for rid, ts in pipe_rows}

        def _minutes_for_repo(rid: int) -> float:
            secs = step_map.get(rid, 0.0)
            if secs <= 0.0:
                secs = pipe_map.get(rid, 0.0)
            return float(secs) / 60.0

        repo_ids = set(pipe_map.keys()) | set(step_map.keys())
        by_repo = {rid: _minutes_for_repo(rid) for rid in repo_ids}
        total = sum(by_repo.values())

        return {
            "total_minutes": float(total),
            "by_repo": by_repo,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat()
        }

    def calculate_deployment_frequency_by_environment(self, repository_id: int, days: int = 30) -> Dict:
        """Deployments per environment for a repository in the last N days"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.db.query(
            Deployment.environment,
            func.count(Deployment.id).label("count")
        ).filter(
            Deployment.repository_id == repository_id,
            Deployment.deployed_at >= cutoff_date
        ).group_by(Deployment.environment).all()
        return {env: int(cnt) for env, cnt in rows}
    
    def get_slow_pipelines(self, repository_id: Optional[int] = None, percentile: float = 90) -> List[Dict]:
        """Identify slow pipelines (above P90 threshold) with baseline context"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
        
        query = self.db.query(Build).filter(
            and_(
                Build.state == "SUCCESSFUL",
                Build.completed_on >= cutoff_date,
                Build.duration_seconds.isnot(None)
            )
        )
        
        if repository_id:
            query = query.filter(Build.repository_id == repository_id)
        
        builds = query.all()
        
        if not builds:
            return []
        
        durations = [b.duration_seconds for b in builds]
        baseline_median = float(np.median(durations))
        baseline_p90 = float(np.percentile(durations, percentile))
        
        slow_builds = [b for b in builds if b.duration_seconds > baseline_p90]
        
        return [
            {
                "build_id": b.id,
                "repository_id": b.repository_id,
                "duration_seconds": b.duration_seconds,
                "baseline_median": baseline_median,
                "baseline_p90": baseline_p90,
                "delta_vs_median_pct": ((b.duration_seconds - baseline_median) / baseline_median) * 100 if baseline_median else None,
                "commit_hash": b.commit_hash,
                "completed_at": b.completed_on.isoformat() if b.completed_on else None
            }
            for b in sorted(slow_builds, key=lambda x: x.duration_seconds, reverse=True)[:20]  # Limit to top 20
        ]

    def get_dev_deploy_slowdown(self, repository_id: int, days: int = 14, percentile: float = 90) -> Optional[Dict]:
        """
        Trunk-based dev deploy heuristic: successful builds on branch 'main' in last N days.
        Returns latest build vs baseline (median/p90) and vs previous successful build.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        builds = self.db.query(Build).filter(
            and_(
                Build.repository_id == repository_id,
                Build.state == "SUCCESSFUL",
                Build.branch == "main",
                Build.completed_on >= cutoff_date,
                Build.duration_seconds.isnot(None)
            )
        ).order_by(Build.completed_on.desc()).limit(60).all()

        if len(builds) < 5:
            return None

        durations = [b.duration_seconds for b in builds]
        baseline_median = float(np.median(durations))
        baseline_p90 = float(np.percentile(durations, percentile))

        latest = builds[0]
        prev = builds[1] if len(builds) > 1 else None

        prev_completed_at = None
        if prev and prev.completed_on:
            prev_completed_at = prev.completed_on.isoformat()

        return {
            "latest": {
                "build_id": latest.id,
                "build_number": latest.build_number,
                "duration_seconds": latest.duration_seconds,
                "commit_hash": latest.commit_hash,
                "completed_at": latest.completed_on.isoformat() if latest.completed_on else None
            },
            "previous": {
                "build_id": prev.id,
                "build_number": prev.build_number,
                "duration_seconds": prev.duration_seconds,
                "commit_hash": prev.commit_hash,
                "completed_at": prev_completed_at
            } if prev else None,
            "baseline": {
                "window_days": days,
                "median_seconds": baseline_median,
                "p90_seconds": baseline_p90
            },
            "delta": {
                "latest_vs_median_pct": ((latest.duration_seconds - baseline_median) / baseline_median) * 100 if baseline_median else None,
                "latest_vs_prev_pct": ((latest.duration_seconds - prev.duration_seconds) / prev.duration_seconds) * 100 if prev and prev.duration_seconds else None,
                "is_slow": True if latest.duration_seconds > baseline_p90 else False
            }
        }

