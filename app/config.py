from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Cron defaults (se pueden sobreescribir desde UI)
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
