"""
Smart re-stock and near-expiry listing intelligence.

A transparent analytical engine — no ML, no LLM, no invented numbers. Demand
comes only from `dispensed` inventory movements (marketplace `sold` /
`transferred` rows are inter-pharmacy transfers, never consumption). When the
evidence is too thin the recommendation says so (insufficient → HOLD, quantity
zero) instead of guessing.

Tunables live in platform_settings and are read on every run:
    restock.demand_window_days        (90)   velocity lookback
    restock.lead_time_days            (7)    supplier lead time fallback
    restock.safety_stock_days         (7)
    restock.review_period_days        (14)
    restock.min_evidence_days         (14)   dispensing history span floor
    restock.min_buy_shelf_life_days   (60)   marketplace match shelf-life floor
    restock.dismiss_cooldown_days     (7)    dismissed rows stay dismissed
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.inventory import BatchStatus, InventoryBatch, InventoryMovement, MovementType
from models.marketplace import (
    ListingStatus,
    MarketplaceListing,
    Reservation,
    ReservationStatus,
)
from models.notification import NotificationType
from models.organization import MembershipRole, UserOrganizationMembership
from models.product import Product
from models.restock import (
    EvidenceStrength,
    RecommendationStatus,
    RestockAction,
    RestockKind,
    RestockRecommendation,
)
from models.transaction import Transaction, TransactionStatus
from repositories.inventory import NearExpiryRuleRepository
from repositories.restock import RestockRecommendationRepository
from schemas.marketplace import ListingCreate
from services import settings_reader
from services.audit_service import AuditService
from services.listing_service import ListingService
from services.money import to_money
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

DEFAULT_DEMAND_WINDOW_DAYS = 90
DEFAULT_LEAD_TIME_DAYS = 7
DEFAULT_SAFETY_STOCK_DAYS = 7
DEFAULT_REVIEW_PERIOD_DAYS = 14
DEFAULT_MIN_EVIDENCE_DAYS = 14
DEFAULT_MIN_BUY_SHELF_LIFE_DAYS = 60
DEFAULT_DISMISS_COOLDOWN_DAYS = 7
PRICE_EVIDENCE_WINDOW_DAYS = 180

LIVE_LISTING_STATUSES = (ListingStatus.DRAFT, ListingStatus.ACTIVE, ListingStatus.RESERVED)
IN_FLIGHT_TRANSACTION_STATUSES = (
    TransactionStatus.PENDING,
    TransactionStatus.DISPATCHED,
    TransactionStatus.IN_TRANSIT,
)

_TERMINAL_STATUSES = (RecommendationStatus.ACTED, RecommendationStatus.ACCEPTED)


def _expiry_zone(days: int) -> str:
    if days > 180:
        return "green"
    if days > 90:
        return "yellow"
    if days > 30:
        return "orange"
    return "red"


def _signature(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class _Tunables:
    demand_window_days: int
    lead_time_days: int
    safety_stock_days: int
    review_period_days: int
    min_evidence_days: int
    min_buy_shelf_life_days: int
    dismiss_cooldown_days: int


@dataclass
class _DemandProfile:
    dispensed_total: int
    span_days: int | None
    velocity: Decimal
    evidence: EvidenceStrength
    missing: str | None


@dataclass
class _RecData:
    branch_id: uuid.UUID
    product_id: uuid.UUID
    kind: RestockKind
    action: RestockAction
    evidence_strength: EvidenceStrength
    demand_window_days: int
    daily_velocity: Decimal
    on_hand_qty: int
    incoming_qty: int
    days_of_cover: Decimal | None
    suggested_qty: int
    suggested_price: Decimal | None
    nearest_expiry_date: date | None
    expiry_zone: str
    batch_id: uuid.UUID | None
    market_median_price: Decimal | None
    matched_listing_id: uuid.UUID | None
    reason_ar: str
    reason_en: str
    inputs: dict


class RestockService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RestockRecommendationRepository(db)
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ── Tunables ──────────────────────────────────────────────────────────

    async def _tunables(self) -> _Tunables:
        db = self.db
        return _Tunables(
            demand_window_days=await settings_reader.get_int(
                db, "restock.demand_window_days", DEFAULT_DEMAND_WINDOW_DAYS
            ),
            lead_time_days=await settings_reader.get_int(
                db, "restock.lead_time_days", DEFAULT_LEAD_TIME_DAYS
            ),
            safety_stock_days=await settings_reader.get_int(
                db, "restock.safety_stock_days", DEFAULT_SAFETY_STOCK_DAYS
            ),
            review_period_days=await settings_reader.get_int(
                db, "restock.review_period_days", DEFAULT_REVIEW_PERIOD_DAYS
            ),
            min_evidence_days=await settings_reader.get_int(
                db, "restock.min_evidence_days", DEFAULT_MIN_EVIDENCE_DAYS
            ),
            min_buy_shelf_life_days=await settings_reader.get_int(
                db, "restock.min_buy_shelf_life_days", DEFAULT_MIN_BUY_SHELF_LIFE_DAYS
            ),
            dismiss_cooldown_days=await settings_reader.get_int(
                db, "restock.dismiss_cooldown_days", DEFAULT_DISMISS_COOLDOWN_DAYS
            ),
        )

    # ── Evidence queries ──────────────────────────────────────────────────

    async def _demand_profile(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID,
        product_id: uuid.UUID,
        tun: _Tunables,
        now: datetime,
    ) -> _DemandProfile:
        cutoff = now - timedelta(days=tun.demand_window_days)
        total, first, last = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(func.abs(InventoryMovement.quantity_delta)), 0),
                    func.min(InventoryMovement.created_at),
                    func.max(InventoryMovement.created_at),
                )
                .join(InventoryBatch, InventoryMovement.batch_id == InventoryBatch.id)
                .where(
                    InventoryMovement.organization_id == org_id,
                    InventoryMovement.movement_type == MovementType.DISPENSED,
                    InventoryMovement.created_at >= cutoff,
                    InventoryBatch.branch_id == branch_id,
                    InventoryBatch.product_id == product_id,
                )
            )
        ).one()
        total = int(total or 0)
        velocity = (Decimal(total) / Decimal(tun.demand_window_days)).quantize(
            Decimal("0.001")
        )
        span = (last - first).days if first is not None and last is not None else None

        if total == 0:
            return _DemandProfile(total, span, velocity, EvidenceStrength.INSUFFICIENT, "no_history")
        if span is None or span < tun.min_evidence_days:
            return _DemandProfile(total, span, velocity, EvidenceStrength.INSUFFICIENT, "short_span")
        if span < tun.demand_window_days / 2:
            return _DemandProfile(total, span, velocity, EvidenceStrength.SPARSE, None)
        return _DemandProfile(total, span, velocity, EvidenceStrength.SUFFICIENT, None)

    async def _incoming_qty(self, org_id: uuid.UUID, product_id: uuid.UUID) -> int:
        reserved = await self.db.scalar(
            select(func.coalesce(func.sum(Reservation.quantity), 0))
            .join(MarketplaceListing, Reservation.listing_id == MarketplaceListing.id)
            .join(InventoryBatch, MarketplaceListing.batch_id == InventoryBatch.id)
            .where(
                Reservation.buyer_organization_id == org_id,
                Reservation.status == ReservationStatus.ACTIVE,
                InventoryBatch.product_id == product_id,
            )
        )
        in_flight = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.quantity), 0))
            .join(MarketplaceListing, Transaction.listing_id == MarketplaceListing.id)
            .join(InventoryBatch, MarketplaceListing.batch_id == InventoryBatch.id)
            .where(
                Transaction.buyer_organization_id == org_id,
                Transaction.status.in_(IN_FLIGHT_TRANSACTION_STATUSES),
                InventoryBatch.product_id == product_id,
            )
        )
        return int(reserved or 0) + int(in_flight or 0)

    async def _match_listing(
        self,
        org_id: uuid.UUID,
        product_id: uuid.UUID,
        today: date,
        min_shelf_days: int,
    ) -> MarketplaceListing | None:
        shelf_floor = today + timedelta(days=min_shelf_days)
        return (
            await self.db.execute(
                select(MarketplaceListing)
                .join(InventoryBatch, MarketplaceListing.batch_id == InventoryBatch.id)
                .where(
                    InventoryBatch.product_id == product_id,
                    MarketplaceListing.seller_organization_id != org_id,
                    MarketplaceListing.status == ListingStatus.ACTIVE,
                    MarketplaceListing.quantity_available > 0,
                    MarketplaceListing.eligibility_passed.is_(True),
                    MarketplaceListing.deleted_at.is_(None),
                    InventoryBatch.expiry_date >= shelf_floor,
                )
                .options(selectinload(MarketplaceListing.batch))
                .order_by(MarketplaceListing.asking_price.asc(), MarketplaceListing.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _market_median_price(
        self, product_id: uuid.UUID, now: datetime
    ) -> Decimal | None:
        cutoff = now - timedelta(days=PRICE_EVIDENCE_WINDOW_DAYS)
        median = await self.db.scalar(
            select(func.percentile_cont(0.5).within_group(Transaction.unit_price))
            .join(MarketplaceListing, Transaction.listing_id == MarketplaceListing.id)
            .join(InventoryBatch, MarketplaceListing.batch_id == InventoryBatch.id)
            .where(
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.completed_at >= cutoff,
                InventoryBatch.product_id == product_id,
            )
        )
        return None if median is None else to_money(median)

    # ── Recommendation builders ───────────────────────────────────────────

    def _base_inputs(self, tun: _Tunables, demand: _DemandProfile, usable: int, incoming: int) -> dict:
        return {
            "demand_window_days": tun.demand_window_days,
            "lead_time_days": tun.lead_time_days,
            "safety_stock_days": tun.safety_stock_days,
            "review_period_days": tun.review_period_days,
            "min_evidence_days": tun.min_evidence_days,
            "dispensed_total": demand.dispensed_total,
            "evidence_span_days": demand.span_days,
            "daily_velocity": str(demand.velocity),
            "usable_qty": usable,
            "incoming_qty": incoming,
        }

    async def _build_replenishment(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID,
        product_id: uuid.UUID,
        combo: list[InventoryBatch],
        live_by_batch: dict[uuid.UUID, int],
        tun: _Tunables,
        today: date,
        now: datetime,
    ) -> _RecData:
        demand = await self._demand_profile(org_id, branch_id, product_id, tun, now)
        unexpired = [b for b in combo if b.expiry_date > today]
        usable = sum(max(0, b.quantity_available - live_by_batch.get(b.id, 0)) for b in unexpired)
        incoming = await self._incoming_qty(org_id, product_id)

        nearest = min((b.expiry_date for b in unexpired), default=None)
        zone = _expiry_zone((nearest - today).days) if nearest else "green"
        cover = (
            (Decimal(usable) / demand.velocity).quantize(Decimal("0.1"))
            if demand.velocity > 0
            else None
        )
        inputs = self._base_inputs(tun, demand, usable, incoming)

        if demand.evidence == EvidenceStrength.INSUFFICIENT:
            if demand.missing == "no_history":
                reason_ar = (
                    "لا توجد حركات صرف مسجلة لهذا المنتج في هذا الفرع خلال "
                    f"{tun.demand_window_days} يوم — سجّل حركات الصرف لتفعيل توصية التوريد"
                )
                reason_en = (
                    f"No dispensing history for this product at this branch in the last "
                    f"{tun.demand_window_days} days — record dispensed movements to enable "
                    "a restock recommendation."
                )
            else:
                reason_ar = (
                    f"سجل الصرف يغطي {demand.span_days or 0} يوم فقط والحد الأدنى "
                    f"{tun.min_evidence_days} يوم — استمر في تسجيل الصرف"
                )
                reason_en = (
                    f"Dispensing history spans only {demand.span_days or 0} days "
                    f"(minimum {tun.min_evidence_days}) — keep recording dispensing."
                )
            inputs["hold_reason"] = demand.missing
            return _RecData(
                branch_id=branch_id, product_id=product_id, kind=RestockKind.REPLENISHMENT,
                action=RestockAction.HOLD, evidence_strength=demand.evidence,
                demand_window_days=tun.demand_window_days, daily_velocity=demand.velocity,
                on_hand_qty=usable, incoming_qty=incoming, days_of_cover=cover,
                suggested_qty=0, suggested_price=None,
                nearest_expiry_date=nearest, expiry_zone=zone,
                batch_id=None, market_median_price=None, matched_listing_id=None,
                reason_ar=reason_ar, reason_en=reason_en, inputs=inputs,
            )

        reorder_point = Decimal(tun.lead_time_days + tun.safety_stock_days) * demand.velocity
        target = (
            Decimal(tun.lead_time_days + tun.safety_stock_days + tun.review_period_days)
            * demand.velocity
        )
        inputs["reorder_point"] = str(reorder_point.quantize(Decimal("0.001")))
        inputs["target_stock"] = str(target.quantize(Decimal("0.001")))
        raw = target - Decimal(usable) - Decimal(incoming)

        if raw <= 0:
            reason_ar = "المخزون الحالي يغطي فترة التوريد والأمان — لا حاجة لإعادة الطلب الآن"
            reason_en = "Current stock covers lead time and safety stock — no reorder needed now."
            return _RecData(
                branch_id=branch_id, product_id=product_id, kind=RestockKind.REPLENISHMENT,
                action=RestockAction.HOLD, evidence_strength=demand.evidence,
                demand_window_days=tun.demand_window_days, daily_velocity=demand.velocity,
                on_hand_qty=usable, incoming_qty=incoming, days_of_cover=cover,
                suggested_qty=0, suggested_price=None,
                nearest_expiry_date=nearest, expiry_zone=zone,
                batch_id=None, market_median_price=None, matched_listing_id=None,
                reason_ar=reason_ar, reason_en=reason_en, inputs=inputs,
            )

        suggested = math.ceil(raw)
        listing = await self._match_listing(
            org_id, product_id, today, tun.min_buy_shelf_life_days
        )
        if listing is not None:
            shelf_days = (listing.batch.expiry_date - today).days
            expiry_cap = math.ceil(demand.velocity * shelf_days)
            suggested = max(0, min(suggested, expiry_cap, listing.quantity_available))
            inputs["matched_listing_id"] = str(listing.id)
            inputs["matched_listing_qty_available"] = listing.quantity_available
            inputs["matched_listing_shelf_days"] = shelf_days
            inputs["expiry_cap_qty"] = expiry_cap
            price = to_money(listing.asking_price)
            reason_ar = (
                f"المخزون يغطي {cover} يوم — يتوفر عرض في السوق بسعر {price} ر.س "
                f"وصلاحية {shelf_days} يوم"
            )
            reason_en = (
                f"Stock covers {cover} days — a marketplace listing is available at "
                f"{price} SAR/unit with {shelf_days} days of shelf life."
            )
            return _RecData(
                branch_id=branch_id, product_id=product_id, kind=RestockKind.REPLENISHMENT,
                action=RestockAction.BUY_FROM_MARKETPLACE, evidence_strength=demand.evidence,
                demand_window_days=tun.demand_window_days, daily_velocity=demand.velocity,
                on_hand_qty=usable, incoming_qty=incoming, days_of_cover=cover,
                suggested_qty=suggested, suggested_price=price,
                nearest_expiry_date=nearest, expiry_zone=zone,
                batch_id=None, market_median_price=None, matched_listing_id=listing.id,
                reason_ar=reason_ar, reason_en=reason_en, inputs=inputs,
            )

        reason_ar = "لا يوجد عرض مطابق في السوق بهذه الصلاحية — أعد الطلب من المورد"
        reason_en = (
            "No eligible marketplace listing matches this product — reorder from your supplier."
        )
        return _RecData(
            branch_id=branch_id, product_id=product_id, kind=RestockKind.REPLENISHMENT,
            action=RestockAction.REORDER_SUPPLIER, evidence_strength=demand.evidence,
            demand_window_days=tun.demand_window_days, daily_velocity=demand.velocity,
            on_hand_qty=usable, incoming_qty=incoming, days_of_cover=cover,
            suggested_qty=suggested, suggested_price=None,
            nearest_expiry_date=nearest, expiry_zone=zone,
            batch_id=None, market_median_price=None, matched_listing_id=None,
            reason_ar=reason_ar, reason_en=reason_en, inputs=inputs,
        )

    async def _build_listing(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID,
        product_id: uuid.UUID,
        combo: list[InventoryBatch],
        live_by_batch: dict[uuid.UUID, int],
        tun: _Tunables,
        today: date,
        now: datetime,
        rule,
    ) -> _RecData | None:
        qualifying = []
        for b in combo:
            if b.expiry_date <= today:
                continue
            if b.quantity_available <= 0:
                continue
            if live_by_batch.get(b.id, 0) > 0:
                continue
            days = (b.expiry_date - today).days
            if rule.min_days_for_listing <= days <= rule.yellow_threshold_days:
                qualifying.append(b)
        if not qualifying:
            return None

        batch = min(qualifying, key=lambda b: b.expiry_date)
        days_to_expiry = (batch.expiry_date - today).days
        available = batch.quantity_available
        demand = await self._demand_profile(org_id, branch_id, product_id, tun, now)
        inputs = self._base_inputs(tun, demand, available, 0)
        inputs["batch_id"] = str(batch.id)
        inputs["days_to_expiry"] = days_to_expiry

        if demand.evidence == EvidenceStrength.INSUFFICIENT:
            surplus = available
        else:
            surplus = int(
                math.ceil(max(Decimal(0), Decimal(available) - demand.velocity * days_to_expiry))
            )
        if surplus <= 0:
            return None
        inputs["surplus_basis"] = (
            "no_demand_data" if demand.evidence == EvidenceStrength.INSUFFICIENT else "velocity"
        )

        median = await self._market_median_price(product_id, now)
        product = await self.db.get(Product, product_id)
        discount = Decimal(str(rule.auto_listing_discount_pct or 0)) / Decimal("100")
        base_price: Decimal | None
        if median is not None:
            base_price, evidence_used = median, "market_median"
        elif product is not None and product.standard_price is not None:
            base_price, evidence_used = to_money(product.standard_price), "standard_price"
        else:
            base_price, evidence_used = None, "none"
        suggested_price = (
            to_money(base_price * (Decimal("1") - discount)) if base_price is not None else None
        )
        inputs["price_evidence"] = evidence_used
        inputs["price_evidence_value"] = str(base_price) if base_price is not None else None
        inputs["auto_listing_discount_pct"] = str(rule.auto_listing_discount_pct)

        reason_ar = (
            f"فائض {surplus} وحدة ينتهي خلال {days_to_expiry} يوم — "
            "أدرجه في السوق قبل انتهائه"
        )
        reason_en = (
            f"Surplus of {surplus} units expires in {days_to_expiry} days — "
            "list it on the marketplace before it expires."
        )
        if suggested_price is None:
            reason_ar += " — حدد سعر البيع يدوياً لعدم توفر مرجع سعري"
            reason_en += " — set a price manually; no price evidence is available."

        return _RecData(
            branch_id=branch_id, product_id=product_id, kind=RestockKind.LISTING,
            action=RestockAction.LIST_NOW, evidence_strength=demand.evidence,
            demand_window_days=tun.demand_window_days, daily_velocity=demand.velocity,
            on_hand_qty=available, incoming_qty=0,
            days_of_cover=(
                (Decimal(available) / demand.velocity).quantize(Decimal("0.1"))
                if demand.velocity > 0
                else None
            ),
            suggested_qty=surplus, suggested_price=suggested_price,
            nearest_expiry_date=batch.expiry_date, expiry_zone=_expiry_zone(days_to_expiry),
            batch_id=batch.id, market_median_price=median, matched_listing_id=None,
            reason_ar=reason_ar, reason_en=reason_en, inputs=inputs,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _signature_payload(self, data: _RecData) -> dict:
        return {
            "action": str(data.action),
            "suggested_qty": data.suggested_qty,
            "suggested_price": str(data.suggested_price),
            "on_hand_qty": data.on_hand_qty,
            "incoming_qty": data.incoming_qty,
            "daily_velocity": str(data.daily_velocity),
            "batch_id": str(data.batch_id),
            "matched_listing_id": str(data.matched_listing_id),
        }

    def _apply(self, row: RestockRecommendation, data: _RecData, now: datetime) -> None:
        row.action = data.action
        row.batch_id = data.batch_id
        row.evidence_strength = data.evidence_strength
        row.demand_window_days = data.demand_window_days
        row.incoming_qty = data.incoming_qty
        row.suggested_qty = data.suggested_qty
        row.suggested_price = data.suggested_price
        row.days_of_cover = data.days_of_cover
        row.daily_velocity = data.daily_velocity
        row.on_hand_qty = data.on_hand_qty
        row.nearest_expiry_date = data.nearest_expiry_date
        row.expiry_zone = data.expiry_zone
        row.market_median_price = data.market_median_price
        row.matched_listing_id = data.matched_listing_id
        row.inputs = data.inputs
        row.reason_ar = data.reason_ar
        row.reason_en = data.reason_en
        row.computed_at = now

    def _new_row(self, org_id: uuid.UUID, data: _RecData, now: datetime) -> RestockRecommendation:
        row = RestockRecommendation(
            id=uuid.uuid4(),
            organization_id=org_id,
            branch_id=data.branch_id,
            product_id=data.product_id,
            kind=data.kind,
            status=RecommendationStatus.NEW,
            computed_at=now,
        )
        self._apply(row, data, now)
        return row

    async def _notify_new_listing_recs(self, org_id: uuid.UUID, count: int) -> None:
        members = (
            await self.db.execute(
                select(UserOrganizationMembership).where(
                    UserOrganizationMembership.organization_id == org_id,
                    UserOrganizationMembership.is_active.is_(True),
                    UserOrganizationMembership.role.in_(
                        [MembershipRole.OWNER, MembershipRole.ADMIN]
                    ),
                )
            )
        ).scalars().all()
        for member in members:
            await self.notifier.create(
                user_id=member.user_id,
                notification_type=NotificationType.RESTOCK_RECOMMENDATION,
                title=f"{count} new listing recommendation(s)",
                title_ar=f"{count} توصية إدراج جديدة",
                body=(
                    f"The restock engine found {count} new product(s) worth listing "
                    "before expiry. Review them under Re-Stock recommendations."
                ),
                body_ar=(
                    f"وجد محرك التوريد {count} منتجاً جديداً يستحق الإدراج قبل انتهائه. "
                    "راجعها في توصيات إعادة التوريد."
                ),
                organization_id=org_id,
                resource_type="restock_recommendation",
                metadata={"new_listing_recommendations": count},
            )

    async def _compute(
        self, org_id: uuid.UUID, branch_id: uuid.UUID | None
    ) -> dict:
        tun = await self._tunables()
        now = datetime.now(timezone.utc)
        today = now.date()

        q = select(InventoryBatch).where(
            InventoryBatch.organization_id == org_id,
            InventoryBatch.deleted_at.is_(None),
        )
        if branch_id is not None:
            q = q.where(InventoryBatch.branch_id == branch_id)
        batches = list((await self.db.execute(q)).scalars().all())

        combos: dict[tuple[uuid.UUID, uuid.UUID], list[InventoryBatch]] = {}
        for b in batches:
            combos.setdefault((b.branch_id, b.product_id), []).append(b)

        live_by_batch: dict[uuid.UUID, int] = {}
        if batches:
            rows = await self.db.execute(
                select(
                    MarketplaceListing.batch_id,
                    func.coalesce(func.sum(MarketplaceListing.quantity_available), 0),
                )
                .where(
                    MarketplaceListing.batch_id.in_([b.id for b in batches]),
                    MarketplaceListing.status.in_(LIVE_LISTING_STATUSES),
                    MarketplaceListing.deleted_at.is_(None),
                )
                .group_by(MarketplaceListing.batch_id)
            )
            live_by_batch = {bid: int(total) for bid, total in rows.all()}

        rule = await NearExpiryRuleRepository(self.db).get_by_org(org_id)

        desired: dict[tuple[uuid.UUID, uuid.UUID, RestockKind], _RecData] = {}
        for (b_branch, b_product), combo in combos.items():
            replenishment = await self._build_replenishment(
                org_id, b_branch, b_product, combo, live_by_batch, tun, today, now
            )
            desired[(b_branch, b_product, RestockKind.REPLENISHMENT)] = replenishment
            if rule is not None:
                listing_rec = await self._build_listing(
                    org_id, b_branch, b_product, combo, live_by_batch, tun, today, now, rule
                )
                if listing_rec is not None:
                    desired[(b_branch, b_product, RestockKind.LISTING)] = listing_rec

        for data in desired.values():
            data.inputs["signature"] = _signature(self._signature_payload(data))

        existing_rows = list(await self.repo.list_all_for_org(org_id))
        if branch_id is not None:
            existing_rows = [r for r in existing_rows if r.branch_id == branch_id]
        existing = {(r.branch_id, r.product_id, RestockKind(r.kind)): r for r in existing_rows}

        created = updated = unchanged = superseded = new_listing_recs = 0
        cooldown = timedelta(days=tun.dismiss_cooldown_days)

        for key, data in desired.items():
            row = existing.get(key)
            if row is None:
                row = self._new_row(org_id, data, now)
                self.db.add(row)
                try:
                    async with self.db.begin_nested():
                        await self.db.flush()
                except IntegrityError:
                    row = await self.repo.get_by_key(key[0], key[1], key[2])
                    if row is None:
                        raise
                    existing[key] = row
                else:
                    created += 1
                    if data.kind == RestockKind.LISTING:
                        new_listing_recs += 1
                    continue

            if RecommendationStatus(row.status) in _TERMINAL_STATUSES:
                unchanged += 1
                continue
            if RecommendationStatus(row.status) == RecommendationStatus.DISMISSED:
                old_signature = (row.inputs or {}).get("signature")
                cooled = row.dismissed_at is not None and now - row.dismissed_at >= cooldown
                if old_signature == data.inputs["signature"] and not cooled:
                    unchanged += 1
                    continue
                self._apply(row, data, now)
                row.status = RecommendationStatus.NEW
                row.dismissed_at = None
                updated += 1
                if data.kind == RestockKind.LISTING:
                    new_listing_recs += 1
                continue

            was_superseded = RecommendationStatus(row.status) == RecommendationStatus.SUPERSEDED
            self._apply(row, data, now)
            if was_superseded:
                row.status = RecommendationStatus.NEW
                if data.kind == RestockKind.LISTING:
                    new_listing_recs += 1
            updated += 1

        for row in existing_rows:
            key = (row.branch_id, row.product_id, RestockKind(row.kind))
            if key in desired:
                continue
            if RecommendationStatus(row.status) in _TERMINAL_STATUSES:
                continue
            if RecommendationStatus(row.status) == RecommendationStatus.SUPERSEDED:
                continue
            row.status = RecommendationStatus.SUPERSEDED
            row.computed_at = now
            superseded += 1

        await self.db.flush()
        if new_listing_recs:
            await self._notify_new_listing_recs(org_id, new_listing_recs)

        summary = {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "superseded": superseded,
            "new_listing_recommendations": new_listing_recs,
        }
        logger.info("Restock recompute org=%s branch=%s: %s", org_id, branch_id, summary)
        return summary

    async def compute_for_org(self, org_id: uuid.UUID) -> dict:
        return await self._compute(org_id, None)

    async def compute_for_branch(self, org_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
        return await self._compute(org_id, branch_id)

    # ── Actions ───────────────────────────────────────────────────────────

    def _get_or_404(self, row: RestockRecommendation | None) -> RestockRecommendation:
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="التوصية غير موجودة"
            )
        return row

    def _require_actionable(self, row: RestockRecommendation) -> None:
        if RecommendationStatus(row.status) in (
            RecommendationStatus.ACTED,
            RecommendationStatus.ACCEPTED,
            RecommendationStatus.SUPERSEDED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"لا يمكن تنفيذ إجراء على توصية بحالة '{row.status}'",
            )

    async def mark_viewed(
        self, org_id: uuid.UUID, rec_id: uuid.UUID, actor_id: uuid.UUID
    ) -> RestockRecommendation:
        row = self._get_or_404(await self.repo.get_for_org(rec_id, org_id))
        if RecommendationStatus(row.status) == RecommendationStatus.NEW:
            row.status = RecommendationStatus.VIEWED
            await self.db.flush()
        return row

    async def dismiss(
        self, org_id: uuid.UUID, rec_id: uuid.UUID, actor_id: uuid.UUID
    ) -> RestockRecommendation:
        row = self._get_or_404(await self.repo.get_for_org(rec_id, org_id))
        if RecommendationStatus(row.status) == RecommendationStatus.DISMISSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="هذه التوصية مرفوضة مسبقاً",
            )
        self._require_actionable(row)
        row.status = RecommendationStatus.DISMISSED
        row.dismissed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.audit.log(
            action="restock_recommendation_dismissed",
            resource_type="restock_recommendation",
            resource_id=row.id,
            actor_id=actor_id,
            organization_id=org_id,
        )
        return row

    async def act(
        self,
        org_id: uuid.UUID,
        rec_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID,
        asking_price: float | None = None,
        quantity: int | None = None,
        ip_address: str | None = None,
    ) -> tuple[RestockRecommendation, uuid.UUID | None]:
        row = self._get_or_404(await self.repo.get_for_org(rec_id, org_id))
        self._require_actionable(row)

        listing_id: uuid.UUID | None = None
        if action == "open_listing":
            if RestockKind(row.kind) != RestockKind.REPLENISHMENT:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="فتح عرض السوق متاح لتوصيات إعادة التوريد فقط",
                )
            if row.matched_listing_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="لا يوجد عرض سوق مرتبط بهذه التوصية",
                )
            listing_id = row.matched_listing_id
        elif action == "create_listing":
            if RestockKind(row.kind) != RestockKind.LISTING:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="إنشاء عرض متاح لتوصيات الإدراج فقط",
                )
            if row.batch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="لا توجد دفعة مرتبطة بهذه التوصية",
                )
            price = asking_price if asking_price is not None else (
                float(row.suggested_price) if row.suggested_price is not None else None
            )
            if price is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="حدد سعر البيع — لا يوجد سعر مقترح لهذه التوصية",
                )
            qty = quantity if quantity is not None else row.suggested_qty
            if qty < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="الكمية المقترحة صفر — لا يمكن إنشاء عرض",
                )
            product = await self.db.get(Product, row.product_id)
            name_ar = product.name_ar if product else "منتج"
            name = product.name if product else "Product"
            listing = await ListingService(self.db).create_listing(
                ListingCreate(
                    batch_id=row.batch_id,
                    seller_branch_id=row.branch_id,
                    title=f"{name} — Near Expiry Sale",
                    title_ar=f"{name_ar} — تخفيض قرب انتهاء الصلاحية",
                    quantity_listed=qty,
                    asking_price=price,
                ),
                org_id,
                actor_id,
                ip_address=ip_address,
            )
            listing_id = listing.id
            row.inputs = {**(row.inputs or {}), "created_listing_id": str(listing.id)}
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="إجراء غير معروف",
            )

        row.status = RecommendationStatus.ACTED
        row.acted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.audit.log(
            action=f"restock_recommendation_acted_{action}",
            resource_type="restock_recommendation",
            resource_id=row.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"action": action, "listing_id": str(listing_id) if listing_id else None},
            ip_address=ip_address,
        )
        return row, listing_id
