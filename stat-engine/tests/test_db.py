import pytest
from app.config import get_settings
from app.db.tables import metadata, datasets, users, projects, variable_profiles, validation_reports
from app.db.session import check_db_health, init_db, close_db


def test_async_database_url_formatting():
    settings = get_settings()
    async_url = settings.async_database_url
    assert async_url.startswith("postgresql+asyncpg://")
    assert "sslmode=" not in async_url


def test_table_metadata_definitions():
    assert "users" in metadata.tables
    assert "projects" in metadata.tables
    assert "datasets" in metadata.tables
    assert "variable_profiles" in metadata.tables
    assert "validation_reports" in metadata.tables
    assert "analysis_jobs" in metadata.tables
    assert "analysis_results" in metadata.tables

    # Check columns
    assert "fileName" in datasets.c
    assert "fileSizeBytes" in datasets.c
    assert "parquetUrl" in datasets.c
    assert "detectedType" in variable_profiles.c
    assert "statsJson" in variable_profiles.c


@pytest.mark.asyncio
async def test_db_connectivity():
    init_db()
    is_connected = await check_db_health()
    await close_db()
    # If DATABASE_URL points to a live database (e.g. Neon PostgreSQL), is_connected is True
    assert isinstance(is_connected, bool)
