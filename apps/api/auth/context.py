"""
Who is really behind the current request.

There are more than twenty places that write audit entries, each passing the
signed-in user as the actor. Threading an extra argument through all of them to
carry "…but support was driving" would be a large change with a guaranteed miss
rate, and a missed one is a silently unattributed action — the worst failure
this feature could have.

So the fact travels out of band: the auth dependency sets it once, and the audit
service reads it. FastAPI resolves dependencies and runs the endpoint in the same
task, and Starlette's middleware copies the context per request, so a value set
here can never leak into another request.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class ActorContext:
    user_id: uuid.UUID | None = None
    impersonator_id: uuid.UUID | None = None
    impersonator_email: str | None = None
    session_id: uuid.UUID | None = None

    @property
    def is_impersonated(self) -> bool:
        return self.impersonator_id is not None


actor_context: ContextVar[ActorContext | None] = ContextVar(
    "actor_context", default=None
)
