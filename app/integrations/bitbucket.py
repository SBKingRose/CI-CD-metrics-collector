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
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Log the error details for debugging
            error_detail = ""
            try:
                error_detail = response.json()
            except:
                error_detail = response.text[:500]  # First 500 chars of error
            print(f"[_get] HTTP Error for {endpoint}: {e}")
            print(f"[_get] Response: {error_detail}")
            raise
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
    
    def get_pipelines(self, repo_slug: str, limit: int = 50, state_filter: Optional[str] = None) -> List[Dict]:
        """Get recent pipelines for a repository with pagination support
        
        Args:
            repo_slug: Repository slug
            limit: Maximum number of pipelines to return
            state_filter: Optional state filter query (e.g., 'state.name="COMPLETED" AND state.result.name="SUCCESSFUL"')
                         Can use query format: 'state="FAILED" OR state="ERROR"'
        """
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/"
        params = {"pagelen": min(limit, 50), "sort": "-created_on"}  # Bitbucket max pagelen is usually 100
        if state_filter:
            params["q"] = state_filter
        
        pipelines = []
        try:
            while len(pipelines) < limit:
                data = self._get(endpoint, params)
                page_pipelines = data.get("values", [])
                pipelines.extend(page_pipelines)
                
                # Stop if no more pages or we have enough
                if "next" not in data or len(pipelines) >= limit:
                    break
                
                # Follow pagination
                next_url = data["next"]
                endpoint = next_url.replace(self.base_url + "/", "")
                params = {}  # Params are in the URL already
            
            return pipelines[:limit]
        except Exception as e:
            print(f"[get_pipelines] Error fetching pipelines for {repo_slug}: {e}")
            return []
    
    def get_pipeline_steps(self, repo_slug: str, pipeline_uuid: str) -> List[Dict]:
        """Get steps for a specific pipeline"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/{pipeline_uuid}/steps/"
        return self._get(endpoint).get("values", [])

    def get_pipeline_step_log(self, repo_slug: str, pipeline_uuid: str, step_uuid: str) -> str:
        """
        Get text logs for a pipeline step.
        Endpoint pattern in Bitbucket Cloud requires URL-encoding braces:
        /repositories/{workspace}/{repo_slug}/pipelines/%7B{pipeline_uuid}%7D/steps/%7B{step_uuid}%7D/log
        """
        # Remove braces if present, then URL-encode them
        pu = pipeline_uuid.strip('{}')
        su = step_uuid.strip('{}')
        # URL-encode braces: { -> %7B, } -> %7D
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pipelines/%7B{pu}%7D/steps/%7B{su}%7D/log"
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
    
    def get_all_deployments(self, repo_slug: str, limit: int = 100) -> List[Dict]:
        """Get all deployments for a repository (not just latest per env) - paginates through all pages"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/deployments/"
        params = {"pagelen": 50}  # Don't use sort parameter - it may not be supported for deployments
        deployments = []
        
        try:
            while True:
                data = self._get(endpoint, params)
                page_deployments = data.get("values", [])
                
                for dep in page_deployments:
                    env = dep.get("environment", {})
                    deployments.append({
                        "environment": env.get("name", ""),
                        "deployment": dep
                    })
                
                # Stop if we've reached the limit or no more pages
                if len(deployments) >= limit or "next" not in data:
                    break
                
                # Follow pagination
                next_url = data["next"]
                # Extract endpoint from full URL
                endpoint = next_url.replace(self.base_url + "/", "")
                params = {}  # Params are in the URL already
                
            return deployments[:limit]  # Return up to limit
        except Exception as e:
            print(f"[get_all_deployments] Error fetching deployments for {repo_slug}: {e}")
            import traceback
            print(f"[get_all_deployments] Traceback: {traceback.format_exc()}")
            return []
    
    def get_downloads(self, repo_slug: str) -> List[Dict]:
        """Get list of downloadable artifacts/files for a repository"""
        endpoint = f"repositories/{self.workspace}/{repo_slug}/downloads"
        params = {"pagelen": 100, "sort": "-created_on"}
        try:
            data = self._get(endpoint, params)
            return data.get("values", [])
        except:
            return []
    
    def download_file(self, repo_slug: str, filename: str) -> Optional[Dict]:
        """Download a specific file from repository downloads"""
        downloads = self.get_downloads(repo_slug)
        for dl in downloads:
            if dl.get("name") == filename:
                # Return the download metadata; actual file content would need direct URL access
                return dl
        return None

