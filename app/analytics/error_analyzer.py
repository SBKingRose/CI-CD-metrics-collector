"""
Error analysis and cross-repo pattern matching.
Extracts error signatures from logs and matches them across repositories.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models import Build, BuildStep, BuildFailure, Repository
from app.fixes_lookup import match_known_fixes


class ErrorAnalyzer:
    def __init__(self, db: Session):
        self.db = db
    
    def extract_error_signature(self, log_text: str) -> Tuple[str, str]:
        """
        Extract error signature from log text.
        Returns (signature_text, signature_hash)
        """
        if not log_text:
            return "", ""
        
        # Get last 10 lines containing error keywords
        lines = log_text.splitlines()
        interesting = [
            l.strip()
            for l in lines
            if any(k in l.lower() for k in ["error", "exception", "traceback", "failed", "fatal"])
        ]
        
        # Take last 10 interesting lines
        interesting = interesting[-10:] if len(interesting) > 10 else interesting
        
        # Normalize: lowercase, remove timestamps, trim whitespace
        normalized = []
        for line in interesting:
            # Remove common timestamp patterns
            line = re.sub(r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}', '', line)
            line = re.sub(r'\[\d{4}-\d{2}-\d{2}.*?\]', '', line)
            line = line.strip().lower()
            if line:
                normalized.append(line)
        
        signature_text = "\n".join(normalized)
        signature_hash = hashlib.sha1(signature_text.encode("utf-8")).hexdigest()
        
        return signature_text, signature_hash
    
    def get_latest_failed_pipeline(self, repo_slug: str) -> Optional[Dict]:
        """
        Get the latest failed/error pipeline for a repository.
        Returns pipeline data if failed, None if latest is successful.
        """
        from app.integrations.bitbucket import BitbucketClient
        bitbucket = BitbucketClient()
        
        try:
            # Get latest pipeline
            pipelines = bitbucket.get_pipelines(repo_slug, limit=1)
            if not pipelines:
                return None
            
            pipeline = pipelines[0]
            state = pipeline.get("state", {})
            result = (state.get("result") or {}).get("name")
            
            if result in ("FAILED", "ERROR"):
                return pipeline
            return None
        except Exception as e:
            print(f"[get_latest_failed_pipeline] Error for {repo_slug}: {e}")
            return None
    
    def get_failed_step_logs(self, repo_slug: str, pipeline_uuid: str) -> List[Dict]:
        """
        Get logs for failed steps in a pipeline.
        Returns list of {step_name, step_uuid, log_text, error_signature, signature_hash}
        """
        from app.integrations.bitbucket import BitbucketClient
        bitbucket = BitbucketClient()
        
        failed_steps_data = []
        
        try:
            # Get all steps for the pipeline
            steps = bitbucket.get_pipeline_steps(repo_slug, pipeline_uuid)
            
            for step in steps:
                step_state = step.get("state", {})
                step_state_name = step_state.get("name", "")
                
                if step_state_name in ("FAILED", "ERROR"):
                    step_uuid = step.get("uuid", "")
                    step_name = step.get("name", "")
                    
                    # Get log for this step
                    log_text = ""
                    try:
                        if step_uuid:
                            log_text = bitbucket.get_pipeline_step_log(repo_slug, pipeline_uuid, step_uuid)
                    except Exception as e:
                        print(f"[get_failed_step_logs] Error getting log for step {step_uuid}: {e}")
                    
                    # Extract error signature
                    signature_text, signature_hash = self.extract_error_signature(log_text)
                    
                    # Match known fixes
                    fixes = match_known_fixes(log_text)
                    
                    failed_steps_data.append({
                        "step_name": step_name,
                        "step_uuid": step_uuid,
                        "log_text": log_text,
                        "error_signature": signature_text,
                        "signature_hash": signature_hash,
                        "known_fixes": fixes
                    })
            
            return failed_steps_data
        except Exception as e:
            print(f"[get_failed_step_logs] Error for pipeline {pipeline_uuid}: {e}")
            return []
    
    def find_other_repos_with_error(self, current_repo_id: int, signature_hash: str) -> List[Dict]:
        """
        Find other repositories that have seen the same error signature.
        Returns list of {repository_slug, repository_name, build_number, occurred_at}
        """
        if not signature_hash:
            return []
        
        # Find BuildFailures with matching signature_hash
        failures = self.db.query(BuildFailure).join(
            Build, Build.id == BuildFailure.build_id
        ).filter(
            and_(
                Build.repository_id != current_repo_id,
                BuildFailure.error_pattern == signature_hash
            )
        ).order_by(BuildFailure.occurred_at.desc()).limit(10).all()
        
        repos_seen = {}
        for failure in failures:
            build = failure.build
            repo = build.repository
            
            if repo.slug not in repos_seen:
                repos_seen[repo.slug] = {
                    "repository_slug": repo.slug,
                    "repository_name": repo.name,
                    "build_number": build.build_number,
                    "occurred_at": failure.occurred_at.isoformat() if failure.occurred_at else None,
                    "error_message": failure.error_message[:200] if failure.error_message else None
                }
        
        return list(repos_seen.values())
    
    def analyze_latest_failure(self, repo_slug: str) -> Optional[Dict]:
        """
        Analyze the latest failed pipeline for a repository.
        Returns analysis with error details, cross-repo matches, and fix suggestions.
        """
        repo = self.db.query(Repository).filter(Repository.slug == repo_slug).first()
        if not repo:
            return None
        
        # Get latest failed pipeline
        pipeline = self.get_latest_failed_pipeline(repo_slug)
        if not pipeline:
            return {
                "status": "OK",
                "message": "Latest pipeline succeeded",
                "repository": repo_slug
            }
        
        pipeline_uuid = pipeline.get("uuid", "")
        if not pipeline_uuid:
            return {
                "status": "ERROR",
                "message": "Pipeline UUID not found",
                "repository": repo_slug
            }
        
        # Get failed steps and their logs
        failed_steps = self.get_failed_step_logs(repo_slug, pipeline_uuid)
        
        if not failed_steps:
            return {
                "status": "FAILED",
                "message": "No failed steps found, but pipeline is failed",
                "repository": repo_slug,
                "pipeline_uuid": pipeline_uuid
            }
        
        # Aggregate error signatures and fixes
        all_signatures = []
        all_fixes = []
        all_logs = []
        
        for step in failed_steps:
            if step["signature_hash"]:
                all_signatures.append(step["signature_hash"])
            all_fixes.extend(step["known_fixes"])
            all_logs.append(step["log_text"])
        
        # Use the first signature for cross-repo matching
        primary_signature_hash = failed_steps[0]["signature_hash"] if failed_steps else ""
        
        # Find other repos with same error
        other_repos = self.find_other_repos_with_error(repo.id, primary_signature_hash)
        
        # Deduplicate fixes
        seen_fix_patterns = set()
        unique_fixes = []
        for fix in all_fixes:
            if fix["pattern"] not in seen_fix_patterns:
                seen_fix_patterns.add(fix["pattern"])
                unique_fixes.append(fix)
        
        return {
            "status": "FAILED",
            "repository": repo_slug,
            "repository_name": repo.name,
            "pipeline_uuid": pipeline_uuid,
            "build_number": pipeline.get("build_number"),
            "commit_hash": pipeline.get("target", {}).get("commit", {}).get("hash", ""),
            "failed_steps": failed_steps,
            "error_signature": failed_steps[0]["error_signature"] if failed_steps else "",
            "signature_hash": primary_signature_hash,
            "known_fixes": unique_fixes,
            "other_repos_with_same_error": other_repos,
            "other_repos_count": len(other_repos),
            "created_at": pipeline.get("created_on"),
            "completed_at": pipeline.get("completed_on")
        }

