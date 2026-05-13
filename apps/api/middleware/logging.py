"""
Request/response logging middleware.
Controlled by LOG_LEVEL and NOLOG env vars.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Attach request ID to state for downstream use
        request.state.request_id = request_id

        logger.info(
            "→ %s %s [%s]",
            request.method,
            request.url.path,
            request_id,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "✕ %s %s [%s] %.1fms — %s",
                request.method,
                request.url.path,
                request_id,
                elapsed,
                exc,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "← %s %s [%s] %d %.1fms",
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            elapsed,
        )
        response.headers["X-Request-ID"] = request_id
        return response
