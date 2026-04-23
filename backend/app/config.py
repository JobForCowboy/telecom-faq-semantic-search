from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
    )

    app_name: str = "Telecom FAQ Semantic Search API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str
    frontend_origin: str = "http://localhost:3000"

    embedding_backend: str = "transformers"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 768
    similarity_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    clarification_score_gap: float = Field(default=0.04, ge=0.0, le=1.0)
    clarification_min_score: float = Field(default=0.58, ge=0.0, le=1.0)
    follow_up_short_message_max_chars: int = Field(default=24, ge=1, le=500)
    conversation_max_messages: int = Field(default=6, ge=2, le=20)
    clarification_enabled: bool = True
    fallback_message: str = (
        "Точный ответ не найден. Мы передали запрос оператору поддержки."
    )
    seed_faq_path: str = "../data/kb/faqs.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
