"""
Notification schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.notification import NotificationChannel, NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: NotificationType
    title: str
    title_ar: str
    body: str
    body_ar: str
    is_read: bool
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    created_at: datetime


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: NotificationType
    channel: NotificationChannel
    is_enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    is_enabled: bool
