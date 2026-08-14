from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    max_files: int = 5000
    analysis_timeout_seconds: int = 300

    ai_max_explain_files: int = 10
    ai_max_test_files: int = 3
    ai_max_modernize_files: int = 3
    llm_timeout_seconds: int = 25
    llm_max_concurrency: int = 3

    github_api_base: str = "https://api.github.com"
    github_token: str = ""

    _PLACEHOLDER_KEYS = frozenset({
        "",
        "your-api-key-here",
        "changeme",
        "replace-me",
        "sk-your-key-here",
    })

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        key = self.llm_api_key.strip()
        if key.lower() in self._PLACEHOLDER_KEYS:
            return False
        return bool(key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
