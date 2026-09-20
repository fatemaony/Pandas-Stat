"""
Dataset repository — async data access layer for the ``datasets`` table.

All read queries automatically filter out soft-deleted rows
(``"deletedAt" IS NULL``).  Write methods set ``updatedAt`` via
PostgreSQL's ``now()`` to stay consistent with Prisma's ``@updatedAt``.

The repository never calls ``session.commit()``; the caller (service
layer) controls transaction boundaries.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, insert, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import datasets, projects
from app.schemas.dataset import DatasetCreate, DatasetRow, DatasetStatus
from app.utils.ids import generate_cuid

logger = logging.getLogger(__name__)


class DatasetRepository:
    """Async CRUD operations against the ``datasets`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Private helpers ────────────────────────────────────────────

    @staticmethod
    def _base_select():
        """Return a SELECT with the soft-delete filter pre-applied."""
        return select(datasets).where(datasets.c.deletedAt.is_(None))

    @staticmethod
    def _row_to_schema(row) -> DatasetRow:
        """Convert a SQLAlchemy Row to a Pydantic DatasetRow."""
        return DatasetRow.model_validate(dict(row._mapping))

    # ── Read operations ────────────────────────────────────────────

    async def get_by_id(self, dataset_id: str) -> DatasetRow | None:
        """Fetch a single non-deleted dataset by primary key."""
        stmt = self._base_select().where(datasets.c.id == dataset_id)
        result = await self._session.execute(stmt)
        row = result.first()
        return self._row_to_schema(row) if row else None

    async def exists(self, dataset_id: str) -> bool:
        """Return ``True`` if a non-deleted dataset with this ID exists."""
        stmt = (
            select(func.count())
            .select_from(datasets)
            .where(
                and_(
                    datasets.c.id == dataset_id,
                    datasets.c.deletedAt.is_(None),
                )
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    _METADATA_FIELD_MAP = {
        "rowCount": "rowCount",
        "row_count": "rowCount",
        "colCount": "colCount",
        "col_count": "colCount",
        "parquetUrl": "parquetUrl",
        "parquet_url": "parquetUrl",
        "columns": "columns",
        "checksum": "checksum",
    }

    async def list_by_project(
        self,
        project_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DatasetRow]:
        """Paginated list of non-deleted datasets in a project, newest first."""
        stmt = (
            self._base_select()
            .where(datasets.c.projectId == project_id)
            .order_by(datasets.c.createdAt.desc(), datasets.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._row_to_schema(row) for row in result.all()]

    # ── Write operations ───────────────────────────────────────────

    async def create(self, data: DatasetCreate) -> DatasetRow:
        """Insert a new dataset row.

        Generates a CUID primary key and sets ``createdAt`` / ``updatedAt``
        to the database server's ``now()``.
        """
        new_id = generate_cuid()
        stmt = (
            insert(datasets)
            .values(
                id=new_id,
                name=data.name,
                fileName=data.file_name,
                fileType=data.file_type,
                fileSizeBytes=data.file_size_bytes,
                fileUrl=data.file_url,
                projectId=data.project_id,
                status=DatasetStatus.UPLOADED.value,
                createdAt=func.now(),
                updatedAt=func.now(),
            )
            .returning(datasets)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            raise RuntimeError("INSERT … RETURNING produced no row")
        await self._session.flush()
        return self._row_to_schema(row)

    async def update_status(
        self, dataset_id: str, status: DatasetStatus | str
    ) -> DatasetRow | None:
        """Update the status enum value and refresh ``updatedAt``.

        Accepts either a ``DatasetStatus`` enum or a valid string (e.g. "READY").
        Raises ``ValueError`` if the status string is invalid.
        """
        if isinstance(status, DatasetStatus):
            status_enum = status
        elif isinstance(status, str):
            try:
                status_enum = DatasetStatus(status)
            except ValueError:
                valid = [s.value for s in DatasetStatus]
                raise ValueError(
                    f"Invalid dataset status: '{status}'. Must be one of: {valid}"
                )
        else:
            raise ValueError(
                f"Status must be DatasetStatus or str, got {type(status).__name__}"
            )

        stmt = (
            update(datasets)
            .where(
                and_(
                    datasets.c.id == dataset_id,
                    datasets.c.deletedAt.is_(None),
                )
            )
            .values(status=status_enum.value, updatedAt=func.now())
            .returning(datasets)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        await self._session.flush()
        return self._row_to_schema(row)

    async def update_metadata(
        self, dataset_id: str, **fields: Any
    ) -> DatasetRow | None:
        """Partial update of metadata fields.

        Accepts both snake_case and camelCase keyword arguments:
        - ``row_count`` / ``rowCount``
        - ``col_count`` / ``colCount``
        - ``parquet_url`` / ``parquetUrl``
        - ``columns``
        - ``checksum``

        Raises ``ValueError`` if unknown keyword arguments are provided.
        """
        values: dict[str, Any] = {}
        for k, v in fields.items():
            if k not in self._METADATA_FIELD_MAP:
                raise ValueError(
                    f"Invalid metadata field: '{k}'. Allowed fields are: "
                    "row_count/rowCount, col_count/colCount, "
                    "parquet_url/parquetUrl, columns, checksum."
                )
            col_name = self._METADATA_FIELD_MAP[k]
            values[col_name] = v

        if not values:
            # Nothing to update — return current state
            return await self.get_by_id(dataset_id)

        values["updatedAt"] = func.now()

        stmt = (
            update(datasets)
            .where(
                and_(
                    datasets.c.id == dataset_id,
                    datasets.c.deletedAt.is_(None),
                )
            )
            .values(**values)
            .returning(datasets)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        await self._session.flush()
        return self._row_to_schema(row)

    # ── Access control ─────────────────────────────────────────────

    async def check_user_access(
        self, dataset_id: str, user_id: str
    ) -> bool:
        """Verify the user owns the project that owns this dataset.

        Joins ``datasets → projects`` and checks
        ``projects."userId" = user_id``.
        """
        stmt = (
            select(func.count())
            .select_from(datasets.join(projects, datasets.c.projectId == projects.c.id))
            .where(
                and_(
                    datasets.c.id == dataset_id,
                    datasets.c.deletedAt.is_(None),
                    projects.c.deletedAt.is_(None),
                    projects.c.userId == user_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def check_project_ownership(
        self, project_id: str, user_id: str
    ) -> bool:
        """Verify the user owns the specified project.

        Unlike ``check_user_access`` (which starts from a *dataset* ID),
        this method queries the ``projects`` table directly.  It is used
        during upload when the dataset does not yet exist.
        """
        stmt = (
            select(func.count())
            .select_from(projects)
            .where(
                and_(
                    projects.c.id == project_id,
                    projects.c.deletedAt.is_(None),
                    projects.c.userId == user_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    # ── Soft delete ────────────────────────────────────────────────

    async def soft_delete(self, dataset_id: str) -> bool:
        """Set ``deletedAt = now()``.  Returns ``True`` if a row was affected."""
        stmt = (
            update(datasets)
            .where(
                and_(
                    datasets.c.id == dataset_id,
                    datasets.c.deletedAt.is_(None),
                )
            )
            .values(deletedAt=func.now(), updatedAt=func.now())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return (result.rowcount or 0) > 0
