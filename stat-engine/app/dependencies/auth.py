"""
FastAPI dependencies for internal authentication.

These dependencies verify that requests originate from the trusted Next.js
BFF (via ``X-Internal-Secret``) and extract the authenticated user ID
(via ``X-User-Id``).  They are NOT a session store — Better Auth on the
Next.js side remains the single source of session truth.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Depends

from app.config import Settings, get_settings


async def verify_internal_secret(
    x_internal_secret: str | None = Header(None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject requests that lack a valid ``X-Internal-Secret`` header.

    This ensures only the trusted Next.js BFF can call the stat-engine
    API.  Direct browser-to-FastAPI calls are blocked.

    Raises:
        HTTPException 403 if the header is missing or does not match.
    """
    if not x_internal_secret or x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Forbidden")


async def get_user_id(
    x_user_id: str | None = Header(None),
) -> str:
    """Extract and return the ``X-User-Id`` header value.

    The Next.js BFF sets this header after verifying the Better Auth
    session.  If the header is absent the request is malformed.

    Raises:
        HTTPException 400 if the header is missing.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return x_user_id
