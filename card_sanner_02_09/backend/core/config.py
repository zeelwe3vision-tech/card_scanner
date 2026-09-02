from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ========================================================
    # SUPABASE
    # ========================================================

    supabase_url: str
    supabase_key: str
    supabase_secret_key: str

    # ========================================================
    # GEMINI
    # ========================================================

    gemini_api_key: str
    gemini_vlm_model: str = "gemini-3.5-flash-lite"

    # ========================================================
    # FRONTEND
    # ========================================================

    frontend_url: str = "http://localhost:3000"

    # ========================================================
    # AUTH
    # ========================================================

    jwt_secret: str

    # ========================================================
    # ENV CONFIG
    # ========================================================

    tavily_api_key: str | None = None
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()