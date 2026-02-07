from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Scraping
    SCRAPING_BASE_URL: str = "https://help.zipboard.co"
    # LLM
    GROQ_API_KEY: str
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    MAX_CONCURRENT_LLM_CALLS: int = 2
    # Google Sheets
    GOOGLE_CREDS_JSON: str
    SHEET_ID: str
    # API
    AUTH_TOKEN: str  # auth token to access this API

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_config() -> Settings:
    return Settings()  # type: ignore


env_settings = get_config()
