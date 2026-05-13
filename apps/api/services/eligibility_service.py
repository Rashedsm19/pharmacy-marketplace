"""
Marketplace eligibility engine.
Enforces all 10 eligibility rules before allowing a listing to be created.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.inventory import InventoryBatchRepository, NearExpiryRuleRepository
from repositories.branch import BranchRepository
from repositories.organization import OrganizationRepository
from repositories.product import ProductRepository
from models.organization import OrganizationStatus
from schemas.marketplace import EligibilityResult, EligibilityRuleResult


class EligibilityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.branch_repo = BranchRepository(db)
        self.batch_repo = InventoryBatchRepository(db)
        self.product_repo = ProductRepository(db)
        self.rule_repo = NearExpiryRuleRepository(db)

    async def check_listing_eligibility(
        self, batch_id: uuid.UUID, org_id: uuid.UUID
    ) -> EligibilityResult:
        rules: list[EligibilityRuleResult] = []

        # Load all required entities
        org = await self.org_repo.get_active(org_id)
        batch = await self.batch_repo.get_by_org(batch_id, org_id)

        if not batch:
            return EligibilityResult(
                all_passed=False,
                rules=[
                    EligibilityRuleResult(
                        rule_number=0,
                        rule_name="Batch Access",
                        passed=False,
                        reason="Batch not found or does not belong to this organization",
                    )
                ],
            )

        branch = await self.branch_repo.get_by_org(batch.branch_id, org_id)
        near_expiry_rule = await self.rule_repo.get_by_org(org_id)

        # Load product directly (no org scope)
        from sqlalchemy import select
        from models.product import Product
        result = await self.db.execute(
            select(Product).where(Product.id == batch.product_id, Product.deleted_at.is_(None))
        )
        product = result.scalar_one_or_none()

        # Load product category
        from models.product import ProductCategory
        category = None
        if product:
            result = await self.db.execute(
                select(ProductCategory).where(ProductCategory.id == product.category_id)
            )
            category = result.scalar_one_or_none()

        today = date.today()

        # Rule 1 — Organization status == approved
        rules.append(EligibilityRuleResult(
            rule_number=1,
            rule_name="Organization Status",
            passed=org is not None and org.status == OrganizationStatus.APPROVED,
            reason=None if (org and org.status == OrganizationStatus.APPROVED)
            else f"Organization status is '{org.status if org else 'not found'}', must be 'approved'",
        ))

        # Rule 2 — Organization is_licensed == True
        rules.append(EligibilityRuleResult(
            rule_number=2,
            rule_name="Organization Licensed",
            passed=org is not None and org.is_licensed,
            reason=None if (org and org.is_licensed)
            else "Organization does not have a valid pharmacy license",
        ))

        # Rule 3 — Branch is_active == True
        rules.append(EligibilityRuleResult(
            rule_number=3,
            rule_name="Branch Active",
            passed=branch is not None and branch.is_active,
            reason=None if (branch and branch.is_active)
            else "Branch is inactive or not found",
        ))

        # Rule 4 — Product is_active and not restricted/controlled
        product_ok = (
            product is not None
            and product.is_active
            and not product.is_restricted
            and not product.is_controlled
        )
        rules.append(EligibilityRuleResult(
            rule_number=4,
            rule_name="Product Eligible",
            passed=product_ok,
            reason=None if product_ok else (
                "Product not found" if not product
                else "Product is inactive, restricted, or controlled"
            ),
        ))

        # Rule 5 — Batch is_opened == False
        rules.append(EligibilityRuleResult(
            rule_number=5,
            rule_name="Batch Not Opened",
            passed=not batch.is_opened,
            reason=None if not batch.is_opened else "Batch has been opened and cannot be listed",
        ))

        # Rule 6 — Batch is_patient_dispensed == False
        rules.append(EligibilityRuleResult(
            rule_number=6,
            rule_name="Not Patient Dispensed",
            passed=not batch.is_patient_dispensed,
            reason=None if not batch.is_patient_dispensed
            else "Batch has been dispensed to a patient and cannot be listed",
        ))

        # Rule 7 — storage_condition_status == compliant
        storage_ok = batch.storage_condition_status == "compliant"
        rules.append(EligibilityRuleResult(
            rule_number=7,
            rule_name="Storage Conditions Compliant",
            passed=storage_ok,
            reason=None if storage_ok
            else f"Storage condition is '{batch.storage_condition_status}', must be 'compliant'",
        ))

        # Rule 8 — expiry_date > today
        not_expired = batch.expiry_date > today
        rules.append(EligibilityRuleResult(
            rule_number=8,
            rule_name="Not Expired",
            passed=not_expired,
            reason=None if not_expired
            else f"Batch expired on {batch.expiry_date}",
        ))

        # Rule 9 — days until expiry >= min_days_for_listing
        days_remaining = (batch.expiry_date - today).days
        min_days = near_expiry_rule.min_days_for_listing if near_expiry_rule else 30
        min_days_ok = days_remaining >= min_days
        rules.append(EligibilityRuleResult(
            rule_number=9,
            rule_name="Minimum Days Until Expiry",
            passed=min_days_ok,
            reason=None if min_days_ok
            else f"Batch has {days_remaining} days until expiry; minimum required is {min_days} days",
        ))

        # Rule 10 — Category exchange allowed
        cat_ok = category is not None and category.is_exchange_allowed_default
        rules.append(EligibilityRuleResult(
            rule_number=10,
            rule_name="Category Exchange Allowed",
            passed=cat_ok,
            reason=None if cat_ok
            else "Product category does not allow marketplace exchange by default",
        ))

        all_passed = all(r.passed for r in rules)
        return EligibilityResult(all_passed=all_passed, rules=rules)
