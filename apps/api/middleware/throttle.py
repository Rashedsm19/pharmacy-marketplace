"""
A limit on how often the same address may try to authenticate.

There was none. Anyone could sit on `/auth/login` and work through a password
list at whatever rate the network allowed, and on `/auth/forgot-password` mint a
reset token per request. An nginx config in the repository does have limits, but
production runs uvicorn directly with nothing in front of it, so those rules
have never applied to a single real request.

The counter lives in memory. That is honest about what it is: this deployment
runs one instance, so one process sees every attempt. If a second instance is
ever added this becomes per-instance and the effective limit doubles — still far
better than none, and the note is here so the next person knows to move it to
Redis rather than discovering it.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.throttle")

# Path → (attempts, window in seconds). Deliberately generous: a pharmacist who
# mistypes a password three times in a row must not be locked out of their own
# account, while a list of ten thousand passwords must not be workable.
LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login": (10, 300),
    "/api/v1/auth/forgot-password": (5, 900),
    "/api/v1/auth/reset-password": (10, 900),
    "/api/v1/auth/register": (5, 900),
}


class LoginThrottleMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _client(self, request: Request) -> str:
        # Behind Render's edge the peer address is an internal one, so prefer the
        # forwarded header when present; fall back to the peer otherwise.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        limit = LIMITS.get(request.url.path)
        if not self.enabled or limit is None or request.method != "POST":
            return await call_next(request)

        attempts, window = limit
        key = (request.url.path, self._client(request))
        now = time.monotonic()

        seen = self._hits[key]
        while seen and now - seen[0] > window:
            seen.popleft()

        if len(seen) >= attempts:
            retry_after = int(window - (now - seen[0])) + 1
            logger.warning(
                "Throttled %s from %s (%d attempts in %ds)",
                request.url.path, key[1], len(seen), window,
            )
            return ORJSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": (
                        "محاولات كثيرة خلال وقت قصير. "
                        f"حاول مرة اخرى بعد {max(retry_after // 60, 1)} دقيقة."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        seen.append(now)

        # Keep the table from growing without bound on a long-lived process.
        if len(self._hits) > 10_000:
            for stale_key in [
                k for k, v in self._hits.items() if not v or now - v[-1] > 3600
            ][:5000]:
                self._hits.pop(stale_key, None)

        return await call_next(request)
