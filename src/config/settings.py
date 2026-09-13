from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # System Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # LLM Gateway
    LLM_BASE_URL: str = "https://api.agentrouter.org/v1"
    LLM_API_KEY: str = "dummy_key_for_dev"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./hermes_research.db"

    # Vector Database
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "hermes_literature"

    # Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio_hermes_admin"
    MINIO_SECRET_KEY: str = "minio_hermes_secret_2026"
    MINIO_BUCKET_PAPERS: str = "hermes-papers"
    MINIO_SECURE: bool = False

    # Task Queue & Cache
    REDIS_URL: str = "redis://localhost:6379/0"

    # Academic Parsing
    GROBID_URL: str = "http://localhost:8070"

    # Academic APIs
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None
    NCBI_EMAIL: str = "hermes.agent@example.com"
    NCBI_API_KEY: Optional[str] = None

    # Discord Bot
    DISCORD_BOT_TOKEN: str = "dummy_token"
    DISCORD_GUILD_ID: Optional[str] = None
    DISCORD_RESEARCHER_1_ID: Optional[str] = None
    DISCORD_RESEARCHER_2_ID: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()
