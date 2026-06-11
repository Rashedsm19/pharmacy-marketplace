"""
Firebase App Check middleware.
Verifies the X-Firebase-AppCheck header when REQUIRE_APPCHECK=true.
This is a stub that validates the JWT structure against Firebase public keys.
"""
from __future__ import annotations

import logging

import jwt
from fastapi import Request, Response
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)

# Cached JWKS client — initialized lazily
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.FIREBASE_APP_CHECK_PUBLIC_KEYS_URL)
    return _jwks_client


class AppCheckMiddleware(BaseHTTPMiddleware):
    """
    Validates Firebase App Check tokens from X-Firebase-AppCheck header.
    Health-check and public endpoints are exempt.
    """

    EXEMPT_PATHS = {"/health", "/api/v1/auth/login", "/api/v1/auth/register"}

    def __init__(self, app, require: bool = True):
        super().__init__(app)
        self.require = require

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.require or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        token = request.headers.get("X-Firebase-AppCheck")
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing App Check token"},
            )

        try:
            client = _get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.FIREBASE_PROJECT_ID,
            )
        except Exception as exc:
            logger.warning("App Check token validation failed: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid App Check token"},
            )

        return await call_next(request)
