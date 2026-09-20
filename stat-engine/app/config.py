"""
Application configuration via environment variables.

Reads from .env file in the stat-engine directory, or from system environment.
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # Server & Security
    host: str = "127.0.0.1"
    port: int = 8000
    internal_api_secret: str = "stat-engine-internal-secret-dev"

    # CORS — restrict to the Next.js frontend origin
    allowed_origins: list[str] = ["http://localhost:3000"]

    # File uploads
    max_file_size_mb: int = 50
    upload_dir: str = str(Path(__file__).resolve().parent.parent / "uploads")

    # Application
    app_version: str = "0.1.0"

    @property
    def async_database_url(self) -> str:
        """Return a database URL compatible with asyncpg driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        
        # Convert sslmode= to ssl= for asyncpg compatibility if present
        if "sslmode=" in url:
            url = url.replace("sslmode=", "ssl=")
        return url

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
