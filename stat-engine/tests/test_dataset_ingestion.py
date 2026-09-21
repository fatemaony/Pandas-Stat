"""
Integration tests for the Dataset Ingestion API (Sub-Phase 1.5).

Tests run against the live Neon PostgreSQL database and the real local
filesystem.  Test rows are created with unique CUIDs and hard-deleted in
teardown to prevent pollution.

Each test that needs a CSV file creates a dataset record *and* writes
the physical file to disk, simulating what Phase 1.4's upload endpoint
produces.  This avoids coupling ingestion tests to the upload endpoint.

Mirrors the fixture pattern established in ``test_dataset_upload.py``.
"""

import hashlib
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
from app.schemas.dataset import DatasetStatus
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


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def setup_and_teardown(test_user_id, test_project_id, other_user_id):
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
                name="Ingestion Test User",
                email=f"{test_user_id}@test.local",
                emailVerified=True,
                role="USER",
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Second user for auth tests
        await session.execute(
            insert(users).values(
                id=other_user_id,
                name="Other Ingestion User",
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
                name="Ingestion Test Project",
                userId=test_user_id,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        await session.commit()

    yield

    # ── Teardown: hard-delete all test data + files ──────────────
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
    proj_dir = _upload_dir / test_project_id
    if proj_dir.exists():
        shutil.rmtree(proj_dir)


@pytest_asyncio.fixture(loop_scope="module")
async def client():
    """Async HTTP client bound to the FastAPI app."""
    app = create_app()
    async with ASGITransport(app=app) as transport:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# ── Helpers ───────────────────────────────────────────────────────────


def _auth_headers(user_id: str) -> dict[str, str]:
    """Return the headers required for an authenticated internal request."""
    return {
        "X-Internal-Secret": _internal_secret,
        "X-User-Id": user_id,
    }


def _sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest for bytes."""
    return hashlib.sha256(data).hexdigest()


async def _create_dataset_with_file(
    project_id: str,
    csv_bytes: bytes,
    *,
    file_name: str = "test.csv",
    compute_checksum: bool = True,
    checksum_override: str | None = None,
) -> str:
    """Create a dataset DB record and write the CSV to disk.

    Simulates the result of Phase 1.4's upload endpoint.

    Returns:
        The dataset ID (CUID).
    """
    assert _test_session_factory is not None

    dataset_id = generate_cuid()
    file_cuid = generate_cuid()
    relative_url = f"/uploads/{project_id}/{file_cuid}.csv"

    # Write file to disk
    file_dir = _upload_dir / project_id
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{file_cuid}.csv"
    file_path.write_bytes(csv_bytes)

    # Determine checksum
    if checksum_override is not None:
        checksum = checksum_override
    elif compute_checksum:
        checksum = f"sha256:{_sha256(csv_bytes)}"
    else:
        checksum = None

    async with _test_session_factory() as session:
        await session.execute(
            insert(datasets).values(
                id=dataset_id,
                name=Path(file_name).stem,
                fileName=file_name,
                fileType="text/csv",
                fileSizeBytes=len(csv_bytes),
                fileUrl=relative_url,
                projectId=project_id,
                status=DatasetStatus.UPLOADED.value,
                checksum=checksum,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        await session.commit()

    return dataset_id


async def _get_dataset_status(dataset_id: str) -> str | None:
    """Read the current status of a dataset directly from the DB."""
    assert _test_session_factory is not None
    async with _test_session_factory() as session:
        result = await session.execute(
            select(datasets.c.status).where(datasets.c.id == dataset_id)
        )
        row = result.first()
        return row[0] if row else None


async def _get_dataset_row(dataset_id: str) -> dict | None:
    """Read the full dataset row directly from the DB."""
    assert _test_session_factory is not None
    async with _test_session_factory() as session:
        result = await session.execute(
            select(datasets).where(datasets.c.id == dataset_id)
        )
        row = result.first()
        return dict(row._mapping) if row else None


# ── Tests ─────────────────────────────────────────────────────────────


async def test_ingest_valid_csv(client, test_user_id, test_project_id):
    """Happy path: valid CSV → READY with correct metadata."""
    csv_data = b"id,name,age,score\n1,Alice,20,85.5\n2,Bob,21,90.0\n3,Carol,19,88.3\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "READY"
    assert body["rowCount"] == 3
    assert body["colCount"] == 4
    assert len(body["columns"]) == 4
    assert body["columns"][0]["name"] == "id"
    assert body["columns"][1]["name"] == "name"
    assert body["columns"][2]["name"] == "age"
    assert body["columns"][3]["name"] == "score"
    # Verify dtypes are present
    assert "dtype" in body["columns"][0]
    assert "dtype" in body["columns"][1]


async def test_ingest_empty_file(client, test_user_id, test_project_id):
    """Zero-byte CSV on disk → ERROR status, 422 response."""
    csv_data = b""
    dataset_id = await _create_dataset_with_file(
        test_project_id, csv_data, compute_checksum=True
    )

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()

    status = await _get_dataset_status(dataset_id)
    assert status == "ERROR"


async def test_ingest_header_only_csv(client, test_user_id, test_project_id):
    """Header-only CSV (no data rows) → READY with rowCount=0."""
    csv_data = b"name,age,city\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "READY"
    assert body["rowCount"] == 0
    assert body["colCount"] == 3
    assert [c["name"] for c in body["columns"]] == ["name", "age", "city"]


async def test_ingest_duplicate_columns(client, test_user_id, test_project_id):
    """Duplicate column names → 422 error."""
    csv_data = b"name,age,name\nAlice,20,Bob\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 422
    assert "duplicate" in response.json()["detail"].lower()

    status = await _get_dataset_status(dataset_id)
    assert status == "ERROR"


async def test_ingest_empty_column_name(client, test_user_id, test_project_id):
    """Empty column name in header → 422 error."""
    csv_data = b"name,,age\nAlice,x,20\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "empty column name" in detail or "unnamed" in detail

    status = await _get_dataset_status(dataset_id)
    assert status == "ERROR"


async def test_ingest_dataset_not_found(client, test_user_id):
    """Non-existent dataset_id → 404."""
    response = await client.post(
        "/api/v1/datasets/nonexistent-id-00000000000/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_ingest_missing_file(client, test_user_id, test_project_id):
    """Dataset exists but physical file was deleted → 422 + ERROR status."""
    csv_data = b"a,b\n1,2\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    # Delete the physical file
    assert _test_session_factory is not None
    async with _test_session_factory() as session:
        result = await session.execute(
            select(datasets.c.fileUrl).where(datasets.c.id == dataset_id)
        )
        file_url = result.scalar()

    relative = file_url.lstrip("/")
    if relative.startswith("uploads/"):
        relative = relative[len("uploads/"):]
    file_path = _upload_dir / relative
    file_path.unlink(missing_ok=True)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 422
    assert "not found" in response.json()["detail"].lower()


async def test_ingest_deleted_dataset(client, test_user_id, test_project_id):
    """Soft-deleted dataset → 404."""
    csv_data = b"x,y\n1,2\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    # Soft-delete the dataset
    assert _test_session_factory is not None
    async with _test_session_factory() as session:
        from sqlalchemy import update
        await session.execute(
            update(datasets)
            .where(datasets.c.id == dataset_id)
            .values(deletedAt=func.now())
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 404


async def test_ingest_malformed_csv(client, test_user_id, test_project_id):
    """Random binary data saved as .csv → ERROR status, 422 response."""
    csv_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02\x00"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    # Should error (either parsing or header validation fails)
    assert response.status_code == 422

    status = await _get_dataset_status(dataset_id)
    assert status == "ERROR"


async def test_ingest_utf8_csv(client, test_user_id, test_project_id):
    """Standard UTF-8 CSV with non-ASCII characters → READY."""
    csv_data = "name,city\nMüller,München\nSørensen,København\n".encode("utf-8")
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["rowCount"] == 2
    assert body["colCount"] == 2


async def test_ingest_utf8_bom_csv(client, test_user_id, test_project_id):
    """UTF-8 with BOM → READY, BOM not in column names."""
    csv_content = "id,value\n1,100\n2,200\n"
    csv_data = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["rowCount"] == 2

    # BOM must NOT appear in the first column name
    first_col_name = body["columns"][0]["name"]
    assert not first_col_name.startswith("\ufeff")
    assert first_col_name == "id"


async def test_ingest_semicolon_csv(client, test_user_id, test_project_id):
    """Semicolon-delimited CSV → READY with correct columns."""
    csv_data = b"name;age;score\nAlice;20;85\nBob;21;90\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["colCount"] == 3
    assert [c["name"] for c in body["columns"]] == ["name", "age", "score"]


async def test_ingest_tab_csv(client, test_user_id, test_project_id):
    """Tab-delimited CSV → READY with correct columns."""
    csv_data = b"name\tage\tscore\nAlice\t20\t85\nBob\t21\t90\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["colCount"] == 3
    assert [c["name"] for c in body["columns"]] == ["name", "age", "score"]


async def test_ingest_checksum_match(client, test_user_id, test_project_id):
    """Correct checksum → ingestion proceeds normally."""
    csv_data = b"x,y\n1,2\n3,4\n"
    # _create_dataset_with_file computes the correct checksum by default
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "READY"


async def test_ingest_checksum_mismatch(client, test_user_id, test_project_id):
    """Tampered file (wrong checksum) → 409 error."""
    csv_data = b"x,y\n1,2\n3,4\n"
    dataset_id = await _create_dataset_with_file(
        test_project_id,
        csv_data,
        checksum_override="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    )

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 409
    assert "integrity" in response.json()["detail"].lower()


async def test_ingest_failure_sets_error_status(client, test_user_id, test_project_id):
    """Any parse failure should leave the dataset in ERROR status."""
    # Use a CSV that will fail header validation (empty column name)
    csv_data = b",data\n1,hello\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 422

    status = await _get_dataset_status(dataset_id)
    assert status == "ERROR"


async def test_ingest_metadata_persisted(client, test_user_id, test_project_id):
    """After ingestion, verify metadata is persisted in the database directly."""
    csv_data = b"product,price,quantity\nWidget,9.99,100\nGadget,19.99,50\n"
    dataset_id = await _create_dataset_with_file(test_project_id, csv_data)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/ingest",
        headers=_auth_headers(test_user_id),
    )

    assert response.status_code == 200

    # Query database directly to verify persistence
    row = await _get_dataset_row(dataset_id)
    assert row is not None
    assert row["status"] == "READY"
    assert row["rowCount"] == 2
    assert row["colCount"] == 3
    assert row["columns"] is not None
    assert len(row["columns"]) == 3

    # Verify column structure
    col_names = [c["name"] for c in row["columns"]]
    assert col_names == ["product", "price", "quantity"]

    # Verify dtypes are present
    for col_meta in row["columns"]:
        assert "dtype" in col_meta
        assert isinstance(col_meta["dtype"], str)
