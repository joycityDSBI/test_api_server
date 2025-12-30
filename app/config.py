from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    debug: bool = False
    secret_key: str = "default-secret"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()