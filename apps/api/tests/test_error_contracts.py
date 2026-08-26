"""The shape of what this API says when it refuses.

A client reads `detail` and renders it. When one endpoint answered with `detail`
as an object instead, the web classifier could not tell that response from one
produced by a proxy in front of the API — so a real business rejection was shown
to a pharmacy as an infrastructure fault, telling them to retry something that
could never succeed while hiding the reasons that would have told them why.

These tests pin the contract rather than the one endpoint that broke it.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth, login


@pytest.mark.asyncio
async def test_detail_is_a_sentence_and_reasons_travel_beside_it(client: AsyncClient):
    """An eligibility rejection names itself in `detail` and lists why in `reasons`."""
    token = await login(client, "seller")

    # A batch that cannot be listed: the id does not belong to this org at all.
    response = await client.post(
        "/listings",
        headers=auth(token),
        json={
            "batch_id": "00000000-0000-0000-0000-000000000000",
            "quantity": 1,
            "unit_price": "10.00",
        },
    )

    assert response.status_code in (404, 422), response.text
    body = response.json()
    assert isinstance(body["detail"], str), (
        "detail must be text a client can render; an object here blanked the page once"
    )
    if response.status_code == 422 and "reasons" in body:
        assert isinstance(body["reasons"], list)
        assert all(isinstance(r, str) for r in body["reasons"])


@pytest.mark.asyncio
async def test_a_validation_failure_still_answers_with_text(client: AsyncClient):
    """FastAPI's own error shape is a list of objects. It must not escape as one."""
    response = await client.post("/auth/login", json={"email": "not-an-email", "password": "x"})

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], str)
    # The structured part is allowed, but beside `detail`, never inside it.
    assert isinstance(body.get("fields", []), list)


@pytest.mark.asyncio
async def test_no_error_response_puts_an_object_in_detail(client: AsyncClient):
    """Sweep the error paths reachable without a session for the same violation."""
    probes = [
        ("post", "/auth/login", {"json": {"email": "nobody@example.com", "password": "wrong"}}),
        ("post", "/auth/login", {"json": {"email": "bad", "password": "x"}}),
        ("get", "/listings", {}),
        ("get", "/admin/customers", {}),
        ("get", "/inventory/batches", {}),
    ]

    for method, path, kwargs in probes:
        response = await getattr(client, method)(path, **kwargs)
        if response.status_code < 400:
            continue
        body = response.json()
        assert isinstance(body.get("detail"), str), (
            f"{method.upper()} {path} answered {response.status_code} "
            f"with a non-string detail: {body!r}"
        )


@pytest.mark.asyncio
async def test_the_browser_is_allowed_to_read_the_headers_it_needs(client: AsyncClient):
    """Retry-After and X-Request-ID are useless if CORS hides them from JS.

    Neither is on the CORS safelist. Production is same-origin through the web
    proxy and never noticed, but the local development setup this repository
    documents talks to the API cross-origin, where the frontend could read
    neither the wait it was told to show nor the id a bug report is traced by.
    """
    response = await client.get("/health", headers={"Origin": "http://localhost:3000"})

    exposed = response.headers.get("access-control-expose-headers", "")
    exposed_lower = {h.strip().lower() for h in exposed.split(",")}
    assert "x-request-id" in exposed_lower, exposed
    assert "retry-after" in exposed_lower, exposed
