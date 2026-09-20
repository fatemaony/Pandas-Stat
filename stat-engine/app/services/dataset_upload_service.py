"""
Dataset upload service — business logic for receiving and storing CSV files.

Responsibilities:
    1. Validate the uploaded file (extension, MIME, empty check)
    2. Authorize project ownership (via repository)
    3. Stream the file to disk with mid-stream size enforcement
    4. Compute SHA-256 checksum during streaming
    5. Create the Dataset database record

The service never executes SQL directly — all data access goes through
``DatasetRepository``.  Transaction commit is performed here (service
layer controls transaction boundaries).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import DatasetCreate, DatasetRow
from app.utils.ids import generate_cuid

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS: set[str] = {".csv"}
ALLOWED_MIME_TYPES: set[str] = {
    "text/csv",
    "application/csv",
    "text/comma-separated-values",
    "application/vnd.ms-excel",  # Some browsers send this for CSV
}
CHUNK_SIZE: int = 64 * 1024  # 64 KB
MAX_FILENAME_LENGTH: int = 255


class DatasetUploadService:
    """Orchestrates the dataset file upload workflow."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings
        self._repo = DatasetRepository(session)

    # ── Public entry point ────────────────────────────────────────

    async def upload(
        self,
        *,
        file: UploadFile,
        project_id: str,
        user_id: str,
        name: str | None = None,
    ) -> DatasetRow:
        """Receive, validate, store, and record a CSV upload.

        Args:
            file: The ``UploadFile`` from the multipart form.
            project_id: CUID of the target project.
            user_id: Authenticated user ID (from ``X-User-Id``).
            name: Optional display name; defaults to the filename stem.

        Returns:
            The newly created ``DatasetRow``.

        Raises:
            HTTPException: For all validation, authorization, and I/O errors.
        """
        # 1. File-level validation (before any disk or DB work)
        original_filename = self._validate_file(file)

        # 2. Authorization — verify user owns the project
        await self._authorize_project(project_id, user_id)

        # 3. Determine display name
        display_name = name if name else Path(original_filename).stem

        # 4. Generate safe storage path
        file_cuid = generate_cuid()
        relative_path = f"/uploads/{project_id}/{file_cuid}.csv"
        absolute_path = Path(self._settings.upload_dir) / project_id / f"{file_cuid}.csv"

        # 5. Stream file to disk
        file_size, checksum = await self._stream_to_disk(file, absolute_path)

        # 6. Create the Dataset record
        try:
            dataset = await self._repo.create(
                DatasetCreate(
                    name=display_name,
                    fileName=original_filename,
                    fileType="text/csv",
                    fileSizeBytes=file_size,
                    fileUrl=relative_path,
                    projectId=project_id,
                )
            )

            # Update checksum via the repository's metadata update
            dataset = await self._repo.update_metadata(
                dataset.id, checksum=f"sha256:{checksum}"
            )

            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            # Clean up the file on DB failure
            absolute_path.unlink(missing_ok=True)
            logger.error("Database error during dataset creation: %s", exc)
            raise HTTPException(status_code=500, detail="Database error") from exc

        assert dataset is not None
        return dataset

    # ── Private helpers ───────────────────────────────────────────

    def _validate_file(self, file: UploadFile) -> str:
        """Validate extension, MIME type, and filename.

        Returns the sanitized original filename.

        Raises:
            HTTPException 400 for invalid files.
        """
        raw_filename = file.filename or ""

        # Sanitize: strip null bytes, limit length
        sanitized = raw_filename.replace("\x00", "").strip()
        if len(sanitized) > MAX_FILENAME_LENGTH:
            sanitized = sanitized[:MAX_FILENAME_LENGTH]

        if not sanitized:
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        # Extension check (primary gate)
        ext = Path(sanitized).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        # MIME check (secondary signal — attacker-controlled but still useful)
        content_type = (file.content_type or "").lower().split(";")[0].strip()
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        return sanitized

    async def _authorize_project(self, project_id: str, user_id: str) -> None:
        """Verify the user owns the target project.

        Raises:
            HTTPException 403 if the project is not found or not owned.
        """
        is_owner = await self._repo.check_project_ownership(project_id, user_id)
        if not is_owner:
            raise HTTPException(
                status_code=403, detail="Project not found or access denied"
            )

    async def _stream_to_disk(
        self, file: UploadFile, dest: Path
    ) -> tuple[int, str]:
        """Stream the upload to disk with mid-stream size enforcement.

        Creates the parent directory if needed.  Computes SHA-256 on the
        fly.  Aborts and cleans up if the size limit is exceeded or if
        the file is empty.

        Returns:
            ``(file_size_bytes, sha256_hex)``

        Raises:
            HTTPException 413 if the file exceeds ``max_file_size_mb``.
            HTTPException 400 if the file is empty.
            HTTPException 500 on I/O errors.
        """
        max_bytes = self._settings.max_file_size_mb * 1024 * 1024
        accumulated = 0
        hasher = hashlib.sha256()

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(dest, "wb") as f:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    accumulated += len(chunk)
                    if accumulated > max_bytes:
                        # Abort: close, delete partial file, reject
                        await f.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum size of {self._settings.max_file_size_mb} MB",
                        )

                    await f.write(chunk)
                    hasher.update(chunk)

        except HTTPException:
            # Re-raise validation errors (413) as-is
            raise
        except Exception as exc:
            # I/O failure — clean up and report
            dest.unlink(missing_ok=True)
            logger.error("File storage failed: %s", exc)
            raise HTTPException(
                status_code=500, detail="File storage failed"
            ) from exc

        # Empty file check
        if accumulated == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        return accumulated, hasher.hexdigest()
