"""
Notification service — creates in-app notifications and dispatches to channels.
"""
from __future__ import annotations

import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models.notification import Notification, NotificationType
from repositories.notification import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    async def create(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        title_ar: str,
        body: str,
        body_ar: str,
        organization_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> Notification:
        notif = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            notification_type=notification_type,
            title=title,
            title_ar=title_ar,
            body=body,
            body_ar=body_ar,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
        )
        self.db.add(notif)
        await self.db.flush()

        # Dispatch to external channels (stubs)
        await self._dispatch_email(user_id, title, body)
        await self._dispatch_whatsapp(user_id, body_ar)

        return notif

    async def _dispatch_email(self, user_id: uuid.UUID, subject: str, body: str) -> None:
        """Email dispatch stub — replace with real adapter in production."""
        from config import settings
        if settings.EMAIL_BACKEND == "stub":
            logger.debug("EMAIL STUB: to_user=%s subject=%s", user_id, subject)
            return
        # Production: implement Resend / SMTP dispatch here

    async def _dispatch_whatsapp(self, user_id: uuid.UUID, body: str) -> None:
        """WhatsApp dispatch stub — replace with Meta Cloud API adapter."""
        from config import settings
        if settings.WHATSAPP_BACKEND == "stub":
            logger.debug("WHATSAPP STUB: to_user=%s", user_id)
            return
        # Production: implement Meta WhatsApp Cloud API dispatch here

    async def create_near_expiry_notification(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        batch_id: uuid.UUID,
        product_name: str,
        days_remaining: int,
    ) -> Notification:
        if days_remaining <= 30:
            ntype = NotificationType.NEAR_EXPIRY_30
            title = f"Critical: {product_name} expires in {days_remaining} days"
            title_ar = f"تحذير: {product_name} ينتهي خلال {days_remaining} يوم"
        elif days_remaining <= 90:
            ntype = NotificationType.NEAR_EXPIRY_90
            title = f"Warning: {product_name} expires in {days_remaining} days"
            title_ar = f"تنبيه: {product_name} ينتهي خلال {days_remaining} يوم"
        else:
            ntype = NotificationType.NEAR_EXPIRY_180
            title = f"Notice: {product_name} expires in {days_remaining} days"
            title_ar = f"ملاحظة: {product_name} ينتهي خلال {days_remaining} يوم"

        return await self.create(
            user_id=user_id,
            notification_type=ntype,
            title=title,
            title_ar=title_ar,
            body=f"The batch for {product_name} will expire in {days_remaining} days. Consider listing it on the marketplace.",
            body_ar=f"دفعة {product_name} ستنتهي خلال {days_remaining} يوم. فكر في إدراجها في السوق.",
            organization_id=org_id,
            resource_type="inventory_batch",
            resource_id=batch_id,
        )
