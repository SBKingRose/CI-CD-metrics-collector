from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import BuildFailure
import re


class PatternMatcher:
    def __init__(self, db: Session):
        self.db = db
    
    def normalize_error_message(self, error_msg: str) -> str:
        """Normalize error message to create a pattern"""
        if not error_msg:
            return ""
        
        # Remove file paths, line numbers, timestamps
        normalized = error_msg.lower()
        normalized = re.sub(r'/[^\s]+', '[PATH]', normalized)
        normalized = re.sub(r'\d+:\d+', '[LINE]', normalized)
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}', '[TIMESTAMP]', normalized)
        normalized = re.sub(r'0x[0-9a-f]+', '[HEX]', normalized)
        
        # Extract key error phrases
        error_patterns = [
            r'timeout',
            r'out of memory',
            r'connection refused',
            r'permission denied',
            r'not found',
            r'failed to',
            r'error:',
            r'exception:',
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, normalized):
                return pattern
        
        # Return first 100 chars as pattern
        return normalized[:100]
    
    def find_matching_failures(self, error_message: str, repository_id: int = None) -> List[Dict]:
        """Find other failures matching the same pattern"""
        pattern = self.normalize_error_message(error_message)
        
        if not pattern:
            return []
        
        query = self.db.query(BuildFailure).filter(
            BuildFailure.error_pattern == pattern
        )
        
        if repository_id:
            query = query.join(BuildFailure.build).filter(
                BuildFailure.build.has(repository_id=repository_id)
            )
        
        matching_failures = query.limit(10).all()
        
        return [
            {
                "build_id": f.build_id,
                "repository_id": f.build.repository_id if f.build else None,
                "error_message": f.error_message[:200],
                "occurred_at": f.occurred_at.isoformat() if f.occurred_at else None
            }
            for f in matching_failures
        ]
    
    def _classify_failure(self, error_msg: str) -> str:
        """Classify failure type from error message"""
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
    
    def get_common_failure_patterns(self, limit: int = 10) -> List[Dict]:
        """Get most common failure patterns across all repositories"""
        patterns = self.db.query(
            BuildFailure.error_pattern,
            func.count(BuildFailure.id).label('count')
        ).filter(
            BuildFailure.error_pattern.isnot(None)
        ).group_by(
            BuildFailure.error_pattern
        ).order_by(
            func.count(BuildFailure.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "pattern": p.error_pattern,
                "count": p.count
            }
            for p in patterns
        ]

