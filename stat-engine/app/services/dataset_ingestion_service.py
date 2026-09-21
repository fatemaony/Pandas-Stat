"""
Dataset ingestion service — CSV parsing and metadata extraction.

Responsibilities:
    1. Validate the dataset record and physical file
    2. Verify file integrity (SHA-256 checksum)
    3. Detect encoding and delimiter
    4. Parse CSV with pandas
    5. Validate headers (empty names, duplicates)
    6. Extract basic metadata (rowCount, colCount, columns with dtypes)
    7. Persist metadata and update status to READY

The service never executes SQL directly — all data access goes through
``DatasetRepository``.  Transaction boundaries are controlled here.

Design notes:
    - Memory: The 50 MB upload limit means pandas holds at most ~250 MB
      in memory.  No chunked processing is needed for Phase 1.
    - Future-proofing: ``ingest()`` is a standalone async method that a
      future Celery worker can call directly without modification.
    - Encoding strategy: utf-8-sig first (handles BOM transparently),
      then latin-1 fallback.  No unreliable chardet sniffing.
    - Delimiter strategy: ``csv.Sniffer`` on the first 8 KB, constrained
      to {, ; \\t}, with ``,`` as the safe default.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import DatasetRow, DatasetStatus
from app.utils.file_utils import compute_file_sha256, resolve_upload_path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

_SNIFF_BYTES: int = 8192  # Bytes read for delimiter detection
_ALLOWED_DELIMITERS: str = ",;\t"


class IngestionError(Exception):
    """Raised for ingestion-specific failures that should set ERROR status.

    Attributes:
        status_code: HTTP status code to return to the client.
        detail: Safe, client-facing error message.
        log_message: Detailed message for server-side logging.
    """

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = 422,
        log_message: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.log_message = log_message or detail


class DatasetIngestionService:
    """Orchestrates CSV ingestion: parsing, validation, and metadata extraction."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings
        self._repo = DatasetRepository(session)

    # ── Public entry point ────────────────────────────────────────

    async def ingest(
        self,
        *,
        dataset_id: str,
        user_id: str,
    ) -> DatasetRow:
        """Parse an uploaded CSV and persist its metadata.

        Lifecycle::

            UPLOADED → PROCESSING → READY   (success)
            UPLOADED → PROCESSING → ERROR    (failure)

        Args:
            dataset_id: CUID of the dataset to ingest.
            user_id: Authenticated user ID for authorization.

        Returns:
            The updated ``DatasetRow`` with metadata populated.

        Raises:
            HTTPException: For all validation, authorization, and parse errors.
        """
        # ── 1. Fetch and validate dataset record ─────────────────
        dataset = await self._repo.get_by_id(dataset_id)
        if dataset is None:
            logger.warning("Ingestion requested for missing dataset: %s", dataset_id)
            raise HTTPException(status_code=404, detail="Dataset not found")

        # ── 2. Authorization ─────────────────────────────────────
        has_access = await self._repo.check_user_access(dataset_id, user_id)
        if not has_access:
            logger.warning(
                "Ingestion access denied: user_id=%s dataset_id=%s",
                user_id,
                dataset_id,
            )
            raise HTTPException(status_code=403, detail="Access denied")

        # ── 3. File-level pre-checks ─────────────────────────────
        file_path = self._validate_file_reference(dataset)

        # ── 4. Checksum verification ─────────────────────────────
        await self._verify_checksum(dataset, file_path)

        # ── 5. Transition to PROCESSING (commit immediately) ─────
        await self._repo.update_status(dataset_id, DatasetStatus.PROCESSING)
        await self._session.commit()

        logger.info(
            "Starting ingestion: dataset_id=%s file=%s",
            dataset_id,
            dataset.file_name,
        )

        # ── 6. Parse CSV and extract metadata (no open txn) ──────
        try:
            raw_bytes = file_path.read_bytes()
            text_content, encoding_used = self._decode_content(raw_bytes)
            delimiter = self._detect_delimiter(text_content)
            df = self._parse_csv(text_content, delimiter)
            self._validate_headers(df)
            metadata = self._extract_metadata(df)

            logger.info(
                "CSV parsed: dataset_id=%s rows=%d columns=%d encoding=%s delimiter=%r",
                dataset_id,
                metadata["row_count"],
                metadata["col_count"],
                encoding_used,
                delimiter,
            )

        except IngestionError as exc:
            logger.error(
                "Dataset ingestion failed: dataset_id=%s reason=%s",
                dataset_id,
                exc.log_message,
            )
            await self._set_error_status(dataset_id)
            raise HTTPException(
                status_code=exc.status_code, detail=exc.detail
            ) from exc

        except Exception as exc:
            logger.error(
                "Dataset ingestion failed (unexpected): dataset_id=%s error=%s",
                dataset_id,
                exc,
                exc_info=True,
            )
            await self._set_error_status(dataset_id)
            raise HTTPException(
                status_code=422, detail="Unable to parse CSV file"
            ) from exc

        # ── 7. Persist metadata + READY (single transaction) ─────
        try:
            result = await self._repo.update_metadata(
                dataset_id,
                rowCount=metadata["row_count"],
                colCount=metadata["col_count"],
                columns=metadata["columns"],
            )
            result = await self._repo.update_status(
                dataset_id, DatasetStatus.READY
            )
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            logger.error(
                "Database error during metadata persistence: dataset_id=%s error=%s",
                dataset_id,
                exc,
                exc_info=True,
            )
            await self._set_error_status(dataset_id)
            raise HTTPException(
                status_code=500, detail="Internal server error"
            ) from exc

        assert result is not None
        logger.info(
            "Ingestion completed: dataset_id=%s status=READY", dataset_id
        )
        return result

    # ── Private helpers ───────────────────────────────────────────

    def _validate_file_reference(self, dataset: DatasetRow) -> Path:
        """Validate the dataset's file reference and return the resolved path.

        Checks:
            - fileUrl has a .csv extension
            - Physical file exists on disk

        Raises:
            IngestionError on any validation failure.
        """
        file_url = dataset.file_url

        # Extension check — trust the stored URL, not a client-supplied value
        if not file_url.lower().endswith(".csv"):
            raise IngestionError(
                "Only CSV files can be ingested",
                log_message=f"Unsupported extension in fileUrl: {file_url}",
            )

        # Resolve to absolute path (with traversal guard)
        try:
            file_path = resolve_upload_path(
                self._settings.upload_dir, file_url
            )
        except ValueError as exc:
            raise IngestionError(
                "Dataset file not found",
                log_message=f"Path traversal detected: {file_url}",
            ) from exc

        # Physical existence check
        if not file_path.exists() or not file_path.is_file():
            raise IngestionError(
                "Dataset file not found",
                log_message=f"File missing on disk: {file_path}",
            )

        return file_path

    async def _verify_checksum(
        self, dataset: DatasetRow, file_path: Path
    ) -> None:
        """Verify the stored SHA-256 checksum against the current file.

        Skips verification if no checksum is stored (logs a warning).

        Raises:
            IngestionError: If checksums do not match (HTTP 409).
        """
        stored = dataset.checksum
        if not stored:
            logger.warning(
                "No checksum stored for dataset %s — skipping verification",
                dataset.id,
            )
            return

        # Extract the hex digest from "sha256:<hex>"
        if stored.startswith("sha256:"):
            expected_hex = stored[len("sha256:"):]
        else:
            expected_hex = stored

        actual_hex = await compute_file_sha256(file_path)

        if actual_hex != expected_hex:
            raise IngestionError(
                "File integrity check failed",
                status_code=409,
                log_message=(
                    f"Checksum mismatch for dataset {dataset.id}: "
                    f"expected={expected_hex} actual={actual_hex}"
                ),
            )

    @staticmethod
    def _decode_content(raw_bytes: bytes) -> tuple[str, str]:
        """Decode raw file bytes to a string.

        Strategy:
            1. ``utf-8-sig`` — handles both plain UTF-8 and UTF-8 with BOM.
            2. ``latin-1`` — fallback that never raises (every byte is valid).

        Returns:
            ``(decoded_text, encoding_name)``

        Raises:
            IngestionError: If the file is empty (zero bytes).
        """
        if not raw_bytes:
            raise IngestionError("CSV file is empty")

        # Try UTF-8 (with BOM stripping)
        try:
            return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

        # Fallback: latin-1 never fails
        return raw_bytes.decode("latin-1"), "latin-1"

    @staticmethod
    def _detect_delimiter(text: str) -> str:
        """Detect the CSV delimiter from the first few KB.

        Uses Python's ``csv.Sniffer`` constrained to ``,``, ``;``, ``\\t``.
        Falls back to ``,`` if sniffing fails.

        Returns:
            The detected single-character delimiter.
        """
        sample = text[:_SNIFF_BYTES]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=_ALLOWED_DELIMITERS)
            return dialect.delimiter
        except csv.Error:
            return ","

    @staticmethod
    def _parse_csv(text: str, delimiter: str) -> pd.DataFrame:
        """Parse the decoded CSV text into a pandas DataFrame.

        Args:
            text: The full decoded CSV content.
            delimiter: The detected delimiter character.

        Returns:
            A ``DataFrame`` with the parsed data.

        Raises:
            IngestionError: If pandas cannot parse the content.
        """
        try:
            df = pd.read_csv(
                io.StringIO(text),
                sep=delimiter,
                header=0,
                engine="python",
                on_bad_lines="error",
            )
        except pd.errors.EmptyDataError as exc:
            raise IngestionError(
                "CSV file is empty",
                log_message=f"pandas EmptyDataError: {exc}",
            ) from exc
        except pd.errors.ParserError as exc:
            raise IngestionError(
                "Unable to parse CSV file",
                log_message=f"pandas ParserError: {exc}",
            ) from exc

        return df

    @staticmethod
    def _validate_headers(df: pd.DataFrame) -> None:
        """Validate DataFrame column names.

        Checks:
            - At least one column exists
            - No empty/whitespace-only column names
            - No duplicate column names

        Raises:
            IngestionError: On any header validation failure.
        """
        columns = list(df.columns)

        if len(columns) == 0:
            raise IngestionError(
                "No columns detected",
                log_message="DataFrame has zero columns",
            )

        # Check for empty/whitespace-only column names
        for i, col in enumerate(columns):
            col_str = str(col).strip()
            if not col_str or col_str.lower() == "unnamed":
                raise IngestionError(
                    f"Empty column name at position {i + 1}",
                    log_message=f"Empty/unnamed column at index {i}: {col!r}",
                )

        # Check for duplicates (case-sensitive)
        seen: dict[str, int] = {}
        duplicates: list[str] = []
        for col in columns:
            col_str = str(col)
            if col_str in seen:
                duplicates.append(col_str)
            else:
                seen[col_str] = 1

        if duplicates:
            unique_dups = sorted(set(duplicates))
            raise IngestionError(
                f"Duplicate column names: {', '.join(unique_dups)}",
                log_message=f"Duplicate columns detected: {unique_dups} in {columns}",
            )

    @staticmethod
    def _extract_metadata(df: pd.DataFrame) -> dict:
        """Extract basic dataset metadata from the parsed DataFrame.

        Returns:
            A dict with keys: ``row_count``, ``col_count``, ``columns``.
            ``columns`` is a list of ``{"name": str, "dtype": str}`` objects.
        """
        columns_meta = [
            {"name": str(col), "dtype": str(df[col].dtype)}
            for col in df.columns
        ]

        return {
            "row_count": len(df),
            "col_count": len(df.columns),
            "columns": columns_meta,
        }

    async def _set_error_status(self, dataset_id: str) -> None:
        """Set the dataset status to ERROR in a fresh transaction.

        This is called after a parsing or persistence failure.
        Errors during this operation are logged but not re-raised,
        to avoid masking the original failure.
        """
        try:
            await self._repo.update_status(dataset_id, DatasetStatus.ERROR)
            await self._session.commit()
        except Exception as exc:
            logger.error(
                "Failed to set ERROR status for dataset %s: %s",
                dataset_id,
                exc,
            )
            try:
                await self._session.rollback()
            except Exception:
                pass
