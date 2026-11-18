"""
API-key authentication for the demo service.

The key is read from the ``API_KEY`` environment variable at request time and
compared with :func:`hmac.compare_digest`. When ``API_KEY`` is unset the
protected endpoints fail closed with 503 rather than running open
(docs/SERVING_DESIGN.md §5).

There is deliberately no rate limiter: this is a demo service, and a limiter
that is switched off is worse than none because it implies protection.
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_ENV_VAR = "API_KEY"
API_KEY_HEADER_NAME = os.getenv("API_KEY_HEADER_NAME", "X-API-Key")

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def expected_api_key() -> str | None:
    """The configured key, or None. Read per call so tests can set it."""
    return os.getenv(API_KEY_ENV_VAR) or None


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    expected = expected_api_key()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "api_key_not_configured",
                "message": f"{API_KEY_ENV_VAR} is not set; refusing to serve "
                           "unauthenticated requests",
            },
        )
    if not api_key or not hmac.compare_digest(
        api_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "Invalid or missing API key"},
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )
