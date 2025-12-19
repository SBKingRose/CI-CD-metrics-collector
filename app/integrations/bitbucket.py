import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.config import settings


class BitbucketClient:
    def __init__(self):
        self.workspace = settings.bitbucket_workspace
        # Bitbucket Cloud API uses basic auth: username:token
        # Use email/username if provided, otherwise use token as username
        self.username = settings.bitbucket_username or settings.jira_email or "x-token-auth"
        # Reuse Jira token if a dedicated Bitbucket token is not provided
        self.api_token = settings.bitbucket_api_token or settings.jira_api_token
        self.base_url = "https://api.bitbucket.org/2.0"
        # Bitbucket Cloud uses basic auth with username:token
        self.auth = (self.username, self.api_token)
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, auth=self.auth, params=params)
        response.raise_for_status()
        return response.json()

    def _get_text(self, endpoint: str, params: Optional[Dict] = None) -> str:
        url = f"{self.base_url}/{endpoint}"
        headers = {"Accept": "text/plain"}
        # Bitbucket may redirect log endpoints; requests follows redirects by default
        response = requests.get(url, auth=self.auth, params=params, headers=headers, allow_redirects=True)
        response.raise_for_status()
        return response.text or ""
    
    def get_repositories(self) -> List[Dict]:
        """Get all repositories in the workspace"""
        repos = []
        url = f"repositories/{self.workspace}"
        params = {"pagelen": 100}
        
        while True:
            data = self._get(url, params)
            repos.extend(data.get("values", []))
            if "next" not in data:
                break
            url = data["next"].replace(self.base_url + "/", "")
        
        return repos
    
    def get_pipelines(self, repo_slug: str, limit: int = 50) -> List[Dict]:
        """Get recent pipelines for a repository"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/"
        params = {"pagelen": limit, "sort": "-created_on"}
        return self._get(endpoint, params).get("values", [])
    
    def get_pipeline_steps(self, repo_slug: str, pipeline_uuid: str) -> List[Dict]:
        """Get steps for a specific pipeline"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/{pipeline_uuid}/steps/"
        return self._get(endpoint).get("values", [])

    def get_pipeline_step_log(self, repo_slug: str, pipeline_uuid: str, step_uuid: str) -> str:
        """
        Get text logs for a pipeline step.
        Endpoint pattern in Bitbucket Cloud is typically:
        /repositories/{workspace}/{repo_slug}/pipelines/{pipeline_uuid}/steps/{step_uuid}/log
        """
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/{pipeline_uuid}/steps/{step_uuid}/log"
        return self._get_text(endpoint)
    
    def get_pull_requests(self, repo_slug: str, state: str = "MERGED", limit: int = 50) -> List[Dict]:
        """Get pull requests for a repository"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pullrequests"
        params = {"state": state, "pagelen": limit, "sort": "-created_on"}
        return self._get(endpoint, params).get("values", [])
    
    def get_commits(self, repo_slug: str, branch: str = "main", limit: int = 50) -> List[Dict]:
        """Get commits for a repository"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/commits/{branch}"
        params = {"pagelen": limit}
        return self._get(endpoint, params).get("values", [])
    
    def get_deployments(self, repo_slug: str) -> List[Dict]:
        """Get deployment environments and their latest deployments"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/environments/"
        try:
            data = self._get(endpoint)
            environments = data.get("values", [])
            deployments = []
            
            for env in environments:
                env_uuid = env.get("uuid")
                if env_uuid:
                    deployments_endpoint = f"repositories/{self.workspace}/{repo_slug}/deployments/"
                    params = {"environment.uuid": env_uuid, "pagelen": 1, "sort": "-created_on"}
                    try:
                        deployment_data = self._get(deployments_endpoint, params)
                        if deployment_data.get("values"):
                            deployments.append({
                                "environment": env.get("name"),
                                "deployment": deployment_data["values"][0]
                            })
                    except:
                        pass
            
            return deployments
        except:
            return []

