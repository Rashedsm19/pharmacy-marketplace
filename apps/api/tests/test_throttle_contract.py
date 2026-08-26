"""What a rate-limited caller is actually told.

The suite disables the throttle process-wide (`conftest` sets THROTTLE_AUTH=false
before the app imports its settings, and settings is a cached singleton), so
these tests build their own app with the middleware switched on rather than
reusing the shared `client` fixture.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from middleware.logging import LoggingMiddleware
from middleware.throttle import LIMITS, LoginThrottleMiddleware, _arabic_minutes


def _throttled_app() -> FastAPI:
    """A minimal app wired in the same order as the real one."""
    app = FastAPI()

    # Registered before the logger so it ends up INSIDE it — `add_middleware`
    # prepends, so the last registered is outermost. This is the ordering that
    # lets a 429 come back out through the logger and carry a request id.
    app.add_middleware(LoginThrottleMiddleware, enabled=True)
    app.add_middleware(LoggingMiddleware)

    @app.post("/api/v1/auth/login")
    async def _login() -> dict:
        return {"ok": True}

    return app


@pytest.fixture
async def throttled_client():
    app = _throttled_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_the_limit_trips_and_says_so_in_arabic(throttled_client: AsyncClient):
    attempts, _window = LIMITS["/api/v1/auth/login"]

    for _ in range(attempts):
        ok = await throttled_client.post("/api/v1/auth/login", json={})
        assert ok.status_code == 200

    blocked = await throttled_client.post("/api/v1/auth/login", json={})

    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert isinstance(detail, str)
    assert "محاولات كثيرة" in detail


@pytest.mark.asyncio
async def test_retry_after_is_seconds_and_the_message_is_minutes(
    throttled_client: AsyncClient,
):
    """The header is machine-readable seconds; the sentence is human minutes.

    They are different units on purpose — RFC 7231 wants delta-seconds — so a
    test that assumed they matched would be asserting the wrong thing.
    """
    attempts, window = LIMITS["/api/v1/auth/login"]
    for _ in range(attempts):
        await throttled_client.post("/api/v1/auth/login", json={})

    blocked = await throttled_client.post("/api/v1/auth/login", json={})

    seconds = int(blocked.headers["retry-after"])
    assert 0 < seconds <= window + 1
    assert _arabic_minutes(seconds) in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_a_throttled_attempt_still_carries_a_request_id(
    throttled_client: AsyncClient,
):
    """The 429 used to short-circuit outside the logger, so it had no id at all.

    That is the one field support asks for, and the response most likely to
    generate a support request was the only one without it.
    """
    attempts, _ = LIMITS["/api/v1/auth/login"]
    for _ in range(attempts):
        await throttled_client.post("/api/v1/auth/login", json={})

    blocked = await throttled_client.post("/api/v1/auth/login", json={})

    assert blocked.status_code == 429
    assert blocked.headers.get("x-request-id"), (
        "a throttled response must be traceable like any other"
    )


def test_the_wait_rounds_up_and_reads_as_arabic():
    """Rounding down told someone to come back before the window had closed."""
    assert _arabic_minutes(30) == "دقيقة"
    assert _arabic_minutes(60) == "دقيقة"
    assert _arabic_minutes(61) == "دقيقتين"
    assert _arabic_minutes(120) == "دقيقتين"
    assert _arabic_minutes(121) == "3 دقائق"
    # The boundary the old floor got wrong: 299s was announced as "4 دقيقة".
    assert _arabic_minutes(299) == "5 دقائق"
    assert _arabic_minutes(300) == "5 دقائق"
    assert _arabic_minutes(301) == "6 دقائق"
    assert _arabic_minutes(660) == "11 دقيقة"


def test_only_the_authentication_endpoints_are_limited():
    """Guards the blast radius: this must not quietly start throttling the app."""
    assert set(LIMITS) == {
        "/api/v1/auth/login",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/register",
    }
