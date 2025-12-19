from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Bitbucket (uses Atlassian API token; same token can be reused for Jira)
    bitbucket_workspace: str
    bitbucket_username: Optional[str] = None  # Optional - will use jira_email if not provided
    bitbucket_api_token: Optional[str] = None  # Optional - will use jira_api_token if not provided
    
    # Jira (token can be the same as Bitbucket)
    jira_url: str
    jira_email: str
    jira_api_token: str
    
    # SonarQube
    sonarqube_url: str
    sonarqube_token: str
    
    # Database
    database_url: str = "sqlite:///./release_intelligence.db"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Collection
    collection_interval_minutes: int = 15
    
    # AI Configuration (optional - for enhanced suggestions)
    ai_provider: str = "huggingface"  # "openai", "huggingface", or "none"
    openai_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    use_ai_suggestions: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

