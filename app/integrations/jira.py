import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.config import settings


class JiraClient:
    def __init__(self):
        self.base_url = settings.jira_url.rstrip("/")
        self.email = settings.jira_email
        self.api_token = settings.jira_api_token
        self.auth = (self.email, self.api_token)
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/rest/api/3/{endpoint}"
        headers = {"Accept": "application/json"}
        response = requests.get(url, auth=self.auth, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_issues(self, jql: str, limit: int = 50) -> List[Dict]:
        """Get issues using JQL query"""
        params = {"jql": jql, "maxResults": limit, "fields": "summary,status,created,resolutiondate,assignee"}
        return self._get("search", params).get("issues", [])
    
    def get_prs_linked_to_issues(self, repo_name: Optional[str] = None) -> List[Dict]:
        """Get pull requests linked to Jira issues"""
        jql = 'issueType = "Pull Request" OR issueType = "PR"'
        if repo_name:
            jql += f' AND summary ~ "{repo_name}"'
        return self.get_issues(jql)
    
    def get_recent_issues(self, days: int = 30) -> List[Dict]:
        """Get recent issues"""
        jql = f'created >= -{days}d ORDER BY created DESC'
        return self.get_issues(jql)

