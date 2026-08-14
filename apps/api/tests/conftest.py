"""
Shared fixtures.

Tests drive the real application in-process over an ASGI transport, so they
exercise routing, dependencies, auth and the database exactly as a deployed
request would — without needing a server to be started alongside them.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

# Must be set before the app imports its settings.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/pharmacy_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("EMAIL_BACKEND", "stub")
os.environ.setdefault("WHATSAPP_BACKEND", "stub")
os.environ.setdefault("REQUIRE_APPCHECK", "false")
os.environ.setdefault("REQUIRE_CLOUDFLARE", "false")
# The suite signs in dozens of times in seconds; the throttle is not what
# these tests are for, and it has its own.
os.environ.setdefault("THROTTLE_AUTH", "false")

from httpx import ASGITransport, AsyncClient  # noqa: E402

BASE_URL = "http://testserver/api/v1"

SEEDED = {
    "admin": ("admin@pharmacy-marketplace.sa", "Admin@12345"),
    "seller": ("manager@aldawaa.sa", "Manager@12345"),
    "buyer": ("manager@nahdi-demo.sa", "Manager@12345"),
    "pharmacist": ("pharmacist@aldawaa.sa", "Pharma@12345"),
}


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepared_database():
    """Create the schema if needed and seed it once for the whole session."""
    from database import engine
    from models.base import Base
    import models  # noqa: F401 — registers every model on the metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy import func, select
    from database import AsyncSessionLocal
    from models.user import User

    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count()).select_from(User))).scalar_one()

    if not count:
        from seeds.seed import seed
        await seed()

    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


async def login(client: AsyncClient, who: str) -> str:
    """Access token for one of the seeded accounts."""
    email, password = SEEDED[who]
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def unique(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def admin_token(client):
    return await login(client, "admin")


@pytest_asyncio.fixture
async def seller_token(client):
    return await login(client, "seller")


@pytest_asyncio.fixture
async def buyer_token(client):
    """The buyer organization is seeded as pending; approve it so it can trade."""
    admin = await login(client, "admin")
    orgs = (await client.get("/organizations", headers=auth(admin), params={"page_size": 50})).json()
    for org in orgs["items"]:
        if org["status"] == "pending":
            await client.post(
                f"/organizations/{org['id']}/approve", headers=auth(admin), json={"notes": "test"}
            )
    return await login(client, "buyer")
