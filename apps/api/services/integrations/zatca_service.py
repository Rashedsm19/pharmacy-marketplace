"""
ZATCA e-invoicing.

Three modes selected by ZATCA_MODE:
  stub       — sign with a locally generated key and mark the invoice cleared.
               Everything except the network call is real, so the document, the
               QR payload and the hash chain can be verified without credentials.
  sandbox    — submit to ZATCA's simulation environment
  production — submit to the live clearance API

The parts that are fully specified by the standard — the TLV QR payload, the
SHA-256 hash chain, the UBL document — are implemented properly rather than
faked, because those are what break silently if approximated.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from config import settings

logger = logging.getLogger("api.zatca")

# The first invoice in a chain refers to the SHA-256 of "0", per the standard.
GENESIS_HASH = base64.b64encode(hashlib.sha256(b"0").digest()).decode()

SANDBOX_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation/invoices/clearance/single"
PRODUCTION_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/core/invoices/clearance/single"


def tlv(tag: int, value: str) -> bytes:
    """One tag-length-value field of the ZATCA QR payload."""
    encoded = value.encode("utf-8")
    return bytes([tag, len(encoded)]) + encoded


def build_qr(
    seller_name: str,
    vat_number: str,
    timestamp: datetime,
    total_with_vat: Decimal,
    vat_amount: Decimal,
) -> str:
    """The five mandatory QR fields, base64 encoded.

    Order is fixed by the specification: seller, VAT number, timestamp, total,
    VAT. A reader that expects tag 1 first will reject anything else.
    """
    payload = (
        tlv(1, seller_name)
        + tlv(2, vat_number)
        + tlv(3, timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        + tlv(4, f"{total_with_vat:.2f}")
        + tlv(5, f"{vat_amount:.2f}")
    )
    return base64.b64encode(payload).decode()


def parse_qr(encoded: str) -> dict[int, str]:
    """Decode a QR payload back into its tags — used by the tests and support."""
    raw = base64.b64decode(encoded)
    fields: dict[int, str] = {}
    index = 0
    while index < len(raw):
        tag = raw[index]
        length = raw[index + 1]
        fields[tag] = raw[index + 2 : index + 2 + length].decode("utf-8")
        index += 2 + length
    return fields


def hash_invoice(xml_content: str) -> str:
    return base64.b64encode(hashlib.sha256(xml_content.encode("utf-8")).digest()).decode()


class ZatcaService:
    """Builds, signs and clears tax invoices."""

    def __init__(self) -> None:
        self._key: ec.EllipticCurvePrivateKey | None = None

    # ── Signing key ───────────────────────────────────────────────────────
    def _signing_key(self) -> ec.EllipticCurvePrivateKey:
        """The CSID private key, or a generated one while running on stub data.

        ZATCA issues an secp256k1 key with the certificate; until that exists the
        service generates its own so the signature path is genuinely exercised
        rather than skipped.
        """
        if self._key is not None:
            return self._key

        key_path = settings.ZATCA_PRIVATE_KEY_PATH
        if key_path and Path(key_path).is_file():
            self._key = serialization.load_pem_private_key(
                Path(key_path).read_bytes(), password=None
            )
            logger.info("Loaded ZATCA signing key from %s", key_path)
        else:
            if settings.ZATCA_MODE != "stub":
                logger.error(
                    "ZATCA_MODE=%s but no private key at ZATCA_PRIVATE_KEY_PATH — "
                    "signing with a generated key, which the authority will reject",
                    settings.ZATCA_MODE,
                )
            self._key = ec.generate_private_key(ec.SECP256K1())
        return self._key

    def sign(self, invoice_hash: str) -> str:
        signature = self._signing_key().sign(
            invoice_hash.encode("utf-8"), ec.ECDSA(hashes.SHA256())
        )
        return base64.b64encode(signature).decode()

    # ── Document ──────────────────────────────────────────────────────────
    def build_xml(
        self,
        *,
        invoice_number: str,
        invoice_uuid: str,
        icv: int,
        previous_hash: str,
        issued_at: datetime,
        seller_name: str,
        seller_vat: str,
        buyer_name: str,
        buyer_vat: str | None,
        line_description: str,
        quantity: int,
        unit_price: Decimal,
        subtotal: Decimal,
        vat_rate: Decimal,
        vat_amount: Decimal,
        total_with_vat: Decimal,
    ) -> str:
        """A UBL 2.1 tax invoice carrying the fields ZATCA validates."""
        issued = issued_at.astimezone(timezone.utc)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
  <cbc:ID>{invoice_number}</cbc:ID>
  <cbc:UUID>{invoice_uuid}</cbc:UUID>
  <cbc:IssueDate>{issued:%Y-%m-%d}</cbc:IssueDate>
  <cbc:IssueTime>{issued:%H:%M:%S}</cbc:IssueTime>
  <cbc:InvoiceTypeCode name="0100000">388</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
  <cbc:TaxCurrencyCode>SAR</cbc:TaxCurrencyCode>
  <cac:AdditionalDocumentReference>
    <cbc:ID>ICV</cbc:ID>
    <cbc:UUID>{icv}</cbc:UUID>
  </cac:AdditionalDocumentReference>
  <cac:AdditionalDocumentReference>
    <cbc:ID>PIH</cbc:ID>
    <cac:Attachment>
      <cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">{previous_hash}</cbc:EmbeddedDocumentBinaryObject>
    </cac:Attachment>
  </cac:AdditionalDocumentReference>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{seller_vat}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity><cbc:RegistrationName>{seller_name}</cbc:RegistrationName></cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{buyer_vat or ""}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity><cbc:RegistrationName>{buyer_name}</cbc:RegistrationName></cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="SAR">{vat_amount:.2f}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="SAR">{subtotal:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="SAR">{vat_amount:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{vat_rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="SAR">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="SAR">{subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="SAR">{total_with_vat:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="SAR">{total_with_vat:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="PCE">{quantity}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="SAR">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>{line_description}</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="SAR">{unit_price:.2f}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""

    # ── Clearance ─────────────────────────────────────────────────────────
    async def clear(self, invoice_uuid: str, invoice_hash: str, xml_content: str) -> tuple[bool, str]:
        """Submit for clearance. Returns (accepted, response text)."""
        mode = (settings.ZATCA_MODE or "stub").lower()
        if mode == "stub":
            logger.info("ZATCA STUB → invoice %s treated as cleared", invoice_uuid)
            return True, '{"clearanceStatus": "CLEARED", "mode": "stub"}'

        url = SANDBOX_URL if mode == "sandbox" else PRODUCTION_URL
        if not settings.ZATCA_CSID or not settings.ZATCA_SECRET:
            message = "ZATCA_CSID / ZATCA_SECRET are not configured"
            logger.error(message)
            return False, message

        from httpx_client import get_http_client

        credentials = base64.b64encode(
            f"{settings.ZATCA_CSID}:{settings.ZATCA_SECRET}".encode()
        ).decode()
        try:
            client = get_http_client()
            response = await client.post(
                url,
                json={
                    "invoiceHash": invoice_hash,
                    "uuid": invoice_uuid,
                    "invoice": base64.b64encode(xml_content.encode("utf-8")).decode(),
                },
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Accept-Version": "V2",
                    "Accept-Language": "en",
                },
                timeout=30.0,
            )
            accepted = response.status_code in (200, 202)
            if not accepted:
                logger.error("ZATCA rejected %s (%s)", invoice_uuid, response.status_code)
            return accepted, response.text[:4000]
        except Exception as exc:  # noqa: BLE001 — clearance must not break the sale
            logger.error("ZATCA clearance call failed for %s: %s", invoice_uuid, exc)
            return False, str(exc)[:1000]


zatca_service = ZatcaService()
