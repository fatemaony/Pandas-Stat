"""
Integration tests for DatasetRepository.

These tests run against the live Neon PostgreSQL database configured in .env.
Test rows are created with unique CUIDs and isolated fixtures, and hard-deleted
in teardown to prevent database pollution.
"""

import pytest
import pytest_asyncio
from sqlalchemy import insert, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.tables import users, projects, datasets
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import DatasetCreate, DatasetStatus
from app.utils.ids import generate_cuid

# All tests in this module share a single event loop so that the
# module-scoped setup/teardown fixture and function-scoped session
# fixture can coexist.
pytestmark = pytest.mark.asyncio(loop_scope="module")

# ── Module-level state ────────────────────────────────────────────────

_test_engine = None
_test_session_factory: async_sessionmaker[AsyncSession] | None = None


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
        # Create test user
        await session.execute(
            insert(users).values(
                id=test_user_id,
                name="Test User",
                email=f"{test_user_id}@test.local",
                emailVerified=True,
                role="USER",
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Create second user for access-control tests
        await session.execute(
            insert(users).values(
                id=other_user_id,
                name="Other User",
                email=f"{other_user_id}@test.local",
                emailVerified=True,
                role="USER",
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Create test project owned by test_user
        await session.execute(
            insert(projects).values(
                id=test_project_id,
                name="Test Project",
                userId=test_user_id,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        # Create project owned by other_user
        await session.execute(
            insert(projects).values(
                id=other_project_id,
                name="Other Project",
                userId=other_user_id,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
        )
        await session.commit()

    yield

    # ── Teardown: hard-delete all test data ──
    async with _test_session_factory() as session:
        # Find all projects created by either test user (including isolated fixtures)
        proj_stmt = select(projects.c.id).where(
            projects.c.userId.in_([test_user_id, other_user_id])
        )
        proj_res = await session.execute(proj_stmt)
        all_proj_ids = [r[0] for r in proj_res.all()]

        if all_proj_ids:
            # Delete datasets first (FK constraint)
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


@pytest_asyncio.fixture(loop_scope="module")
async def session():
    """Yield a fresh AsyncSession for each test. Rolls back on exit."""
    assert _test_session_factory is not None
    async with _test_session_factory() as sess:
        yield sess
        await sess.rollback()


@pytest_asyncio.fixture(loop_scope="module")
async def isolated_project_id(session, test_user_id):
    """Create an isolated project for tests requiring empty dataset state."""
    proj_id = generate_cuid()
    await session.execute(
        insert(projects).values(
            id=proj_id,
            name=f"isolated-{proj_id[:8]}",
            userId=test_user_id,
            createdAt=func.now(),
            updatedAt=func.now(),
        )
    )
    await session.commit()

    yield proj_id

    # Clean up datasets in this project then the project itself
    await session.execute(
        delete(datasets).where(datasets.c.projectId == proj_id)
    )
    await session.execute(
        delete(projects).where(projects.c.id == proj_id)
    )
    await session.commit()


@pytest.fixture
def repo(session):
    """Construct a DatasetRepository bound to the test session."""
    return DatasetRepository(session)


def _make_create_data(project_id: str, **overrides) -> DatasetCreate:
    """Helper to build a DatasetCreate with sensible defaults."""
    defaults = {
        "name": f"test-dataset-{generate_cuid()[:8]}",
        "fileName": "test.csv",
        "fileType": "text/csv",
        "fileSizeBytes": 1024,
        "fileUrl": "/uploads/test.csv",
        "projectId": project_id,
    }
    defaults.update(overrides)
    return DatasetCreate(**defaults)


# ── Tests ─────────────────────────────────────────────────────────────


async def test_create_dataset(repo, session, test_project_id):
    data = _make_create_data(test_project_id)
    row = await repo.create(data)
    await session.commit()

    assert row.id is not None
    assert len(row.id) == 25
    assert row.name == data.name
    assert row.file_name == data.file_name
    assert row.status == DatasetStatus.UPLOADED
    assert row.created_at is not None
    assert row.updated_at is not None


async def test_get_by_id(repo, session, test_project_id):
    data = _make_create_data(test_project_id)
    created = await repo.create(data)
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == created.name
    assert fetched.file_url == created.file_url


async def test_get_by_id_not_found(repo):
    fetched = await repo.get_by_id("nonexistent-id-00000000000")
    assert fetched is None


async def test_exists(repo, session, test_project_id):
    data = _make_create_data(test_project_id)
    created = await repo.create(data)
    await session.commit()

    assert await repo.exists(created.id) is True
    assert await repo.exists("nonexistent-id-00000000000") is False


async def test_list_by_project(repo, session, isolated_project_id):
    # Create 3 datasets in an isolated project
    ids = []
    for _ in range(3):
        row = await repo.create(_make_create_data(isolated_project_id))
        ids.append(row.id)
    await session.commit()

    results = await repo.list_by_project(isolated_project_id, limit=50, offset=0)
    assert len(results) == 3
    result_ids = [r.id for r in results]
    for expected_id in ids:
        assert expected_id in result_ids

    # Verify ordering: newest first (and deterministic)
    timestamps = [r.created_at for r in results]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_list_by_project_pagination(repo, session, isolated_project_id):
    # Create 3 datasets in a clean isolated project
    for _ in range(3):
        await repo.create(_make_create_data(isolated_project_id))
    await session.commit()

    page1 = await repo.list_by_project(isolated_project_id, limit=2, offset=0)
    page2 = await repo.list_by_project(isolated_project_id, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 1

    # Deterministic pagination: no overlap between pages
    ids1 = {r.id for r in page1}
    ids2 = {r.id for r in page2}
    assert ids1.isdisjoint(ids2)

    # Verify overall deterministic order
    all_rows = await repo.list_by_project(isolated_project_id, limit=10, offset=0)
    assert [r.id for r in all_rows] == [page1[0].id, page1[1].id, page2[0].id]


async def test_update_status_enum(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    updated = await repo.update_status(created.id, DatasetStatus.PROCESSING)
    await session.commit()

    assert updated is not None
    assert updated.status == DatasetStatus.PROCESSING
    assert updated.updated_at >= created.updated_at


async def test_update_status_string(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    updated = await repo.update_status(created.id, "READY")
    await session.commit()

    assert updated is not None
    assert updated.status == DatasetStatus.READY


async def test_update_status_invalid(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    with pytest.raises(ValueError, match="Invalid dataset status"):
        await repo.update_status(created.id, "NON_EXISTENT_STATUS")


async def test_update_status_not_found(repo):
    result = await repo.update_status("nonexistent-id-00000000000", DatasetStatus.ERROR)
    assert result is None


async def test_update_metadata_all_fields(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    columns_payload = [
        {"name": "age", "type": "int", "nullable": False},
        {"name": "income", "type": "float", "nullable": True},
    ]

    updated = await repo.update_metadata(
        created.id,
        rowCount=1000,
        colCount=2,
        checksum="sha256:abc123def456",
        columns=columns_payload,
        parquetUrl="s3://datasets/test.parquet",
    )
    await session.commit()

    assert updated is not None
    assert updated.row_count == 1000
    assert updated.col_count == 2
    assert updated.checksum == "sha256:abc123def456"
    assert updated.columns == columns_payload
    assert updated.parquet_url == "s3://datasets/test.parquet"
    assert updated.updated_at >= created.updated_at


async def test_update_metadata_snake_case(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    updated = await repo.update_metadata(
        created.id,
        row_count=500,
        col_count=5,
        parquet_url="/storage/snake.parquet",
        checksum="checksum-snake",
    )
    await session.commit()

    assert updated is not None
    assert updated.row_count == 500
    assert updated.col_count == 5
    assert updated.parquet_url == "/storage/snake.parquet"
    assert updated.checksum == "checksum-snake"


async def test_update_metadata_camel_case(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    updated = await repo.update_metadata(
        created.id,
        rowCount=750,
        colCount=8,
        parquetUrl="/storage/camel.parquet",
        checksum="checksum-camel",
    )
    await session.commit()

    assert updated is not None
    assert updated.row_count == 750
    assert updated.col_count == 8
    assert updated.parquet_url == "/storage/camel.parquet"
    assert updated.checksum == "checksum-camel"


async def test_update_metadata_invalid_fields(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    with pytest.raises(ValueError, match="Invalid metadata field"):
        await repo.update_metadata(created.id, unknownField="invalid_value")


async def test_update_metadata_empty_fields(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    result = await repo.update_metadata(created.id)
    assert result is not None
    assert result.id == created.id


async def test_check_user_access_owner(repo, session, test_project_id, test_user_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    assert await repo.check_user_access(created.id, test_user_id) is True


async def test_check_user_access_non_owner(repo, session, test_project_id, other_user_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    assert await repo.check_user_access(created.id, other_user_id) is False


async def test_check_user_access_nonexistent_dataset(repo, test_user_id):
    assert await repo.check_user_access("nonexistent-id-00000000000", test_user_id) is False


async def test_soft_delete(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    deleted = await repo.soft_delete(created.id)
    await session.commit()

    assert deleted is True
    # get_by_id should return None (soft-deleted)
    assert await repo.get_by_id(created.id) is None
    # exists should return False
    assert await repo.exists(created.id) is False


async def test_soft_delete_idempotent(repo, session, test_project_id):
    created = await repo.create(_make_create_data(test_project_id))
    await session.commit()

    assert await repo.soft_delete(created.id) is True
    await session.commit()

    # Second soft delete on same row should return False (already deleted)
    assert await repo.soft_delete(created.id) is False


async def test_soft_deleted_excluded_from_list(repo, session, isolated_project_id):
    created = await repo.create(_make_create_data(isolated_project_id))
    await session.commit()

    await repo.soft_delete(created.id)
    await session.commit()

    results = await repo.list_by_project(isolated_project_id)
    result_ids = {r.id for r in results}
    assert created.id not in result_ids
