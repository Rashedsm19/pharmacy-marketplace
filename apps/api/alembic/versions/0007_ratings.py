"""Counterparty ratings

In a market between strangers, reputation is what makes the first trade
possible. Nothing recorded it.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rater_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rated_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rated_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["rater_organization_id"], ["pharmacy_organizations.id"]),
        sa.ForeignKeyConstraint(["rated_organization_id"], ["pharmacy_organizations.id"]),
        sa.ForeignKeyConstraint(["rated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_ratings_score_range"),
    )
    op.create_index("ix_ratings_transaction_id", "ratings", ["transaction_id"])
    op.create_index("ix_ratings_rater_organization_id", "ratings", ["rater_organization_id"])
    op.create_index("ix_ratings_rated_organization_id", "ratings", ["rated_organization_id"])
    # One rating per transaction per rating organization.
    op.create_index(
        "uq_ratings_transaction_rater",
        "ratings",
        ["transaction_id", "rater_organization_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ratings_transaction_rater", table_name="ratings")
    op.drop_index("ix_ratings_rated_organization_id", table_name="ratings")
    op.drop_index("ix_ratings_rater_organization_id", table_name="ratings")
    op.drop_index("ix_ratings_transaction_id", table_name="ratings")
    op.drop_table("ratings")
