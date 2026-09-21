"""
File utility functions for the statistical engine.

Provides reusable helpers for:
    - SHA-256 checksum computation on existing files
    - Safe file-path resolution with traversal prevention
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)

CHUNK_SIZE: int = 64 * 1024  # 64 KB — same as the upload service


async def compute_file_sha256(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Compute the SHA-256 hex digest for an existing file on disk.

    Reads the file in chunks to avoid loading the entire file into memory.

    Args:
        path: Absolute path to the file.
        chunk_size: Read buffer size in bytes.

    Returns:
        The lowercase hex digest string (without a ``sha256:`` prefix).

    Raises:
        FileNotFoundError: If *path* does not exist.
        OSError: On I/O failure.
    """
    hasher = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_upload_path(upload_dir: str, file_url: str) -> Path:
    """Resolve a stored ``fileUrl`` to an absolute filesystem path.

    The stored ``fileUrl`` uses the format ``/uploads/{project_id}/{cuid}.csv``.
    This function strips the leading ``/uploads/`` prefix and joins the
    remainder with the configured *upload_dir*, then verifies the result
    is contained within *upload_dir* to prevent path-traversal attacks.

    Args:
        upload_dir: The application's configured upload directory
                    (e.g. ``settings.upload_dir``).
        file_url: The relative URL stored in the database
                  (e.g. ``/uploads/proj123/abc.csv``).

    Returns:
        The resolved absolute ``Path``.

    Raises:
        ValueError: If the resolved path escapes the upload directory
                    (path traversal detected).
    """
    # Strip the leading /uploads/ prefix to get the project-relative part
    relative = file_url.lstrip("/")
    if relative.startswith("uploads/"):
        relative = relative[len("uploads/"):]

    resolved = Path(upload_dir).resolve() / relative
    resolved = resolved.resolve()

    # Guard against path traversal
    upload_root = Path(upload_dir).resolve()
    if not str(resolved).startswith(str(upload_root)):
        raise ValueError("Path traversal detected")

    return resolved
