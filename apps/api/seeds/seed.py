"""
Seed script — populates the database with demo data.
Run: python -m seeds.seed
"""
from __future__ import annotations

import asyncio
import sys
import os
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def seed() -> None:
    from database import AsyncSessionLocal, engine
    from models import Base

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        try:
            await _seed_all(db)
            await db.commit()
            print("✅ Seed complete")
        except Exception as exc:
            await db.rollback()
            print(f"❌ Seed failed: {exc}")
            raise


async def _seed_all(db) -> None:
    from auth.password import hash_password
    from models.user import User, UserRole
    from models.organization import (
        PharmacyOrganization, OrganizationStatus,
        UserOrganizationMembership, MembershipRole,
    )
    from models.branch import PharmacyBranch, StorageConditionStatus
    from models.product import ProductCategory, Product
    from models.inventory import InventoryBatch, BatchStatus, NearExpiryRule, InventoryMovement, MovementType
    from models.marketplace import (
        MarketplaceListing, ListingStatus, ListingOffer, OfferStatus,
        Reservation, ReservationStatus,
    )
    from models.transaction import Transaction, TransactionStatus
    from models.settings import PlatformSettings
    import secrets

    today = date.today()

    # ── Super Admin ───────────────────────────────────────────────────────
    admin = User(
        id=uuid.uuid4(),
        email="admin@pharmacy-marketplace.sa",
        phone="+966500000001",
        full_name="Super Administrator",
        hashed_password=hash_password("Admin@12345"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    await db.flush()

    # ── Organizations ─────────────────────────────────────────────────────
    org1 = PharmacyOrganization(
        id=uuid.uuid4(),
        name="Al-Dawaa Pharmacy Group",
        name_ar="مجموعة صيدليات الدواء",
        commercial_registration_number="CR-1010100001",
        license_number="LIC-001",
        is_licensed=True,
        status=OrganizationStatus.APPROVED,
        email="info@aldawaa.sa",
        phone="+966112345001",
        address="King Fahd Road, Riyadh",
        city="Riyadh",
        region="Riyadh Region",
        approved_at=datetime.now(timezone.utc),
        approved_by_id=admin.id,
        allow_auto_listing=True,
    )
    org2 = PharmacyOrganization(
        id=uuid.uuid4(),
        name="Nahdi Medical Pharmacy",
        name_ar="صيدلية النهدي الطبية",
        commercial_registration_number="CR-1010100002",
        license_number=None,
        is_licensed=False,
        status=OrganizationStatus.PENDING,
        email="info@nahdi-demo.sa",
        phone="+966112345002",
        city="Jeddah",
        region="Makkah Region",
    )
    org3 = PharmacyOrganization(
        id=uuid.uuid4(),
        name="Quick Cure Pharmacy",
        name_ar="صيدلية الشفاء السريع",
        commercial_registration_number="CR-1010100003",
        license_number="LIC-003",
        is_licensed=True,
        status=OrganizationStatus.SUSPENDED,
        email="info@quickcure-demo.sa",
        phone="+966112345003",
        city="Dammam",
        region="Eastern Region",
        suspension_reason="License renewal pending",
    )
    db.add_all([org1, org2, org3])
    await db.flush()

    # ── Users per org ─────────────────────────────────────────────────────
    user1 = User(
        id=uuid.uuid4(),
        email="manager@aldawaa.sa",
        phone="+966500000011",
        full_name="Ahmed Al-Rashidi",
        hashed_password=hash_password("Manager@12345"),
        role=UserRole.ORG_ADMIN,
        is_active=True,
        is_email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    user2 = User(
        id=uuid.uuid4(),
        email="pharmacist@aldawaa.sa",
        phone="+966500000012",
        full_name="Sara Al-Qahtani",
        hashed_password=hash_password("Pharma@12345"),
        role=UserRole.PHARMACIST,
        is_active=True,
        is_email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    user3 = User(
        id=uuid.uuid4(),
        email="manager@nahdi-demo.sa",
        phone="+966500000013",
        full_name="Khaled Al-Harbi",
        hashed_password=hash_password("Manager@12345"),
        role=UserRole.ORG_ADMIN,
        is_active=True,
        is_email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add_all([user1, user2, user3])
    await db.flush()

    # Memberships
    db.add_all([
        UserOrganizationMembership(
            id=uuid.uuid4(), user_id=user1.id, organization_id=org1.id,
            role=MembershipRole.OWNER, is_active=True, joined_at=datetime.now(timezone.utc),
        ),
        UserOrganizationMembership(
            id=uuid.uuid4(), user_id=user2.id, organization_id=org1.id,
            role=MembershipRole.PHARMACIST, is_active=True, joined_at=datetime.now(timezone.utc),
        ),
        UserOrganizationMembership(
            id=uuid.uuid4(), user_id=user3.id, organization_id=org2.id,
            role=MembershipRole.OWNER, is_active=True, joined_at=datetime.now(timezone.utc),
        ),
    ])
    await db.flush()

    # ── Branches ──────────────────────────────────────────────────────────
    branch1 = PharmacyBranch(
        id=uuid.uuid4(), organization_id=org1.id, name="Al-Dawaa Main Branch",
        name_ar="فرع الدواء الرئيسي", branch_code="ADW-001", is_active=True,
        city="Riyadh", region="Riyadh Region", phone="+966112340001",
        storage_condition_status=StorageConditionStatus.COMPLIANT,
        cold_chain_available=True, narcotics_license=False,
    )
    branch2 = PharmacyBranch(
        id=uuid.uuid4(), organization_id=org1.id, name="Al-Dawaa North Branch",
        name_ar="فرع الدواء الشمالي", branch_code="ADW-002", is_active=True,
        city="Riyadh", region="Riyadh Region", phone="+966112340002",
        storage_condition_status=StorageConditionStatus.COMPLIANT,
        cold_chain_available=False,
    )
    branch3 = PharmacyBranch(
        id=uuid.uuid4(), organization_id=org1.id, name="Al-Dawaa South Branch",
        name_ar="فرع الدواء الجنوبي", branch_code="ADW-003", is_active=True,
        city="Riyadh", region="Riyadh Region",
        storage_condition_status=StorageConditionStatus.COMPLIANT,
    )
    branch4 = PharmacyBranch(
        id=uuid.uuid4(), organization_id=org2.id, name="Nahdi Jeddah Branch",
        name_ar="فرع النهدي جدة", branch_code="NHD-001", is_active=True,
        city="Jeddah", region="Makkah Region",
        storage_condition_status=StorageConditionStatus.UNDER_REVIEW,
    )
    branch5 = PharmacyBranch(
        id=uuid.uuid4(), organization_id=org3.id, name="Quick Cure Dammam",
        name_ar="شفاء سريع الدمام", branch_code="QC-001", is_active=False,
        city="Dammam", region="Eastern Region",
        storage_condition_status=StorageConditionStatus.NON_COMPLIANT,
    )
    db.add_all([branch1, branch2, branch3, branch4, branch5])
    await db.flush()

    # ── Near-Expiry Rules ─────────────────────────────────────────────────
    db.add_all([
        NearExpiryRule(id=uuid.uuid4(), organization_id=org1.id, min_days_for_listing=30,
                       allow_auto_listing=True, auto_listing_discount_pct=20),
        NearExpiryRule(id=uuid.uuid4(), organization_id=org2.id, min_days_for_listing=45),
        NearExpiryRule(id=uuid.uuid4(), organization_id=org3.id, min_days_for_listing=60),
    ])
    await db.flush()

    # ── Product Categories ────────────────────────────────────────────────
    cats = {}
    cat_data = [
        ("antibiotics", "Antibiotics", "مضادات حيوية"),
        ("vitamins", "Vitamins & Supplements", "فيتامينات ومكملات"),
        ("analgesics", "Analgesics & Pain Relief", "مسكنات الألم"),
        ("cardiovascular", "Cardiovascular", "أدوية القلب والأوعية"),
        ("dermatology", "Dermatology", "أدوية الجلدية"),
        ("gastrointestinal", "Gastrointestinal", "أدوية الجهاز الهضمي"),
    ]
    for code, name, name_ar in cat_data:
        cat = ProductCategory(
            id=uuid.uuid4(), code=code, name=name, name_ar=name_ar,
            is_exchange_allowed_default=True,
        )
        db.add(cat)
        cats[code] = cat
    await db.flush()

    # ── Products ──────────────────────────────────────────────────────────
    products = []
    product_data = [
        ("antibiotics", "Amoxicillin 500mg", "أموكسيسيلين 500 مجم", "AMX-500", 45.0),
        ("antibiotics", "Azithromycin 250mg", "أزيثروميسين 250 مجم", "AZT-250", 65.0),
        ("antibiotics", "Ciprofloxacin 500mg", "سيبروفلوكساسين 500 مجم", "CIP-500", 55.0),
        ("antibiotics", "Metronidazole 500mg", "ميترونيدازول 500 مجم", "MET-500", 30.0),
        ("antibiotics", "Clarithromycin 500mg", "كلاريثروميسين 500 مجم", "CLR-500", 75.0),
        ("vitamins", "Vitamin C 1000mg", "فيتامين ج 1000 مجم", "VIT-C1000", 25.0),
        ("vitamins", "Vitamin D3 5000IU", "فيتامين د3 5000 وحدة", "VIT-D5000", 40.0),
        ("vitamins", "Vitamin B Complex", "فيتامين ب المركب", "VIT-BCOMP", 35.0),
        ("vitamins", "Omega-3 1000mg", "أوميغا-3 1000 مجم", "OMG-1000", 55.0),
        ("vitamins", "Zinc 50mg", "زنك 50 مجم", "ZNC-050", 20.0),
        ("analgesics", "Paracetamol 500mg", "باراسيتامول 500 مجم", "PAR-500", 15.0),
        ("analgesics", "Ibuprofen 400mg", "إيبوبروفين 400 مجم", "IBU-400", 20.0),
        ("analgesics", "Naproxen 250mg", "نابروكسين 250 مجم", "NAP-250", 35.0),
        ("analgesics", "Diclofenac 50mg", "ديكلوفيناك 50 مجم", "DIC-050", 30.0),
        ("analgesics", "Tramadol 50mg", "ترامادول 50 مجم", "TRM-050", 45.0, True),
        ("cardiovascular", "Atorvastatin 20mg", "أتورفاستاتين 20 مجم", "ATV-020", 60.0),
        ("cardiovascular", "Amlodipine 5mg", "أملوديبين 5 مجم", "AML-005", 40.0),
        ("cardiovascular", "Metoprolol 50mg", "ميتوبرولول 50 مجم", "MTP-050", 50.0),
        ("cardiovascular", "Ramipril 5mg", "راميبريل 5 مجم", "RMP-005", 55.0),
        ("cardiovascular", "Aspirin 100mg", "أسبرين 100 مجم", "ASP-100", 12.0),
        ("dermatology", "Hydrocortisone Cream 1%", "كريم هيدروكورتيزون 1%", "HYD-001", 30.0),
        ("dermatology", "Clotrimazole Cream 1%", "كريم كلوتريمازول 1%", "CLT-001", 25.0),
        ("dermatology", "Tretinoin Cream 0.05%", "كريم ترتينوين 0.05%", "TRT-005", 80.0),
        ("dermatology", "Acyclovir Cream 5%", "كريم أسيكلوفير 5%", "ACY-005", 45.0),
        ("dermatology", "Mupirocin Ointment 2%", "مرهم موبيروسين 2%", "MUP-002", 60.0),
        ("gastrointestinal", "Omeprazole 20mg", "أوميبرازول 20 مجم", "OMP-020", 35.0),
        ("gastrointestinal", "Metoclopramide 10mg", "ميتوكلوبراميد 10 مجم", "MTC-010", 20.0),
        ("gastrointestinal", "Loperamide 2mg", "لوبراميد 2 مجم", "LPR-002", 25.0),
        ("gastrointestinal", "Domperidone 10mg", "دومبيريدون 10 مجم", "DMP-010", 30.0),
        ("gastrointestinal", "Lansoprazole 30mg", "لانسوبرازول 30 مجم", "LNS-030", 45.0),
    ]
    for row in product_data:
        cat_code = row[0]
        name, name_ar, sku, price = row[1], row[2], row[3], row[4]
        is_controlled = row[5] if len(row) > 5 else False
        p = Product(
            id=uuid.uuid4(),
            category_id=cats[cat_code].id,
            name=name,
            name_ar=name_ar,
            sku=sku,
            standard_price=price,
            is_active=True,
            is_controlled=is_controlled,
        )
        db.add(p)
        products.append(p)
    await db.flush()

    # ── Inventory Batches ─────────────────────────────────────────────────
    batches = []
    import random
    random.seed(42)

    def make_batch(product, branch, org, days_offset, qty=100):
        expiry = today + timedelta(days=days_offset)
        b = InventoryBatch(
            id=uuid.uuid4(),
            organization_id=org.id,
            branch_id=branch.id,
            product_id=product.id,
            batch_number=f"BTH-{secrets.token_hex(4).upper()}",
            quantity=qty,
            quantity_available=qty,
            unit_cost=product.standard_price,
            expiry_date=expiry,
            received_date=today - timedelta(days=30),
            supplier="Saudi Pharma Distributors",
            status=BatchStatus.ACTIVE,
            storage_condition_status="compliant",
        )
        return b

    # 20 healthy batches (>180 days)
    for i in range(20):
        p = products[i % len(products)]
        b = branch1 if i % 2 == 0 else branch2
        batches.append(make_batch(p, b, org1, random.randint(181, 365)))

    # 15 batches expiring in 180 days (yellow zone)
    for i in range(15):
        p = products[i % len(products)]
        b = [branch1, branch2, branch3][i % 3]
        batches.append(make_batch(p, b, org1, random.randint(91, 180)))

    # 15 batches expiring in 90 days (orange zone)
    for i in range(15):
        p = products[i % 15]
        b = branch1 if i % 2 == 0 else branch2
        batches.append(make_batch(p, b, org1, random.randint(31, 90), qty=50))

    # 10 batches expiring in 30 days (red zone)
    for i in range(10):
        p = products[i % 10]
        b = [branch1, branch2, branch3][i % 3]
        batches.append(make_batch(p, b, org1, random.randint(5, 30), qty=30))

    db.add_all(batches)
    await db.flush()

    # ── Marketplace Listings (10 active) ─────────────────────────────────
    listing_batches = [b for b in batches if (b.expiry_date - today).days >= 30][:10]
    listings = []
    for i, b in enumerate(listing_batches):
        from models.product import Product as Prod
        from sqlalchemy import select as sa_select
        prod_q = await db.execute(sa_select(Prod).where(Prod.id == b.product_id))
        prod = prod_q.scalar_one_or_none()
        asking_price = float(b.unit_cost or 50) * b.quantity_available * 0.7
        listing = MarketplaceListing(
            id=uuid.uuid4(),
            seller_organization_id=org1.id,
            seller_branch_id=b.branch_id,
            batch_id=b.id,
            created_by_id=user1.id,
            title=f"{prod.name if prod else 'Product'} — Near Expiry Sale",
            title_ar=f"{prod.name_ar if prod else 'منتج'} — تخفيض قرب انتهاء الصلاحية",
            quantity_listed=b.quantity_available,
            quantity_available=b.quantity_available,
            asking_price=round(asking_price, 2),
            allow_offers=True,
            status=ListingStatus.ACTIVE,
            eligibility_passed=True,
        )
        db.add(listing)
        b.status = BatchStatus.LISTED
        listings.append(listing)
    await db.flush()

    # ── Offers (8 with mixed statuses) ───────────────────────────────────
    offer_statuses = [
        OfferStatus.PENDING, OfferStatus.PENDING, OfferStatus.PENDING,
        OfferStatus.ACCEPTED, OfferStatus.REJECTED,
        OfferStatus.PENDING, OfferStatus.CANCELLED, OfferStatus.PENDING,
    ]
    offers = []
    for i, status_val in enumerate(offer_statuses):
        listing = listings[i % len(listings)]
        offer = ListingOffer(
            id=uuid.uuid4(),
            listing_id=listing.id,
            buyer_organization_id=org2.id,
            submitted_by_id=user3.id,
            offered_price=round(float(listing.asking_price) * 0.85, 2),
            quantity=min(10, listing.quantity_available),
            status=status_val,
            message="Interested in purchasing this batch",
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            responded_at=datetime.now(timezone.utc) if status_val in (OfferStatus.ACCEPTED, OfferStatus.REJECTED) else None,
        )
        db.add(offer)
        offers.append(offer)
    await db.flush()

    # ── 5 Completed Transactions ──────────────────────────────────────────
    completed_listings = listings[5:10]  # Use last 5 listings
    for i, listing in enumerate(completed_listings):
        # Create reservation
        reservation = Reservation(
            id=uuid.uuid4(),
            listing_id=listing.id,
            buyer_organization_id=org2.id,
            reserved_by_id=user3.id,
            quantity=min(5, listing.quantity_available),
            agreed_price=float(listing.asking_price),
            status=ReservationStatus.CONFIRMED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            confirmed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(reservation)
        await db.flush()

        qty = min(5, listing.quantity_available)
        total = qty * float(listing.asking_price)
        platform_fee = round(total * 0.02, 2)

        tx = Transaction(
            id=uuid.uuid4(),
            listing_id=listing.id,
            reservation_id=reservation.id,
            seller_organization_id=org1.id,
            buyer_organization_id=org2.id,
            quantity=qty,
            unit_price=float(listing.asking_price),
            total_amount=total,
            platform_fee=platform_fee,
            net_amount=total - platform_fee,
            status=TransactionStatus.COMPLETED,
            reference_number=f"TXN-{secrets.token_hex(6).upper()}",
            dispatched_at=datetime.now(timezone.utc) - timedelta(days=2),
            dispatched_by_id=user1.id,
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            received_by_id=user3.id,
            completed_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(tx)
        listing.status = ListingStatus.SOLD

    await db.flush()

    # ── Platform Settings ─────────────────────────────────────────────────
    settings_data = [
        ("marketplace.platform_fee_pct", {"value": 2.0}, "general", "Platform fee percentage"),
        ("marketplace.min_listing_days", {"value": 30}, "marketplace", "Minimum days until expiry for listing"),
        ("notifications.email_enabled", {"value": True}, "notifications", "Enable email notifications"),
        ("notifications.whatsapp_enabled", {"value": False}, "notifications", "Enable WhatsApp notifications"),
        ("listings.max_per_org", {"value": 50}, "marketplace", "Maximum active listings per organization"),
    ]
    for key, value, category, description in settings_data:
        db.add(PlatformSettings(
            id=uuid.uuid4(),
            key=key,
            value=value,
            description=description,
            category=category,
        ))
    await db.flush()

    print(f"  ✔ 1 super admin, 3 users, 3 orgs, 5 branches created")
    print(f"  ✔ 30 products, {len(batches)} inventory batches created")
    print(f"  ✔ {len(listings)} listings, {len(offers)} offers, 5 transactions created")


if __name__ == "__main__":
    asyncio.run(seed())
