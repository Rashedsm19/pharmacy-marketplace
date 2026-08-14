"""
Email delivery.

Three backends selected by EMAIL_BACKEND:
  stub   — logs and drops the message (default; used by tests and local dev)
  resend — Resend HTTP API, via the shared httpx client
  smtp   — plain SMTP, run off the event loop in a worker thread

Delivery never raises: a message that cannot be sent must not roll back the
business transaction that triggered it. Failures are logged and reported back
so the caller can decide whether to surface anything.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger("api.email")


class EmailService:
    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> bool:
        """Returns True when the message was handed to a provider."""
        backend = (settings.EMAIL_BACKEND or "stub").lower()
        try:
            if backend == "resend":
                return await self._send_resend(to, subject, body_text, body_html)
            if backend == "smtp":
                return await asyncio.to_thread(
                    self._send_smtp, to, subject, body_text, body_html
                )
            logger.info("EMAIL STUB → to=%s subject=%s", to, subject)
            return False
        except Exception as exc:  # noqa: BLE001 — delivery must never break the caller
            logger.error("Email delivery failed (backend=%s, to=%s): %s", backend, to, exc)
            return False

    async def _send_resend(
        self, to: str, subject: str, body_text: str, body_html: str | None
    ) -> bool:
        if not settings.RESEND_API_KEY:
            logger.error("EMAIL_BACKEND=resend but RESEND_API_KEY is empty")
            return False

        from httpx_client import get_http_client

        payload: dict[str, object] = {
            "from": settings.EMAIL_FROM,
            "to": [to],
            "subject": subject,
            "text": body_text,
        }
        if body_html:
            payload["html"] = body_html

        client = get_http_client()
        response = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            timeout=15.0,
        )
        if response.status_code >= 400:
            logger.error("Resend rejected the message (%s): %s", response.status_code, response.text[:300])
            return False
        logger.info("Email sent via Resend → to=%s subject=%s", to, subject)
        return True

    def _send_smtp(
        self, to: str, subject: str, body_text: str, body_html: str | None
    ) -> bool:
        message = EmailMessage()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        logger.info("Email sent via SMTP → to=%s subject=%s", to, subject)
        return True


email_service = EmailService()


def password_reset_email(full_name: str, token: str) -> tuple[str, str, str]:
    """Subject, plain body and HTML body for the reset link."""
    link = f"{settings.FRONTEND_URL.rstrip('/')}/ar/reset-password?token={token}"
    subject = "إعادة تعيين كلمة المرور — MedSave"
    text = (
        f"مرحبا {full_name}،\n\n"
        "وصلنا طلب لإعادة تعيين كلمة مرور حسابك في منصة MedSave.\n"
        f"افتح الرابط التالي لتعيين كلمة مرور جديدة:\n\n{link}\n\n"
        "الرابط صالح لمدة ساعة واحدة. إن لم تطلب ذلك فتجاهل هذه الرسالة، "
        "ولن يطرأ أي تغيير على حسابك.\n\n"
        "منصة MedSave لتداول مخزون الصيدليات"
    )
    html = f"""<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;line-height:1.9;color:#1F2823">
  <p>مرحبا {full_name}،</p>
  <p>وصلنا طلب لإعادة تعيين كلمة مرور حسابك في منصة <strong>MedSave</strong>.</p>
  <p style="margin:26px 0">
    <a href="{link}" style="background:#0AA39B;color:#fff;text-decoration:none;
       padding:12px 26px;border-radius:10px;display:inline-block;font-weight:700">
      تعيين كلمة مرور جديدة
    </a>
  </p>
  <p style="font-size:13px;color:#55605B">
    الرابط صالح لمدة ساعة واحدة. إن لم تطلب ذلك فتجاهل هذه الرسالة،
    ولن يطرأ أي تغيير على حسابك.
  </p>
  <p style="font-size:12px;color:#8A938E">منصة MedSave لتداول مخزون الصيدليات</p>
</div>"""
    return subject, text, html
