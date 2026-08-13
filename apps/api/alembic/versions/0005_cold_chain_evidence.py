"""Cold chain evidence on transactions

requires_cold_chain existed on the batch with nothing proving the shipment
actually stayed cold between the two pharmacies.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions", sa.Column("temperature_log_url", sa.String(length=500), nullable=True)
    )
    op.add_column("transactions", sa.Column("min_temp_c", sa.Numeric(5, 2), nullable=True))
    op.add_column("transactions", sa.Column("max_temp_c", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "transactions",
        sa.Column(
            "temperature_excursion", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "temperature_excursion")
    op.drop_column("transactions", "max_temp_c")
    op.drop_column("transactions", "min_temp_c")
    op.drop_column("transactions", "temperature_log_url")
