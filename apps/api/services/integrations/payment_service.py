"""
Payment gateway adapter.

The wallet never talks to a gateway directly; it asks a `PaymentProvider` for a
checkout, and later learns the outcome through a signed webhook (or, with the
stub, through an explicit simulate call). Switching from the stub to mada via
HyperPay or Moyasar is an env change — `PAYMENT_BACKEND` — not a code change.
The real backends are declared so that switch fails loudly rather than
silently pretending money arrived.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol

from fastapi import HTTPException, status

from config import settings


@dataclass(frozen=True)
class CheckoutSession:
    provider: str
    provider_ref: str
    redirect_url: str
    # True when the caller may settle the session itself (stub only).
    simulate_available: bool


@dataclass(frozen=True)
class WebhookEvent:
    provider_ref: str
    status: str            # paid | failed
    amount: Decimal | None


class PaymentProvider(Protocol):
    name: str

    async def create_checkout(
        self, amount: Decimal, organization_id: uuid.UUID, reference: uuid.UUID
    ) -> CheckoutSession: ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent: ...

    async def capture(self, payment_id: str) -> None: ...

    async def refund(self, payment_id: str, amount: Decimal) -> None: ...


def _not_enabled(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"بوابة الدفع {name} غير مفعلة على هذا الخادم",
    )


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class StubPaymentProvider:
    """Settles nothing on its own: the caller simulates the gateway callback."""

    name = "stub"

    async def create_checkout(
        self, amount: Decimal, organization_id: uuid.UUID, reference: uuid.UUID
    ) -> CheckoutSession:
        ref = f"stub_{reference.hex}"
        return CheckoutSession(
            provider=self.name,
            provider_ref=ref,
            redirect_url=f"https://payments.stub.local/checkout/{ref}",
            simulate_available=True,
        )

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        secret = settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="لم يضبط سر التحقق من إشعارات الدفع على الخادم",
            )
        given = headers.get("x-payment-signature") or headers.get("X-Payment-Signature") or ""
        if not hmac.compare_digest(given, sign_payload(body, secret)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="توقيع إشعار الدفع غير صحيح"
            )
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="إشعار دفع غير مقروء")
        ref = str(payload.get("provider_ref") or "")
        if not ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="إشعار الدفع بلا مرجع")
        amount = payload.get("amount")
        return WebhookEvent(
            provider_ref=ref,
            status="paid" if payload.get("status", "paid") == "paid" else "failed",
            amount=Decimal(str(amount)) if amount is not None else None,
        )

    async def capture(self, payment_id: str) -> None:
        return None

    async def refund(self, payment_id: str, amount: Decimal) -> None:
        return None


class HyperPayProvider:
    name = "hyperpay"

    async def create_checkout(self, amount, organization_id, reference) -> CheckoutSession:
        raise _not_enabled("HyperPay")

    def verify_webhook(self, headers, body) -> WebhookEvent:
        raise _not_enabled("HyperPay")

    async def capture(self, payment_id: str) -> None:
        raise _not_enabled("HyperPay")

    async def refund(self, payment_id: str, amount: Decimal) -> None:
        raise _not_enabled("HyperPay")


class MoyasarProvider:
    name = "moyasar"

    async def create_checkout(self, amount, organization_id, reference) -> CheckoutSession:
        raise _not_enabled("Moyasar")

    def verify_webhook(self, headers, body) -> WebhookEvent:
        raise _not_enabled("Moyasar")

    async def capture(self, payment_id: str) -> None:
        raise _not_enabled("Moyasar")

    async def refund(self, payment_id: str, amount: Decimal) -> None:
        raise _not_enabled("Moyasar")


_PROVIDERS = {
    "stub": StubPaymentProvider,
    "hyperpay": HyperPayProvider,
    "moyasar": MoyasarProvider,
}


def get_payment_provider() -> PaymentProvider:
    backend = (settings.PAYMENT_BACKEND or "stub").lower()
    cls = _PROVIDERS.get(backend)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"PAYMENT_BACKEND={backend} غير معروف",
        )
    return cls()


def stub_enabled() -> bool:
    return (settings.PAYMENT_BACKEND or "stub").lower() == "stub"
