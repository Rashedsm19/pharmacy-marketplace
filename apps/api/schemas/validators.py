"""
Shared validation for regulatory identifiers.

These are checked in one place because the same rules apply wherever the numbers
are accepted — registration, profile editing and admin correction.
"""
from __future__ import annotations

import re

VAT_PATTERN = re.compile(r"^3\d{13}3$")


def normalise_optional(value: str | None) -> str | None:
    """Blank optional input arrives as "", which must not reach the database."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def validate_vat_number(value: str | None) -> str | None:
    """Saudi VAT numbers are 15 digits that begin and end with 3."""
    value = normalise_optional(value)
    if value is None:
        return None
    compact = value.replace(" ", "").replace("-", "")
    if not VAT_PATTERN.match(compact):
        raise ValueError("الرقم الضريبي يجب أن يكون ١٥ رقماً يبدأ وينتهي بالرقم ٣")
    return compact


def validate_gln(value: str | None) -> str | None:
    """A GS1 Global Location Number: 13 digits with a mod-10 check digit."""
    value = normalise_optional(value)
    if value is None:
        return None
    compact = value.replace(" ", "").replace("-", "")
    if not compact.isdigit() or len(compact) != 13:
        raise ValueError("رقم الموقع العالمي GLN يجب أن يكون ١٣ رقماً")

    # GS1 check digit: weight the first 12 digits 3,1,3,1… from the right.
    digits = [int(d) for d in compact]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits[:12]), start=1))
    if (10 - total % 10) % 10 != digits[12]:
        raise ValueError("رقم الموقع العالمي GLN غير صالح — رقم التحقق لا يطابق")
    return compact
