from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    datasources_file: str = "datasources.json"

    bitbucket_workspace: str = ""
    bitbucket_repo: str = ""
    bitbucket_branch: str = "main"
    bitbucket_user: str = ""
    bitbucket_app_password: str = ""

    llm_provider: str = "bedrock"  # bedrock | ollama

    aws_region: str = "eu-west-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    jira_email: str = ""
    jira_project_key: str = "PROJ"

    # Cron defaults
    cron_enabled: bool = False
    cron_interval_minutes: int = 60
    cron_hours: int = 24
    cron_size: int = 20
    cron_step_search: bool = True
    cron_step_analyze: bool = True
    cron_step_send: bool = False

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
