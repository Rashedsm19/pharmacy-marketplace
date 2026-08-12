"""Allow re-reserving a listing after a reservation is cancelled or expires

Replaces the blanket UNIQUE(listing_id) on reservations with a partial unique
index covering only active reservations. The old constraint made a listing
permanently unsellable once any reservation on it was cancelled.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("reservations_listing_id_key", "reservations", type_="unique")
    op.create_index(
        "uq_reservations_active_listing",
        "reservations",
        ["listing_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_reservations_active_listing", table_name="reservations")
    op.create_unique_constraint(
        "reservations_listing_id_key", "reservations", ["listing_id"]
    )
