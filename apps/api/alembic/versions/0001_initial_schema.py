"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-03-28 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: models use plain String columns for status fields, so the migration
    # uses VARCHAR(50) instead of native postgres ENUM types to avoid type
    # mismatch with the async driver.

    # ── Tables ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_reset_token", sa.String(255), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "pharmacy_organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=True),
        sa.Column("commercial_registration_number", sa.String(100), nullable=False, unique=True),
        sa.Column("license_number", sa.String(100), nullable=True, unique=True),
        sa.Column("is_licensed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("license_doc_url", sa.String(500), nullable=True),
        sa.Column("cr_doc_url", sa.String(500), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        sa.Column("allow_auto_listing", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "user_organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_memberships_user_id", "user_organization_memberships", ["user_id"])
    op.create_index("ix_memberships_org_id", "user_organization_memberships", ["organization_id"])

    op.create_table(
        "pharmacy_branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=True),
        sa.Column("branch_code", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("manager_name", sa.String(255), nullable=True),
        sa.Column("storage_condition_status", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("storage_notes", sa.Text(), nullable=True),
        sa.Column("cold_chain_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("narcotics_license", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_branches_org_id", "pharmacy_branches", ["organization_id"])

    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_exchange_allowed_default", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requires_cold_chain", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False, unique=True),
        sa.Column("barcode", sa.String(100), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("manufacturer_ar", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(50), nullable=False, server_default="unit"),
        sa.Column("unit_ar", sa.String(50), nullable=False, server_default="وحدة"),
        sa.Column("standard_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_controlled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("requires_prescription", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_barcode", "products", ["barcode"])

    op.create_table(
        "inventory_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_branches.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("supplier", sa.String(255), nullable=True),
        sa.Column("purchase_order_number", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("is_opened", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_patient_dispensed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("storage_condition_status", sa.String(50), nullable=False, server_default="compliant"),
        sa.Column("storage_notes", sa.Text(), nullable=True),
        sa.Column("requires_cold_chain", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("notified_180", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notified_90", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notified_30", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batches_org_id", "inventory_batches", ["organization_id"])
    op.create_index("ix_batches_branch_id", "inventory_batches", ["branch_id"])
    op.create_index("ix_batches_product_id", "inventory_batches", ["product_id"])
    op.create_index("ix_batches_expiry_date", "inventory_batches", ["expiry_date"])
    op.create_index("ix_batches_status", "inventory_batches", ["status"])

    op.create_table(
        "near_expiry_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("min_days_for_listing", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("yellow_threshold_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("orange_threshold_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("red_threshold_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("allow_auto_listing", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("auto_listing_discount_pct", sa.Numeric(5, 2), nullable=False, server_default="20.0"),
        sa.Column("notify_owner", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "marketplace_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("seller_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_branches.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_batches.id"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("title_ar", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity_listed", sa.Integer(), nullable=False),
        sa.Column("quantity_available", sa.Integer(), nullable=False),
        sa.Column("asking_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("minimum_offer_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("allow_offers", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_partial_purchase", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("min_purchase_quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligibility_passed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("eligibility_result", sa.Text(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_listings_seller_org_id", "marketplace_listings", ["seller_organization_id"])
    op.create_index("ix_listings_status", "marketplace_listings", ["status"])
    op.create_index("ix_listings_batch_id", "marketplace_listings", ["batch_id"])

    op.create_table(
        "listing_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=False),
        sa.Column("viewer_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=True),
        sa.Column("viewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_listing_views_listing_id", "listing_views", ["listing_id"])

    op.create_table(
        "listing_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=False),
        sa.Column("buyer_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("offered_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("seller_note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_offers_listing_id", "listing_offers", ["listing_id"])
    op.create_index("ix_offers_buyer_org_id", "listing_offers", ["buyer_organization_id"])
    op.create_index("ix_offers_status", "listing_offers", ["status"])

    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=False, unique=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("listing_offers.id"), nullable=True),
        sa.Column("buyer_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("reserved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("agreed_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reservations_listing_id", "reservations", ["listing_id"])
    op.create_index("ix_reservations_buyer_org_id", "reservations", ["buyer_organization_id"])

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=False, unique=True),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reservations.id"), nullable=True),
        sa.Column("seller_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("buyer_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("reference_number", sa.String(100), nullable=False, unique=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("delivery_tracking_number", sa.String(100), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seller_notes", sa.Text(), nullable=True),
        sa.Column("buyer_notes", sa.Text(), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_seller_org_id", "transactions", ["seller_organization_id"])
    op.create_index("ix_transactions_buyer_org_id", "transactions", ["buyer_organization_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_batches.id"), nullable=False),
        sa.Column("movement_type", sa.String(50), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("quantity_before", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_movements_batch_id", "inventory_movements", ["batch_id"])
    op.create_index("ix_movements_org_id", "inventory_movements", ["organization_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_organizations.id"), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("title_ar", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_ar", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["notification_type"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notif_prefs_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "platform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False, server_default="general"),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_platform_settings_key", "platform_settings", ["key"])


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("inventory_movements")
    op.drop_table("transactions")
    op.drop_table("reservations")
    op.drop_table("listing_offers")
    op.drop_table("listing_views")
    op.drop_table("marketplace_listings")
    op.drop_table("near_expiry_rules")
    op.drop_table("inventory_batches")
    op.drop_table("products")
    op.drop_table("product_categories")
    op.drop_table("pharmacy_branches")
    op.drop_table("user_organization_memberships")
    op.drop_table("pharmacy_organizations")
    op.drop_table("users")

    for enum_name in [
        "user_role", "organization_status", "membership_role",
        "storage_condition_status", "batch_status", "movement_type",
        "listing_status", "offer_status", "reservation_status",
        "transaction_status", "notification_type", "notification_channel",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
