from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import Diagnostic, Repository, Build, BuildFailure
from app.analytics.regression_detector import RegressionDetector
from app.analytics.pattern_matcher import PatternMatcher
from app.analytics.metrics_calculator import MetricsCalculator
from app.ai.suggestion_generator import AISuggestionGenerator


class DiagnosticEngine:
    def __init__(self, db: Session):
        self.db = db
        self.regression_detector = RegressionDetector(db)
        self.pattern_matcher = PatternMatcher(db)
        self.metrics_calculator = MetricsCalculator(db)
        self.ai_generator = AISuggestionGenerator()
    
    def generate_diagnostics(self) -> List[Dict]:
        """Generate all diagnostics"""
        diagnostics = []
        
        repositories = self.db.query(Repository).all()
        
        for repo in repositories:
            # Build duration regression
            regression = self.regression_detector.detect_build_duration_regression(repo.id)
            if regression:
                diagnostics.append(self._create_regression_diagnostic(repo, regression))
            
            # Step regressions
            builds = self.db.query(Build).filter(Build.repository_id == repo.id).limit(100).all()
            step_names = set()
            for build in builds:
                for step in build.steps:
                    step_names.add(step.step_name)
            
            for step_name in step_names:
                step_regression = self.regression_detector.detect_step_regression(repo.id, step_name)
                if step_regression:
                    diagnostics.append(self._create_step_regression_diagnostic(repo, step_regression))
            
            # Resource waste
            waste_findings = self.regression_detector.detect_resource_waste(repo.id)
            for waste in waste_findings:
                diagnostics.append(self._create_resource_waste_diagnostic(repo, waste))
        
        # Cross-repo step regression detection
        all_step_names = set()
        for repo in repositories:
            builds = self.db.query(Build).filter(Build.repository_id == repo.id).limit(50).all()
            for build in builds:
                for step in build.steps:
                    all_step_names.add(step.step_name)
        
        for step_name in all_step_names:
            cross_repo_regression = self.regression_detector.detect_cross_repo_step_regression(step_name)
            if cross_repo_regression:
                diagnostics.append(self._create_cross_repo_step_regression_diagnostic(cross_repo_regression))
        
        # Pattern matching diagnostics
        recent_failures = self.db.query(Build).filter(
            Build.state == "FAILED"
        ).order_by(Build.completed_on.desc()).limit(20).all()
        
        for build in recent_failures:
            if build.steps:
                failed_step = next((s for s in build.steps if s.state == "FAILED"), None)
                if failed_step:
                    failures = self.db.query(BuildFailure).filter(
                        BuildFailure.step_id == failed_step.id
                    ).first()
                    
                    if failures:
                        matches = self.pattern_matcher.find_matching_failures(failures.error_message)
                        if len(matches) > 1:  # More than just this failure
                            # Count unique repos in matches
                            repo_ids = set()
                            for match in matches:
                                if match.get("repository_id"):
                                    repo_ids.add(match["repository_id"])
                            
                            diagnostics.append(self._create_pattern_match_diagnostic(
                                build.repository, failures, matches, len(repo_ids)
                            ))
        
        return diagnostics
    
    def _create_regression_diagnostic(self, repo: Repository, regression: Dict) -> Dict:
        """Create diagnostic for build duration regression"""
        title = f"Build duration regressed {regression['regression_percent']:.1f}% in {repo.name}"
        base_message = (
            f"Repo {repo.name} is slow because builds regressed {regression['regression_percent']:.1f}% "
            f"(from {regression['baseline_median']:.1f}s to {regression['recent_median']:.1f}s median). "
            f"This regression occurred after commit {regression['commit_hash'][:8]}."
        )
        
        diagnostic = {
            "repository_id": repo.id,
            "type": "regression",
            "severity": "high" if regression['regression_percent'] > 50 else "medium",
            "title": title,
            "message": base_message,
            "metadata": regression
        }
        
        # Enhance with AI suggestion
        enhanced_message = self.ai_generator.enhance_diagnostic(diagnostic)
        diagnostic["message"] = enhanced_message
        
        return diagnostic
    
    def _create_step_regression_diagnostic(self, repo: Repository, regression: Dict) -> Dict:
        """Create diagnostic for step regression"""
        title = f"Step '{regression['step_name']}' regressed {regression['regression_percent']:.1f}% in {repo.name}"
        base_message = (
            f"Step '{regression['step_name']}' in {repo.name} regressed {regression['regression_percent']:.1f}% "
            f"after commit {regression['commit_hash'][:8]}."
        )
        
        diagnostic = {
            "repository_id": repo.id,
            "type": "step_regression",
            "severity": "high" if regression['regression_percent'] > 50 else "medium",
            "title": title,
            "message": base_message,
            "metadata": regression
        }
        
        enhanced_message = self.ai_generator.enhance_diagnostic(diagnostic)
        diagnostic["message"] = enhanced_message
        
        return diagnostic
    
    def _create_resource_waste_diagnostic(self, repo: Repository, waste: Dict) -> Dict:
        """Create diagnostic for resource waste"""
        if waste.get("type") == "memory_waste":
            title = f"Memory limit {waste['waste_ratio']:.1f}× higher than peak usage in {repo.name}"
            base_message = (
                f"Step '{waste['step_name']}' in {repo.name} has memory limit {waste['waste_ratio']:.1f}× "
                f"higher than peak usage ({waste['avg_limit_mb']:.0f}MB limit vs {waste['avg_peak_mb']:.0f}MB peak). "
                f"Reduce to {waste['recommended_limit_mb']}MB to save build minutes."
            )
        else:  # time_waste
            title = f"Timeout {waste['waste_ratio']:.1f}× higher than actual duration in {repo.name}"
            base_message = (
                f"Step '{waste['step_name']}' in {repo.name} has timeout {waste['waste_ratio']:.1f}× "
                f"higher than actual duration ({waste['avg_max_time_seconds']:.0f}s timeout vs {waste['avg_duration_seconds']:.0f}s actual). "
                f"Reduce timeout to {waste['recommended_max_time_seconds']}s to save build minutes."
            )
        
        diagnostic = {
            "repository_id": repo.id,
            "type": "resource_waste",
            "severity": "low",
            "title": title,
            "message": base_message,
            "metadata": waste
        }
        
        enhanced_message = self.ai_generator.enhance_diagnostic(diagnostic)
        diagnostic["message"] = enhanced_message
        
        return diagnostic
    
    def _create_cross_repo_step_regression_diagnostic(self, regression: Dict) -> Dict:
        """Create diagnostic for cross-repo step regression"""
        repo_names = [r["repository_name"] for r in regression["regressed_repos"]]
        title = f"Step '{regression['step_name']}' regressed across {regression['repo_count']} repositories"
        message = (
            f"Step '{regression['step_name']}' has regressed an average of {regression['avg_regression_percent']:.1f}% "
            f"across {regression['repo_count']} repositories: {', '.join(repo_names[:3])}"
            f"{' and more' if len(repo_names) > 3 else ''}."
        )
        
        return {
            "repository_id": None,  # Cross-repo, no single repo
            "type": "cross_repo_step_regression",
            "severity": "high",
            "title": title,
            "message": message,
            "metadata": regression
        }
    
    def _create_pattern_match_diagnostic(self, repo: Repository, failure, matches: List[Dict], repo_count: int) -> Dict:
        """Create diagnostic for failure pattern match"""
        title = f"Failure pattern matches {len(matches)} other occurrences"
        if repo_count > 1:
            message = (
                f"This failure in {repo.name} matches a known pattern seen in {len(matches)} other builds "
                f"across {repo_count} repositories. Error: {failure.error_message[:200]}"
            )
        else:
            message = (
                f"This failure in {repo.name} matches a known pattern seen in {len(matches)} other builds. "
                f"Error: {failure.error_message[:200]}"
            )
        
        return {
            "repository_id": repo.id,
            "type": "pattern_match",
            "severity": "medium",
            "title": title,
            "message": message,
            "metadata": {
                "failure_id": failure.id,
                "matches": matches,
                "repo_count": repo_count
            }
        }
    
    def save_diagnostics(self, diagnostics: List[Dict]):
        """Save diagnostics to database"""
        for diag in diagnostics:
            existing = self.db.query(Diagnostic).filter(
                and_(
                    Diagnostic.repository_id == diag.get("repository_id"),
                    Diagnostic.diagnostic_type == diag["type"],
                    Diagnostic.title == diag["title"]
                )
            ).first()
            
            if not existing:
                diagnostic = Diagnostic(
                    repository_id=diag.get("repository_id"),
                    diagnostic_type=diag["type"],
                    severity=diag["severity"],
                    title=diag["title"],
                    message=diag["message"],
                    diagnostic_metadata=diag.get("metadata", {})
                )
                self.db.add(diagnostic)
        
        self.db.commit()

