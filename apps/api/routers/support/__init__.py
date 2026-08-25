"""
The platform support console.

One person is the entire support function for this platform, so these endpoints
exist to let them do for a customer what the customer cannot do for themselves:
look up an account, issue a reset link, disable someone who has left, remove a
listing that should not be public, and delete stock that got in by mistake.

Two rules run through all of it. Every action names a reason and lands in the
audit trail, because acting on someone else's data has to be answerable. And
every guard is a refusal with an explanation rather than a silent no-op — a
support tool that quietly does nothing is worse than one that says why it won't.

The console is split by the thing being acted on. Sub-routers are included in
the order the endpoints were declared in, because registration order is what
decides a path match when two routes could both take a request.
"""
from __future__ import annotations

from fastapi import APIRouter

from routers.support import (
    accounts,
    customers,
    impersonation,
    imports,
    inventory,
    moderation,
    organizations,
)

router = APIRouter(prefix="/admin", tags=["Support console"])

router.include_router(accounts.router)
router.include_router(organizations.router)
router.include_router(moderation.router)
router.include_router(inventory.router)
router.include_router(imports.router)
router.include_router(impersonation.router)
router.include_router(customers.router)

__all__ = ["router"]
