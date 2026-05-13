# Architecture — Pharmacy Near-Expiry Marketplace

## System Overview

```
Client (Browser)
     │
     ▼
┌────────────┐     ┌────────────────────────────────────────┐
│   Nginx    │────▶│  Next.js 15 (SSR / App Router)         │
│  Port 80   │     │  RTL-first Arabic UI (next-intl)       │
└─────┬──────┘     │  TanStack Query v5 + React Hook Form   │
      │             └────────────────────────────────────────┘
      │ /api/*
      ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI (ORJSONResponse, uvloop)                   │
│  Port 8000                                          │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐    │
│  │ Routers  │  │ Services │  │ Repositories  │    │
│  │ /api/v1/ │─▶│ Business │─▶│ DB Queries    │    │
│  │          │  │ Logic    │  │ (filtered by  │    │
│  │          │  │          │  │  org_id)      │    │
│  └──────────┘  └──────────┘  └───────┬───────┘    │
│                                       │             │
│  ┌─────────────────────────────────┐  │             │
│  │  APScheduler                   │  │             │
│  │  Near-expiry scan (6h)         │  │             │
│  └─────────────────────────────────┘  │             │
└───────────────────────────────────────┼─────────────┘
                                        ▼
                          ┌─────────────────────┐
                          │  PostgreSQL 16       │
                          │  SQLAlchemy 2.0 async│
                          │  asyncpg driver      │
                          └─────────────────────┘
```

## Data Flow: Listing Creation

```
1. Buyer browses /marketplace → GET /api/v1/listings
2. Seller navigates to /marketplace/create
3. Seller selects a batch → GET /api/v1/listings/eligibility-check?batch_id=X
4. EligibilityService runs all 10 rules → returns EligibilityResult
5. If all_passed: Seller submits form → POST /api/v1/listings
6. ListingService.create_listing():
   a. Re-runs eligibility check
   b. Validates quantity ≤ batch.quantity_on_hand
   c. Updates batch.status = "listed"
   d. Creates MarketplaceListing record
   e. Writes AuditLog entry
7. Frontend redirects to /my/listings
```

## Data Flow: Offer → Transaction

```
1. Buyer sees listing → POST /api/v1/offers (submit offer)
2. Seller sees incoming offers → GET /api/v1/offers/incoming
3. Seller accepts → POST /api/v1/offers/:id/accept
   - OfferService.accept_offer():
     a. Rejects all other PENDING offers for same listing
     b. Creates Reservation (expires in N hours per platform settings)
     c. Updates offer.status = "accepted"
4. Transaction created → POST /api/v1/transactions/from-reservation/:id
5. Seller dispatches → POST /api/v1/transactions/:id/dispatch
6. Buyer confirms receipt → POST /api/v1/transactions/:id/confirm-receipt
   - TransactionService.confirm_receipt():
     a. Updates batch.status = "sold"
     b. Records InventoryMovement (type=sold)
     c. Updates listing.status = "sold"
     d. Marks transaction.status = "completed"
     e. Writes AuditLog
```

## Multi-Tenancy

Every organization's data is isolated through mandatory `organization_id` filtering in repositories:

```python
# Every query includes:
stmt = select(Model).where(
    Model.organization_id == organization_id,
    Model.deleted_at.is_(None)
)

# Super admin bypass is EXPLICIT only:
if current_user.role == UserRole.SUPER_ADMIN:
    stmt = select(Model)  # no org filter
```

## Security Architecture

```
Request
  │
  ├── CloudflareGuardMiddleware (if REQUIRE_CLOUDFLARE=true)
  │   └── Validates CF-Connecting-IP header
  │
  ├── AppCheckMiddleware (if REQUIRE_APPCHECK=true)
  │   └── Validates Firebase App Check JWT
  │
  ├── LoggingMiddleware
  │   └── Assigns X-Request-ID, logs timing
  │
  ├── CORSMiddleware
  │   └── Validates against ALLOWED_ORIGINS env var
  │
  └── Router handlers
      └── get_current_user() dependency
          └── Decodes JWT → loads User from DB
              └── role-based guards (require_role, require_super_admin)
```

## Database Schema (18 tables)

```
users
pharmacy_organizations
  └── user_organization_memberships (many-to-many)
pharmacy_branches
  └── near_expiry_rules

product_categories (self-referential parent/children)
products

inventory_batches
  └── inventory_movements

marketplace_listings
  └── listing_views
  └── listing_offers
      └── reservations
          └── transactions

audit_logs
notifications
notification_preferences
platform_settings
```

## Frontend Architecture

```
apps/web/src/
├── app/
│   └── [locale]/          # All routes under locale segment
│       ├── layout.tsx      # Sets dir="rtl", lang, loads fonts
│       ├── login/          # Auth pages
│       ├── dashboard/      # KPI + charts
│       ├── inventory/      # Batch management
│       ├── marketplace/    # Listing discovery + detail + create
│       ├── my/             # User's own data (listings/offers/txns)
│       ├── org/            # Organization + branch management
│       ├── reports/        # 5 report screens with charts
│       ├── admin/          # Super admin only (6 screens)
│       └── notifications/  # Notification center
├── components/
│   ├── layout/             # Shell (sidebar + navbar)
│   └── ui/                 # badge, expiry-badge, data-table
├── lib/
│   ├── api.ts              # Typed Axios client + all API functions
│   ├── auth.ts             # Zustand store + cookie management
│   └── utils.ts            # formatCurrency, formatDate, getExpiryZone
├── i18n/                   # next-intl configuration
└── middleware.ts            # Auth guard + locale detection
```

## Near-Expiry Scanner

APScheduler runs `scan_near_expiry_batches()` every 6 hours:

```
For each active InventoryBatch where deleted_at IS NULL:
  1. Calculate days_until_expiry
  2. Check thresholds: 180, 90, 30 days
  3. If threshold not yet notified (notified_180/90/30 = False):
     a. Create Notification for org members
     b. Mark threshold as notified
     c. If org.allow_auto_listing = True:
        → Run eligibility check
        → If all passed: create MarketplaceListing automatically
```
