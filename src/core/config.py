from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Scraping
    SCRAPING_BASE_URL: str = "https://help.zipboard.co"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_config() -> Settings:
    return Settings()

env_settings = get_config()
