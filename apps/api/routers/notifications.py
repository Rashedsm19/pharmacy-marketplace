"""Notifications router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException

from dependencies import CurrentUser, DbSession
from repositories.notification import NotificationRepository, NotificationPreferenceRepository
from schemas.common import MessageResponse, PaginatedResponse
from schemas.notification import NotificationOut, NotificationPreferenceOut, NotificationPreferenceUpdate

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedResponse[NotificationOut])
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    repo = NotificationRepository(db)
    rows, total = await repo.list_by_user(
        current_user.id, unread_only=unread_only,
        offset=(page - 1) * page_size, limit=page_size,
    )
    return PaginatedResponse(
        items=[NotificationOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/unread-count")
async def unread_count(db: DbSession, current_user: CurrentUser):
    repo = NotificationRepository(db)
    count = await repo.count_unread(current_user.id)
    return {"count": count}


@router.post("/{notification_id}/read", response_model=MessageResponse)
async def mark_read(notification_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    repo = NotificationRepository(db)
    notif = await repo.get(notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.flush()
    return MessageResponse(message="Marked as read")


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_read(db: DbSession, current_user: CurrentUser):
    repo = NotificationRepository(db)
    count = await repo.mark_all_read(current_user.id)
    return MessageResponse(message=f"Marked {count} notifications as read")


@router.get("/preferences", response_model=list[NotificationPreferenceOut])
async def get_preferences(db: DbSession, current_user: CurrentUser):
    repo = NotificationPreferenceRepository(db)
    prefs = await repo.list_by_user(current_user.id)
    return [NotificationPreferenceOut.model_validate(p) for p in prefs]


@router.patch("/preferences/{pref_id}", response_model=NotificationPreferenceOut)
async def update_preference(
    pref_id: uuid.UUID,
    data: NotificationPreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    repo = NotificationPreferenceRepository(db)
    pref = await repo.get(pref_id)
    if not pref or pref.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Preference not found")
    pref.is_enabled = data.is_enabled
    await db.flush()
    return NotificationPreferenceOut.model_validate(pref)
