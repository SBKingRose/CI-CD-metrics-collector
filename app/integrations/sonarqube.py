import requests
from typing import List, Dict, Optional
from app.config import settings


class SonarQubeClient:
    def __init__(self):
        self.base_url = settings.sonarqube_url.rstrip("/")
        self.token = settings.sonarqube_token
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/api/{endpoint}"
        auth = (self.token, "")
        response = requests.get(url, auth=auth, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_projects(self) -> List[Dict]:
        """Get all projects"""
        return self._get("projects/search").get("components", [])
    
    def get_project_measures(self, project_key: str, metrics: List[str]) -> Dict:
        """Get measures for a project"""
        params = {
            "component": project_key,
            "metricKeys": ",".join(metrics)
        }
        return self._get("measures/component", params)
    
    def get_code_quality_metrics(self, project_key: str) -> Dict:
        """Get code quality metrics for a project"""
        metrics = [
            "bugs", "vulnerabilities", "code_smells",
            "coverage", "duplicated_lines_density",
            "ncloc", "complexity"
        ]
        return self.get_project_measures(project_key, metrics)

