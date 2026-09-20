# Sub-Phase 1.3 Design: Database Access Layer + Dataset Repository

---

## 1. Current Database Architecture

```
FastAPI Lifespan
    │
    ├─ init_db(settings) → creates AsyncEngine + async_sessionmaker
    ├─ close_db()        → disposes connection pool on shutdown
    │
    ├─ get_db()          → FastAPI Depends() yields AsyncSession (with rollback-on-error)
    └─ check_db_health() → SELECT 1 via raw engine connection
```

- **Engine**: SQLAlchemy 2.0 `create_async_engine` with `asyncpg`, connection pooling (`pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`).
- **Session**: `async_sessionmaker` producing `AsyncSession` instances — currently unused by any route except the health check (which bypasses sessions entirely).
- **Tables**: 13 SQLAlchemy Core `Table` definitions in [`tables.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/db/tables.py) mirroring Prisma.
- **State**: Module-level globals `engine` and `async_session_factory`.

---

## 2. What Already Exists

| Component | File | Status |
|---|---|---|
| Async engine + pooling | [`app/db/session.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/db/session.py) | Working |
| `get_db()` FastAPI dependency | [`app/db/session.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/db/session.py#L62-L74) | Working (unused) |
| SQLAlchemy Core tables for all 13 Prisma models | [`app/db/tables.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/db/tables.py) | Working |
| `check_db_health()` | [`app/db/session.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/db/session.py#L77-L91) | Working |
| Lifespan (init/close DB) | [`app/main.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/main.py#L17-L32) | Working |
| Health endpoint with DB status | [`app/main.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/app/main.py#L57-L64) | Working |
| 4 passing tests | [`tests/test_db.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/tests/test_db.py), [`tests/test_health.py`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/tests/test_health.py) | Passing |
| Prisma schema (13 models, cuid IDs) | [`prisma/schema.prisma`](file:///c:/projects/ai-analytics/pandas-stat/prisma/schema.prisma) | Migrated |
| `.env` with Neon PostgreSQL URL | [`stat-engine/.env`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/.env) | Configured |

**What does NOT exist yet:**
- No API routers (health is an inline closure)
- No Pydantic request/response schemas
- No repository / data access layer
- No service layer
- No ID generation utility (Prisma uses `cuid()`)

---

## 3. What Is Missing

1. **Repository layer** — No code currently executes INSERT/SELECT/UPDATE against any table. `get_db()` exists but nothing calls it.
2. **Pydantic schemas** — No request/response models for dataset operations.
3. **CUID generation** — Prisma generates `cuid()` IDs server-side. The Python backend needs a compatible ID generator when creating rows.
4. **Timestamp handling** — Prisma uses `@default(now())` and `@updatedAt`. The Python backend must supply `createdAt`/`updatedAt` explicitly since we're bypassing Prisma's runtime.
5. **API router scaffolding** — No router structure exists for mounting domain endpoints.

---

## 4. Whether a Repository Layer Is Actually Necessary

**Yes.** Justification:

| Concern | Without Repository | With Repository |
|---|---|---|
| **Testability** | Service tests must mock SQLAlchemy internals | Repository has a clean async interface to mock |
| **Query isolation** | SQL construction leaks into service/route code | SQL stays in one place |
| **Schema drift protection** | Every service directly references `tables.datasets.c.fileName` | Column references are centralized; if Prisma renames a column, one file changes |
| **Soft-delete consistency** | Every query must remember `WHERE deletedAt IS NULL` | Repository applies it automatically |
| **Transaction boundaries** | Ad-hoc session management scattered across services | Repository methods use the session passed by the service; service controls commit |

The repository should be **thin** — no business logic, just parameterized queries that return typed dicts or Pydantic models. Business rules belong in the service layer.

---

## 5. Proposed Repository Structure

```
stat-engine/app/
├── config.py              (existing)
├── main.py                (existing, modify to mount router)
├── db/
│   ├── __init__.py        (existing)
│   ├── session.py         (existing, no changes)
│   └── tables.py          (existing, no changes)
├── repositories/
│   ├── __init__.py        (new)
│   └── dataset_repo.py   (new — Dataset CRUD via SQLAlchemy Core)
├── schemas/
│   ├── __init__.py        (new)
│   └── dataset.py         (new — Pydantic models for Dataset I/O)
└── utils/
    ├── __init__.py        (new)
    └── ids.py             (new — CUID-compatible ID generation)
```

> [!NOTE]
> No `services/` or `routers/` directory in this sub-phase. The repository is the deliverable. Routers and services will be added in the next sub-phase (Dataset Upload API). This keeps the scope tight.

---

## 6. Proposed Dataset Repository Methods

```python
class DatasetRepository:
    """Async data access layer for the datasets table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, dataset_id: str) -> DatasetRow | None
        """Fetch a single non-deleted dataset by primary key."""

    async def exists(self, dataset_id: str) -> bool
        """Return True if a non-deleted dataset with this ID exists."""

    async def list_by_project(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[DatasetRow]
        """Paginated list of non-deleted datasets in a project."""

    async def create(self, data: DatasetCreate) -> DatasetRow
        """Insert a new dataset row. Generates CUID, sets timestamps."""

    async def update_status(
        self, dataset_id: str, status: str
    ) -> DatasetRow | None
        """Update the status enum value (UPLOADED → PROCESSING → READY → ERROR)."""

    async def update_metadata(
        self, dataset_id: str, **fields
    ) -> DatasetRow | None
        """Partial update of metadata fields (rowCount, colCount, columns, checksum, parquetUrl)."""

    async def check_user_access(
        self, dataset_id: str, user_id: str
    ) -> bool
        """Verify the user owns the project that owns this dataset.
        Joins datasets → projects WHERE projects.userId = user_id."""

    async def soft_delete(self, dataset_id: str) -> bool
        """Set deletedAt = now(). Returns True if a row was affected."""
```

### Design decisions:

- **`DatasetRow`** — A Pydantic model representing a row returned from the database (output schema). Not the same as the SQLAlchemy Table.
- **`DatasetCreate`** — A Pydantic model for insert data (input schema). Does not include `id`, `createdAt`, `updatedAt` — those are generated by the repository.
- **Soft delete** — The Prisma schema uses `deletedAt DateTime?` on every model. All read queries filter `WHERE "deletedAt" IS NULL`.
- **No `commit()`** — The repository does NOT call `session.commit()`. The caller (future service layer) controls transaction boundaries. The repository calls `session.flush()` after writes so the caller gets the generated row back within the same transaction.
- **No hard delete** — Matches Prisma's soft-delete pattern with `deletedAt`.

---

## 7. Proposed Service/Repository Data Flow

```
Future: API Router (Sub-Phase 1.4+)
         │
         │  depends on get_db() → AsyncSession
         │
         ▼
Future: Service Layer
         │
         │  constructs DatasetRepository(session)
         │  calls repo methods
         │  controls commit/rollback
         │
         ▼
THIS PHASE: DatasetRepository
         │
         │  builds SQLAlchemy Core select/insert/update
         │  executes via session.execute(stmt)
         │  returns Pydantic DatasetRow
         │
         ▼
         Existing: app/db/tables.py (Table definitions)
         Existing: app/db/session.py (AsyncSession factory)
         │
         ▼
         PostgreSQL (Neon)
```

---

## 8. Files to Create

| File | Purpose |
|---|---|
| `app/repositories/__init__.py` | Package init |
| `app/repositories/dataset_repo.py` | `DatasetRepository` class with all dataset CRUD methods |
| `app/schemas/__init__.py` | Package init |
| `app/schemas/dataset.py` | `DatasetRow`, `DatasetCreate`, `DatasetStatusEnum` Pydantic models |
| `app/utils/__init__.py` | Package init |
| `app/utils/ids.py` | CUID-compatible ID generation function |
| `tests/test_dataset_repo.py` | Integration tests for repository against live Neon DB |

---

## 9. Files to Modify

| File | Change |
|---|---|
| [`pyproject.toml`](file:///c:/projects/ai-analytics/pandas-stat/stat-engine/pyproject.toml) | Add `cuid2>=2.0.0` dependency (Python CUID2 generator) |

> [!IMPORTANT]
> **No changes** to `session.py`, `tables.py`, `config.py`, or `main.py`. The existing database integration is fully reused as-is.

---

## 10. Database/Schema Impact

**None.**

- No new tables created.
- No Prisma migrations.
- No schema modifications.
- The repository reads/writes to existing Prisma-managed tables (`datasets`, `projects`) using SQLAlchemy Core `select()`/`insert()`/`update()` statements.
- IDs are generated as CUID2 strings in Python, matching Prisma's `cuid()` format and length.

---

## 11. Testing Strategy

### Integration Tests (against live Neon DB)

1. **`test_create_dataset`** — Insert a dataset row, verify it returns a `DatasetRow` with generated ID, timestamps, and status `UPLOADED`.
2. **`test_get_by_id`** — Create → get → verify all fields match.
3. **`test_get_by_id_not_found`** — Query a nonexistent ID → returns `None`.
4. **`test_exists`** — Create → `exists()` returns `True`; random ID → `False`.
5. **`test_list_by_project`** — Create 3 datasets in a project → list returns 3 ordered by `createdAt` desc.
6. **`test_update_status`** — Create → update to `PROCESSING` → verify status changed and `updatedAt` advanced.
7. **`test_update_metadata`** — Create → update `rowCount`, `colCount` → verify partial update.
8. **`test_check_user_access`** — Verify access with correct `userId` → `True`; wrong `userId` → `False`.
9. **`test_soft_delete`** — Create → soft delete → `get_by_id` returns `None` but row exists in DB with `deletedAt` set.

### Test fixtures

- Tests will need a real project and user row in the database. The test module will insert a temporary user + project in `setup`, and soft-delete / clean up in `teardown`.
- All test dataset rows will use unique CUIDs to avoid collisions with production data.

> [!WARNING]
> These are **integration tests** hitting the live Neon database. They require `DATABASE_URL` in `.env`. If we later want isolated unit tests, we'll mock the `AsyncSession` — but for this sub-phase, integration tests against the real schema catch column-name mismatches that unit tests would miss.

---

## 12. Potential Problems

### 12.1 CUID vs CUID2 Compatibility
- **Risk**: Prisma uses `cuid()` (v1), but the best-maintained Python package generates CUID2. The formats differ (`cuid` = `c` prefix + 24 chars; `cuid2` = random string, variable length).
- **Severity**: Medium
- **Mitigation**: PostgreSQL stores them as plain `String` — no format validation occurs at the DB level. Both are unique strings. However, if the Next.js side inspects ID format, mismatches could be confusing. We should pick CUID2 with a fixed length of 25 characters to closely approximate CUID v1 length, or use a Python `cuid` v1 library if one exists.

### 12.2 Timestamp Precision Mismatch
- **Risk**: Prisma's `@default(now())` uses the database server's `now()`. Our Python code will use `datetime.utcnow()` which may have microsecond skew vs. DB time.
- **Severity**: Low
- **Mitigation**: Use `func.now()` in SQLAlchemy insert statements to let PostgreSQL generate the timestamp, keeping it consistent with Prisma's behavior.

### 12.3 `updatedAt` Must Be Set Manually
- **Risk**: Prisma's `@updatedAt` auto-updates the column. SQLAlchemy Core does not. If we forget `updatedAt = func.now()` on UPDATE statements, the field will go stale.
- **Severity**: Medium
- **Mitigation**: Every `update_*` method in the repository must include `.values(updatedAt=func.now())`. Enforce this through code review and tests that assert `updatedAt` advances after updates.

### 12.4 Soft-Delete Filter Leakage
- **Risk**: If any query forgets `WHERE "deletedAt" IS NULL`, soft-deleted rows will reappear.
- **Severity**: Medium
- **Mitigation**: Centralize the filter in a private helper method `_base_select()` that all read methods use. Never construct raw `select(datasets)` outside this helper.

### 12.5 Test Data Pollution
- **Risk**: Integration tests create real rows in the shared Neon database.
- **Severity**: Medium
- **Mitigation**: Tests will use a dedicated cleanup fixture that hard-deletes (`DELETE FROM`) all rows created during the test session, keyed by a test-specific prefix or collected IDs. This prevents leftover test data from accumulating.

---

## Summary

This sub-phase adds exactly **4 production files** and **1 test file**. It modifies only `pyproject.toml` (one new dependency). It touches zero existing source files. The repository provides a clean, tested async interface that the future service and router layers will consume.

**Awaiting your approval before implementation.**
