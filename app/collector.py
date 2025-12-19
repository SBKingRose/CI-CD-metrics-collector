from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import Repository, Build, BuildStep, PullRequest, Deployment, BuildFailure
from app.integrations.bitbucket import BitbucketClient
from app.integrations.jira import JiraClient
from app.integrations.sonarqube import SonarQubeClient
from app.analytics.pattern_matcher import PatternMatcher
import re


class DataCollector:
    def __init__(self, db: Session = None):
        self.bitbucket = BitbucketClient()
        self.jira = JiraClient()
        self.sonarqube = SonarQubeClient()
        self.db = db or SessionLocal()
    
    def collect_repositories(self):
        """Collect and sync repository list"""
        repos = self.bitbucket.get_repositories()
        
        for repo_data in repos:
            repo = self.db.query(Repository).filter(
                Repository.slug == repo_data["slug"]
            ).first()
            
            if not repo:
                repo = Repository(
                    name=repo_data["name"],
                    slug=repo_data["slug"],
                    workspace=self.bitbucket.workspace
                )
                self.db.add(repo)
            else:
                repo.name = repo_data["name"]
        
        self.db.commit()
        return repos
    
    def collect_builds(self, repo_slug: str, limit: int = 50):
        """Collect builds for a repository"""
        repo = self.db.query(Repository).filter(Repository.slug == repo_slug).first()
        if not repo:
            return
        
        pipelines = self.bitbucket.get_pipelines(repo_slug, limit)
        
        for pipeline_data in pipelines:
            # Check if build already exists
            existing = self.db.query(Build).filter(
                Build.pipeline_uuid == pipeline_data["uuid"]
            ).first()
            
            if existing:
                continue
            
            # Parse dates
            started_on = None
            completed_on = None
            if pipeline_data.get("created_on"):
                started_on = datetime.fromisoformat(pipeline_data["created_on"].replace("Z", "+00:00"))
            if pipeline_data.get("completed_on"):
                completed_on = datetime.fromisoformat(pipeline_data["completed_on"].replace("Z", "+00:00"))
            
            # Calculate duration
            duration_seconds = None
            if started_on and completed_on:
                duration_seconds = (completed_on - started_on).total_seconds()
            
            # Bitbucket state structure:
            # state.name: COMPLETED / IN_PROGRESS / PAUSED ...
            # state.result.name: SUCCESSFUL / FAILED / STOPPED ...
            state_obj = pipeline_data.get("state", {}) or {}
            state_result = (state_obj.get("result") or {}).get("name")
            state_name = state_result or state_obj.get("name") or ""

            build = Build(
                repository_id=repo.id,
                build_number=pipeline_data.get("build_number", 0),
                pipeline_uuid=pipeline_data["uuid"],
                commit_hash=pipeline_data.get("target", {}).get("commit", {}).get("hash", ""),
                branch=pipeline_data.get("target", {}).get("ref_name", ""),
                state=str(state_name).upper(),
                duration_seconds=duration_seconds,
                started_on=started_on,
                completed_on=completed_on,
                trigger_name=pipeline_data.get("trigger", {}).get("name", "")
            )
            self.db.add(build)
            self.db.flush()
            
            # Collect steps
            try:
                steps_data = self.bitbucket.get_pipeline_steps(repo_slug, pipeline_data["uuid"])
                for step_data in steps_data:
                    step_started = None
                    step_completed = None
                    if step_data.get("started_on"):
                        step_started = datetime.fromisoformat(step_data["started_on"].replace("Z", "+00:00"))
                    if step_data.get("completed_on"):
                        step_completed = datetime.fromisoformat(step_data["completed_on"].replace("Z", "+00:00"))
                    
                    step_duration = None
                    if step_started and step_completed:
                        step_duration = (step_completed - step_started).total_seconds()
                    
                    step_state_obj = step_data.get("state", {}) or {}
                    step_state_result = (step_state_obj.get("result") or {}).get("name")
                    step_state_name = step_state_result or step_state_obj.get("name") or ""

                    step_uuid = step_data.get("uuid")
                    # step size is not consistently exposed; best-effort
                    size_factor = None
                    if isinstance(step_data.get("size"), int):
                        size_factor = step_data.get("size")
                    elif isinstance(step_data.get("size"), str):
                        m = re.search(r"(\d+)", step_data.get("size") or "")
                        if m:
                            size_factor = int(m.group(1))

                    step = BuildStep(
                        build_id=build.id,
                        step_uuid=str(step_uuid) if step_uuid else None,
                        step_name=step_data.get("name", ""),
                        step_type=step_data.get("type", ""),
                        duration_seconds=step_duration,
                        state=str(step_state_name).upper(),
                        started_on=step_started,
                        completed_on=step_completed,
                        size_factor=size_factor or 1
                    )
                    self.db.add(step)
                    
                    # If step failed, create failure record
                    if step.state == "FAILED":
                        error_msg = (step_data.get("error") or {}).get("message", "") or ""
                        log_excerpt = ""
                        try:
                            if step_uuid:
                                raw_log = self.bitbucket.get_pipeline_step_log(repo_slug, pipeline_data["uuid"], step_uuid)
                                # Keep last ~2000 chars to avoid huge DB writes
                                raw_log_tail = raw_log[-2000:] if raw_log else ""
                                # Extract lines that look like the failure summary
                                lines = [ln for ln in raw_log_tail.splitlines() if ln.strip()]
                                interesting = []
                                for ln in reversed(lines):
                                    if re.search(r"(error|exception|failed|fatal|traceback)", ln, re.IGNORECASE):
                                        interesting.append(ln.strip())
                                    if len(interesting) >= 8:
                                        break
                                interesting.reverse()
                                log_excerpt = "\n".join(interesting) or "\n".join(lines[-12:])  # fallback
                        except Exception:
                            log_excerpt = ""

                        # Store excerpt on the step for UI drilldown
                        if log_excerpt:
                            step.log_excerpt = log_excerpt[:4000]

                        # If API doesn't provide structured error message, fallback to log excerpt
                        if not error_msg and log_excerpt:
                            error_msg = log_excerpt[:1000]
                        
                        # Extract error signature hash for cross-repo matching
                        from app.analytics.error_analyzer import ErrorAnalyzer
                        analyzer = ErrorAnalyzer(self.db)
                        error_signature, signature_hash = analyzer.extract_error_signature(log_excerpt or error_msg)
                        
                        # Also use pattern matcher for backward compatibility
                        pattern_matcher = PatternMatcher(self.db)
                        pattern = pattern_matcher.normalize_error_message(error_msg)
                        
                        # Use signature hash as the primary pattern for cross-repo matching
                        failure_type = self._classify_failure(error_msg)
                        failure = BuildFailure(
                            build_id=build.id,
                            step_id=step.id,
                            error_message=error_msg,
                            error_pattern=signature_hash or pattern,  # Prefer signature hash for matching
                            failure_type=failure_type,
                            occurred_at=step_completed or datetime.now(timezone.utc)
                        )
                        self.db.add(failure)

                    # Best-effort: detect deployments from step metadata (if available)
                    # Some Bitbucket step objects include deployment_environment / deployment
                    dep_env = None
                    if isinstance(step_data.get("deployment_environment"), dict):
                        dep_env = step_data["deployment_environment"].get("name")
                    elif isinstance(step_data.get("deployment"), dict):
                        dep_env = step_data["deployment"].get("environment", {}).get("name") or step_data["deployment"].get("environment", {}).get("slug")

                    if dep_env and step.state == "SUCCESSFUL":
                        # avoid duplicates: keep only latest per repo/env by time
                        existing_dep = self.db.query(Deployment).filter(
                            Deployment.repository_id == repo.id,
                            Deployment.environment == dep_env,
                            Deployment.deployed_at == (step_completed or completed_on)
                        ).first()
                        if not existing_dep:
                            self.db.add(Deployment(
                                repository_id=repo.id,
                                environment=dep_env,
                                docker_image="",  # populated only if deployments API/log parsing added later
                                deployed_at=step_completed or completed_on,
                                build_id=build.id,
                                commit_hash=build.commit_hash
                            ))
            except Exception as e:
                print(f"Error collecting steps for pipeline {pipeline_data['uuid']}: {e}")
        
        self.db.commit()
    
    def collect_pull_requests(self, repo_slug: str, limit: int = 50):
        """Collect pull requests for a repository"""
        repo = self.db.query(Repository).filter(Repository.slug == repo_slug).first()
        if not repo:
            return
        
        prs = self.bitbucket.get_pull_requests(repo_slug, state="MERGED", limit=limit)
        
        for pr_data in prs:
            # PR id is unique only within a repository in our schema
            existing = self.db.query(PullRequest).filter(
                PullRequest.repository_id == repo.id,
                PullRequest.pr_id == pr_data["id"]
            ).first()
            
            if existing:
                continue
            
            created_at = None
            merged_at = None
            closed_at = None
            
            if pr_data.get("created_on"):
                created_at = datetime.fromisoformat(pr_data["created_on"].replace("Z", "+00:00"))
            # Use closed_on if available (more accurate for DORA velocity)
            if pr_data.get("closed_on"):
                closed_at = datetime.fromisoformat(pr_data["closed_on"].replace("Z", "+00:00"))
                merged_at = closed_at  # For merged PRs, closed_on is when it merged
            elif pr_data.get("updated_on"):
                merged_at = datetime.fromisoformat(pr_data["updated_on"].replace("Z", "+00:00"))
            
            pr = PullRequest(
                repository_id=repo.id,
                pr_id=pr_data["id"],
                title=pr_data.get("title", ""),
                state="MERGED",
                created_at=created_at,
                merged_at=merged_at,
                closed_at=closed_at,
                author=pr_data.get("author", {}).get("display_name", "")
            )
            self.db.add(pr)
        
        self.db.commit()
    
    def collect_deployments(self, repo_slug: str):
        """Collect deployment information - fetch ALL deployments with pagination"""
        repo = self.db.query(Repository).filter(Repository.slug == repo_slug).first()
        if not repo:
            print(f"[collect_deployments] Repository {repo_slug} not found in database")
            return
        
        # Get all deployments (paginate through all pages, up to 500)
        try:
            deployments_data = self.bitbucket.get_all_deployments(repo_slug, limit=500)
            print(f"[collect_deployments] Fetched {len(deployments_data)} deployments for {repo_slug}")
        except Exception as e:
            print(f"[collect_deployments] Error fetching deployments for {repo_slug}: {e}")
            return
        
        if not deployments_data:
            print(f"[collect_deployments] No deployments returned from API for {repo_slug}")
            return
        
        added_count = 0
        
        for dep_data in deployments_data:
            env_name = dep_data.get("environment", "")
            deployment = dep_data.get("deployment", {})
            
            if not deployment:
                continue
            
            deployed_at = None
            if deployment.get("created_on"):
                deployed_at = datetime.fromisoformat(deployment["created_on"].replace("Z", "+00:00"))
            
            # Extract docker image from deployment
            docker_image = deployment.get("release", {}).get("name", "") or deployment.get("environment", {}).get("name", "")
            
            commit_hash = deployment.get("release", {}).get("commit", {}).get("hash", "") or ""

            # Deduplicate by (repo, env, deployed_at, commit_hash)
            existing = self.db.query(Deployment).filter(
                Deployment.repository_id == repo.id,
                Deployment.environment == env_name,
                Deployment.deployed_at == deployed_at,
                Deployment.commit_hash == commit_hash,
            ).first()

            if not existing:
                # Best-effort: link to a build if we already have it
                build_id = None
                if commit_hash:
                    b = self.db.query(Build).filter(
                        Build.repository_id == repo.id,
                        Build.commit_hash == commit_hash
                    ).order_by(Build.completed_on.desc().nullslast()).first()
                    build_id = b.id if b else None

                dep = Deployment(
                    repository_id=repo.id,
                    environment=env_name,
                    docker_image=docker_image,
                    deployed_at=deployed_at,
                    build_id=build_id,
                    commit_hash=commit_hash
                )
                self.db.add(dep)
                added_count += 1
        
        self.db.commit()
        print(f"[collect_deployments] Added {added_count} new deployments for {repo_slug}")
    
    def _classify_failure(self, error_msg: str) -> str:
        """Classify failure type from error message"""
        if not error_msg:
            return "unknown"
        error_lower = error_msg.lower()
        if "timeout" in error_lower:
            return "timeout"
        elif "memory" in error_lower or "oom" in error_lower:
            return "memory_error"
        elif "test" in error_lower and "fail" in error_lower:
            return "test_failure"
        elif "compile" in error_lower or "syntax" in error_lower:
            return "compilation_error"
        elif "connection" in error_lower or "network" in error_lower:
            return "network_error"
        else:
            return "unknown"
    
    def collect_all(self):
        """Collect all data for all repositories"""
        repos = self.collect_repositories()
        
        for repo in repos:
            repo_slug = repo["slug"]
            print(f"Collecting data for {repo_slug}...")
            
            try:
                self.collect_builds(repo_slug)
                self.collect_pull_requests(repo_slug)
                self.collect_deployments(repo_slug)
            except Exception as e:
                print(f"Error collecting data for {repo_slug}: {e}")
                continue

