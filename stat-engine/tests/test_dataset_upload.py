"""
Integration tests for the Dataset Upload API (Sub-Phase 1.4).

Tests run against the live Neon PostgreSQL database and the real local
filesystem.  Test rows are created with unique CUIDs and hard-deleted in
teardown to prevent pollution.

Mirrors the fixture pattern established in ``test_dataset_repo.py``.
"""

import io
import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.tables import users, projects, datasets
from app.main import create_app
from app.utils.ids import generate_cuid

# All tests share a single event loop to coexist with module-scoped fixtures.
pytestmark = pytest.mark.asyncio(loop_scope="module")

# ── Module-level state ────────────────────────────────────────────────

_test_engine = None
_test_session_factory: async_sessionmaker[AsyncSession] | None = None
_settings = get_settings()
_internal_secret = _settings.internal_api_secret
_upload_dir = Path(_settings.upload_dir)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_user_id():
    return generate_cuid()


@pytest.fixture(scope="module")
def test_project_id():
    return generate_cuid()


@pytest.fixture(scope="module")
def other_user_id():
    return generate_cuid()


@pytest.fixture(scope="module")
def other_project_id():
    return generate_cuid()


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def setup_and_teardown(
    test_user_id, test_project_id, other_user_id, other_project_id
):
    """Initialize engine, create prerequisite rows, clean up after."""
    global _test_engine, _test_session_factory

    settings = get_settings()
    _test_engine = create_async_engine(
        settings.async_database_url,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
    )
    _test_session_factory = async_sessionmaker(
        bind=_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with _test_session_factory() as session:
        # Test user
        await session.execute(
            insert(users).values(
                id=test_user_id,
                name="Upload Test User",
                email=f"{test_user_id}@test.local",
                emailVerified=True,
                role="USER",
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Second user for authorization tests
        await session.execute(
            insert(users).values(
                id=other_user_id,
                name="Other Upload User",
                email=f"{other_user_id}@test.local",
                emailVerified=True,
                role="USER",
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Project owned by test_user
        await session.execute(
            insert(projects).values(
                id=test_project_id,
                name="Upload Test Project",
                userId=test_user_id,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Project owned by other_user
        await session.execute(
            insert(projects).values(
                id=other_project_id,
                name="Other Upload Project",
                userId=other_user_id,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        await session.commit()

    yield

    # ── Teardown: hard-delete all test data + uploaded files ──────
    async with _test_session_factory() as session:
        proj_stmt = select(projects.c.id).where(
            projects.c.userId.in_([test_user_id, other_user_id])
        )
        proj_res = await session.execute(proj_stmt)
        all_proj_ids = [r[0] for r in proj_res.all()]

        if all_proj_ids:
            await session.execute(
                delete(datasets).where(datasets.c.projectId.in_(all_proj_ids))
            )
            await session.execute(
                delete(projects).where(projects.c.id.in_(all_proj_ids))
            )

        await session.execute(
            delete(users).where(users.c.id.in_([test_user_id, other_user_id]))
        )
        await session.commit()

    await _test_engine.dispose()

    # Clean up uploaded test files
    for proj_id in [test_project_id, other_project_id]:
        proj_dir = _upload_dir / proj_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)


@pytest_asyncio.fixture(loop_scope="module")
async def client():
    """Async HTTP client bound to the FastAPI app."""
    app = create_app()
    async with ASGITransport(app=app) as transport:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def _csv_content(rows: int = 3) -> bytes:
    """Generate a small valid CSV for testing."""
    lines = ["id,name,value"]
    for i in range(1, rows + 1):
        lines.append(f"{i},item_{i},{i * 10}")
    return "\n".join(lines).encode("utf-8")


def _auth_headers(user_id: str) -> dict[str, str]:
    """Return the headers required for an authenticated internal request."""
    return {
        "X-Internal-Secret": _internal_secret,
        "X-User-Id": user_id,
    }


# ── Tests ─────────────────────────────────────────────────────────────


async def test_upload_csv_success(client, test_user_id, test_project_id):
    """Full happy-path: 201, correct shape, file on disk, checksum present."""
    csv_data = _csv_content(5)

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("test_sales.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id, "name": "Sales Dataset"},
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["name"] == "Sales Dataset"
    assert body["fileName"] == "test_sales.csv"
    assert body["fileType"] == "text/csv"
    assert body["fileSizeBytes"] == len(csv_data)
    assert body["status"] == "UPLOADED"
    assert body["projectId"] == test_project_id
    assert body["checksum"] is not None
    assert body["checksum"].startswith("sha256:")
    assert body["parquetUrl"] is None
    assert body["columns"] is None
    assert body["rowCount"] is None
    assert body["colCount"] is None
    assert body["id"] is not None
    assert len(body["id"]) == 25

    # Verify file exists on disk
    file_path = _upload_dir / body["fileUrl"].lstrip("/").replace("uploads/", "", 1)
    assert file_path.exists()
    assert file_path.read_bytes() == csv_data


async def test_upload_missing_secret(client, test_user_id, test_project_id):
    """403 when X-Internal-Secret is absent."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers={"X-User-Id": test_user_id},
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


async def test_upload_wrong_secret(client, test_user_id, test_project_id):
    """403 when X-Internal-Secret has the wrong value."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers={
            "X-Internal-Secret": "wrong-secret-value",
            "X-User-Id": test_user_id,
        },
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


async def test_upload_missing_user_id(client, test_project_id):
    """400 when X-User-Id is absent."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers={"X-Internal-Secret": _internal_secret},
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 400
    assert "X-User-Id" in response.json()["detail"]


async def test_upload_wrong_project_owner(client, test_user_id, other_project_id):
    """403 when user tries to upload to a project they don't own."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": other_project_id},
    )

    assert response.status_code == 403
    assert "access denied" in response.json()["detail"].lower()


async def test_upload_nonexistent_project(client, test_user_id):
    """403 for a project_id that does not exist."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": "nonexistent-project-id-0000"},
    )

    assert response.status_code == 403


async def test_upload_invalid_extension_txt(client, test_user_id, test_project_id):
    """400 for a .txt file."""
    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("data.txt", io.BytesIO(b"some text"), "text/plain")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


async def test_upload_invalid_extension_exe(client, test_user_id, test_project_id):
    """400 for a .exe file."""
    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("malware.exe", io.BytesIO(b"\x4d\x5a"), "application/octet-stream")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


async def test_upload_no_extension(client, test_user_id, test_project_id):
    """400 for a file with no extension."""
    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("datafile", io.BytesIO(b"a,b\n1,2"), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


async def test_upload_oversized_file(test_user_id, test_project_id):
    """413 for a file exceeding max_file_size_mb.

    Creates a dedicated app instance with ``get_settings`` overridden
    to return ``max_file_size_mb=0`` so any non-empty file triggers 413.
    """
    from app.config import get_settings as real_get_settings

    csv_data = b"col\n" + b"x" * 2048

    tiny_settings = real_get_settings()
    # We need a copy-like approach: override just the size limit
    original_max = tiny_settings.max_file_size_mb

    def _override_settings():
        tiny_settings.max_file_size_mb = 0
        return tiny_settings

    app = create_app()
    app.dependency_overrides[real_get_settings] = _override_settings

    try:
        async with ASGITransport(app=app) as transport:
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.post(
                    "/api/v1/datasets/upload",
                    headers=_auth_headers(test_user_id),
                    files={"file": ("big.csv", io.BytesIO(csv_data), "text/csv")},
                    data={"project_id": test_project_id},
                )
    finally:
        tiny_settings.max_file_size_mb = original_max
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "maximum size" in response.json()["detail"].lower()


async def test_upload_empty_file(client, test_user_id, test_project_id):
    """400 for a zero-byte file."""
    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


async def test_upload_safe_filename_generation(client, test_user_id, test_project_id):
    """fileUrl must NOT contain the original filename."""
    original_name = "My Dangerous ../../../etc/passwd.csv"
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": (original_name, io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 201
    body = response.json()

    # fileUrl should use a CUID, not the original filename
    assert "passwd" not in body["fileUrl"]
    assert ".." not in body["fileUrl"]
    assert "etc" not in body["fileUrl"]
    # But fileName should store the sanitized original for display
    assert body["fileName"] is not None


async def test_upload_dataset_record_in_db(client, test_user_id, test_project_id):
    """Verify the Dataset row exists in the DB with correct fields."""
    csv_data = _csv_content(10)

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("db_check.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id, "name": "DB Check Dataset"},
    )

    assert response.status_code == 201
    dataset_id = response.json()["id"]

    # Query the database directly
    assert _test_session_factory is not None
    async with _test_session_factory() as session:
        result = await session.execute(
            select(datasets).where(datasets.c.id == dataset_id)
        )
        row = result.first()

    assert row is not None
    row_dict = dict(row._mapping)
    assert row_dict["name"] == "DB Check Dataset"
    assert row_dict["fileName"] == "db_check.csv"
    assert row_dict["fileSizeBytes"] == len(csv_data)
    assert row_dict["projectId"] == test_project_id
    assert row_dict["status"] == "UPLOADED"
    assert row_dict["fileUrl"].startswith("/uploads/")


async def test_upload_file_exists_on_disk(client, test_user_id, test_project_id):
    """Verify the file actually exists at the path in fileUrl."""
    csv_data = _csv_content(2)

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("disk_check.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
    )

    assert response.status_code == 201
    file_url = response.json()["fileUrl"]

    # fileUrl = /uploads/{project_id}/{cuid}.csv
    # Resolve to absolute path
    rel_parts = file_url.lstrip("/").split("/")  # ["uploads", project_id, "file.csv"]
    file_path = _upload_dir / rel_parts[1] / rel_parts[2]

    assert file_path.exists()
    assert file_path.stat().st_size == len(csv_data)


async def test_upload_default_name_from_filename(client, test_user_id, test_project_id):
    """When 'name' is not provided, the filename stem is used as display name."""
    csv_data = _csv_content()

    response = await client.post(
        "/api/v1/datasets/upload",
        headers=_auth_headers(test_user_id),
        files={"file": ("quarterly_report.csv", io.BytesIO(csv_data), "text/csv")},
        data={"project_id": test_project_id},
        # No 'name' field
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "quarterly_report"
    assert body["fileName"] == "quarterly_report.csv"
