"""
WhatsApp delivery.

Two backends selected by WHATSAPP_BACKEND:
  stub — logs and drops the message (default; local dev and tests)
  meta — Meta WhatsApp Cloud API, via the shared httpx client

Same rule as email: delivery never raises. A message that cannot be sent must
not roll back the business transaction that produced it.
"""
from __future__ import annotations

import logging
import re

from config import settings

logger = logging.getLogger("api.whatsapp")

_META_GRAPH = "https://graph.facebook.com/v20.0"


def normalize_saudi_phone(raw: str | None) -> str | None:
    """Return an E.164 number without the plus sign, or None if unusable.

    Accepts the forms staff actually type: 05xxxxxxxx, 5xxxxxxxx, 9665xxxxxxxx,
    +9665xxxxxxxx, with spaces or dashes in between.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("05") and len(digits) == 10:
        digits = "966" + digits[1:]
    elif digits.startswith("5") and len(digits) == 9:
        digits = "966" + digits
    if digits.startswith("966") and len(digits) == 12:
        return digits
    return None


class WhatsAppService:
    async def send(self, to_phone: str | None, body: str) -> bool:
        """Returns True when the message was handed to a provider."""
        backend = (settings.WHATSAPP_BACKEND or "stub").lower()
        number = normalize_saudi_phone(to_phone)
        if number is None:
            logger.debug("WhatsApp skipped: no usable phone (%r)", to_phone)
            return False
        try:
            if backend == "meta":
                return await self._send_meta(number, body)
            logger.info("WHATSAPP STUB → to=%s body=%s", number, body[:80])
            return False
        except Exception as exc:  # noqa: BLE001 — delivery must never break the caller
            logger.error("WhatsApp delivery failed (backend=%s, to=%s): %s", backend, number, exc)
            return False

    async def _send_meta(self, number: str, body: str) -> bool:
        if not settings.META_WHATSAPP_ACCESS_TOKEN or not settings.META_WHATSAPP_PHONE_NUMBER_ID:
            logger.error("WHATSAPP_BACKEND=meta but the Meta token or phone number id is empty")
            return False

        from httpx_client import get_http_client

        client = get_http_client()
        response = await client.post(
            f"{_META_GRAPH}/{settings.META_WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {settings.META_WHATSAPP_ACCESS_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": number,
                "type": "text",
                "text": {"preview_url": False, "body": body},
            },
            timeout=10.0,
        )
        if response.status_code >= 400:
            logger.error("Meta WhatsApp rejected the message: %s %s", response.status_code, response.text[:300])
            return False
        return True


whatsapp_service = WhatsAppService()
