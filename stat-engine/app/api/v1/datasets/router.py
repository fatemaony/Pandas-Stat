"""
Dataset upload router — HTTP boundary for the upload endpoint.

This module contains NO business logic.  It only:
    1. Declares the FastAPI route
    2. Applies authentication dependencies
    3. Receives the multipart form
    4. Delegates to ``DatasetUploadService``
    5. Returns the HTTP response
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db
from app.dependencies.auth import verify_internal_secret, get_user_id
from app.schemas.dataset import DatasetRow
from app.services.dataset_upload_service import DatasetUploadService

router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["datasets"],
    dependencies=[Depends(verify_internal_secret)],
)


@router.post(
    "/upload",
    response_model=DatasetRow,
    status_code=201,
    summary="Upload a CSV dataset",
    description=(
        "Receives a CSV file via multipart/form-data, validates and stores it, "
        "and creates the corresponding Dataset database record with status UPLOADED."
    ),
    responses={
        400: {"description": "Invalid file, missing header, or empty file"},
        403: {"description": "Forbidden — invalid secret or project access denied"},
        413: {"description": "File exceeds maximum allowed size"},
        422: {"description": "Validation error — missing required form fields"},
    },
)
async def upload_dataset(
    user_id: str = Depends(get_user_id),
    file: UploadFile = File(..., description="CSV file to upload"),
    project_id: str = Form(..., description="Target project CUID"),
    name: str | None = Form(None, description="Optional display name"),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DatasetRow:
    """Upload a CSV dataset file.

    Authentication is handled by the ``verify_internal_secret``
    dependency applied at router level.  The ``user_id`` is extracted
    from the ``X-User-Id`` header by the ``get_user_id`` dependency.
    """
    service = DatasetUploadService(session=session, settings=settings)
    return await service.upload(
        file=file,
        project_id=project_id,
        user_id=user_id,
        name=name,
    )
