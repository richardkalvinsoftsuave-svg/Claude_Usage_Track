"""Application settings loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All environment-driven configuration."""

    model_config = ConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://root:password@localhost:3306/usage_db"
    upload_dir: Path = Path("./uploads")
    extraction_mode: str = "ocr_plus_manual_vlm"  # ocr_only | ocr_plus_manual_vlm | docling_only | docling_plus_manual_vlm | vlm_only
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:3b"
    max_file_size: int = 10 * 1024 * 1024  # 10 MB


settings = Settings()
