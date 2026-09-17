"""
One place for money arithmetic.

Every amount in the database is Numeric(12, 2) in riyals. SQLAlchemy hands it
back as Decimal, request bodies arrive as float or str, and a float multiplied
by a Decimal raises — which once took the whole near-expiry job down. Route all
conversions through here so the rounding rule (half up, to the halala) is the
same everywhere a customer could compare two numbers.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

HALALA = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value: object) -> Decimal:
    """Coerce any numeric-ish value into a Decimal rounded to two places."""
    if value is None:
        return ZERO
    if isinstance(value, bool):
        raise TypeError("a boolean is not an amount")
    try:
        return Decimal(str(value)).quantize(HALALA, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not an amount: {value!r}") from exc


def pct_of(amount: object, pct: object) -> Decimal:
    """`pct` percent of `amount`, rounded to the halala."""
    return (Decimal(str(amount)) * Decimal(str(pct)) / Decimal("100")).quantize(
        HALALA, rounding=ROUND_HALF_UP
    )


def times(unit: object, quantity: int) -> Decimal:
    return (Decimal(str(unit)) * Decimal(int(quantity))).quantize(
        HALALA, rounding=ROUND_HALF_UP
    )
