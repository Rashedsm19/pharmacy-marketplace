"""Support console — viewing as a customer."""
from __future__ import annotations


import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from dependencies import DbSession, SuperAdmin
from models.user import UserRole
from schemas.support import (
    ImpersonateIn,
    ImpersonateOut,
    ImpersonationRow,
)
from services.audit_service import AuditService

from routers.support.helpers import _client, _load_user, _org_of

router = APIRouter()


# ── Viewing as a customer ─────────────────────────────────────────────────────

@router.post("/users/{user_id}/impersonate", response_model=ImpersonateOut)
async def impersonate(
    user_id: uuid.UUID,
    payload: ImpersonateIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> ImpersonateOut:
    """Open a time-limited session inside a customer's account.

    "It doesn't work on my screen" is most of support, and answering it from
    outside the account is guesswork. The session is recorded, expires on its
    own, and can be ended on the spot — and no refresh token is issued, so it
    cannot quietly extend itself.
    """
    from config import settings
    from auth.jwt import create_access_token
    from models.impersonation import ImpersonationSession

    target = await _load_user(db, user_id)
    if target.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكن انتحال حساب مدير منصة",
        )
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="الحساب معطل — فعله أولا إن أردت تصفحه",
        )

    organization, _ = await _org_of(db, target.id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="الحساب بلا منشأة — لا توجد شاشات لتصفحها",
        )

    now = datetime.now(timezone.utc)
    session = ImpersonationSession(
        id=uuid.uuid4(),
        admin_user_id=current_user.id,
        admin_email=current_user.email,
        target_user_id=target.id,
        target_email=target.email,
        organization_id=organization.id,
        organization_name=organization.name_ar or organization.name,
        reason=payload.reason,
        started_at=now,
        expires_at=now + timedelta(minutes=payload.minutes),
        **_client(request),
    )
    db.add(session)
    await db.flush()

    token = create_access_token(
        target.id,
        target.email,
        target.role,
        organization.id,
        impersonator_id=current_user.id,
        impersonator_email=current_user.email,
        session_id=session.id,
        expires_minutes=payload.minutes,
    )

    await AuditService(db).log(
        action="support.impersonation.start",
        resource_type="user",
        resource_id=target.id,
        actor_id=current_user.id,
        organization_id=organization.id,
        after_state={
            "session_id": str(session.id),
            "expires_at": session.expires_at.isoformat(),
            "minutes": payload.minutes,
        },
        notes=payload.reason,
        **_client(request),
    )
    assert settings  # configuration is loaded; keeps the import meaningful

    return ImpersonateOut(
        access_token=token,
        expires_at=session.expires_at,
        session_id=session.id,
        user_id=target.id,
        user_email=target.email,
        user_name=target.full_name,
        organization_id=organization.id,
        organization_name=session.organization_name or "",
        notice=(
            f"أنت الآن تتصفح حساب «{session.organization_name}» لمدة "
            f"{payload.minutes} دقيقة. كل إجراء يسجل باسمك."
        ),
    )


@router.post("/impersonation/{session_id}/end")
async def end_impersonation(
    session_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> dict:
    """Close a session immediately — the token stops working on its next use."""
    from models.impersonation import ImpersonationSession

    session = await db.get(ImpersonationSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="الجلسة غير موجودة"
        )
    if session.ended_at is not None:
        return {"id": str(session.id), "ended": True, "message": "الجلسة منتهية بالفعل"}

    session.ended_at = datetime.now(timezone.utc)
    session.ended_reason = "ended_by_admin"
    await db.flush()

    await AuditService(db).log(
        action="support.impersonation.end",
        resource_type="user",
        resource_id=session.target_user_id,
        actor_id=current_user.id,
        organization_id=session.organization_id,
        after_state={"session_id": str(session.id)},
        notes=f"إنهاء تصفح حساب {session.target_email}",
        **_client(request),
    )
    return {"id": str(session.id), "ended": True, "message": "أنهيت الجلسة"}


@router.get("/impersonation/sessions", response_model=list[ImpersonationRow])
async def list_impersonation_sessions(
    db: DbSession,
    current_user: SuperAdmin,
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ImpersonationRow]:
    """Who has been inside which account, and who is inside one right now."""
    from models.impersonation import ImpersonationSession

    query = select(ImpersonationSession).order_by(
        ImpersonationSession.started_at.desc()
    )
    if active_only:
        query = query.where(
            ImpersonationSession.ended_at.is_(None),
            ImpersonationSession.expires_at > datetime.now(timezone.utc),
        )
    rows = (await db.execute(query.limit(limit))).scalars().all()
    return [ImpersonationRow.model_validate(row) for row in rows]

