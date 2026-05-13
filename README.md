# Pharmacy Near-Expiry Marketplace (سوق الصيدليات)

A B2B marketplace platform for Saudi Arabian pharmacies to trade near-expiry pharmaceutical inventory — reducing waste and recovering value through a regulated, compliance-first exchange system.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (Port 80)                       │
│              /api/* → FastAPI   /  → Next.js                 │
└───────────────┬──────────────────────────┬──────────────────┘
                │                          │
    ┌───────────▼──────────┐   ┌───────────▼──────────┐
    │  FastAPI Backend      │   │  Next.js Frontend     │
    │  Port 8000            │   │  Port 3000            │
    │  Python 3.12          │   │  Next.js 15 App Router│
    │  SQLAlchemy 2.0 async │   │  TypeScript strict    │
    │  APScheduler          │   │  TanStack Query v5    │
    │  Pydantic v2          │   │  next-intl (ar/en)    │
    └───────────┬──────────┘   └───────────────────────┘
                │
    ┌───────────▼──────────┐
    │  PostgreSQL 16        │
    │  Port 5432            │
    └──────────────────────┘

Layers (Backend):
  Router → Service → Repository → SQLAlchemy Models → PostgreSQL

Security:
  JWT (access 30min + refresh 7d) | Argon2 passwords
  Tenant isolation: every query filtered by organization_id
  Cloudflare guard | Firebase App Check guard | Rate limiting
```

---

## Prerequisites

- **Docker** 24+ and **Docker Compose** v2.20+
- **Node.js** 20+ (for local frontend dev)
- **Python** 3.12+ (for local backend dev)
- **PostgreSQL** 16+ (if running without Docker)

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone <repo-url>
cd tickitss

# 2. Copy environment files
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local

# 3. Start all services
cd infra/docker
docker compose up -d

# 4. Run database migrations
docker compose exec api alembic upgrade head

# 5. Seed demo data
docker compose exec api python seeds/seed.py

# 6. Open the app
open http://localhost
```

**Default credentials after seeding:**
- Super Admin: `admin@pharmacy-marketplace.sa` / `Admin@12345`
- Pharmacy (approved, seller): `manager@aldawaa.sa` / `Manager@12345`
- Pharmacist (Al-Dawaa): `pharmacist@aldawaa.sa` / `Pharma@12345`
- Pharmacy (pending, buyer): `manager@nahdi-demo.sa` / `Manager@12345`

---

## Manual Setup (Development)

### Backend

```bash
cd apps/api

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY, etc.

# Run migrations
alembic upgrade head

# Seed database
python seeds/seed.py

# Start development server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local: set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Start development server
npm run dev
# Open http://localhost:3000
```

---

## Environment Variables

### Backend (`apps/api/.env`)

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async URL | `postgresql+asyncpg://postgres:postgres@localhost/pharmacy_marketplace` |
| `SECRET_KEY` | JWT access token signing key | — (required) |
| `REFRESH_SECRET_KEY` | JWT refresh token signing key | — (required) |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `http://localhost:3000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `NOLOG` | Disable all logging | `false` |
| `REQUIRE_CLOUDFLARE` | Enforce Cloudflare IP header | `false` |
| `REQUIRE_APPCHECK` | Enforce Firebase App Check JWT | `false` |
| `FIREBASE_PROJECT_ID` | Firebase project ID (App Check) | — |
| `ENVIRONMENT` | `development` or `production` | `development` |

### Frontend (`apps/web/.env.local`)

| Variable | Description | Default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000/api/v1` |

---

## API Endpoints Summary

All API routes are prefixed with `/api/v1/`

| Domain | Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `GET /auth/me` |
| **Organizations** | `GET/PATCH /organizations/:id`, `POST /:id/approve`, `/:id/reject`, `/:id/suspend` |
| **Branches** | `GET/POST /branches`, `GET/PATCH/DELETE /branches/:id` |
| **Products** | `GET/POST /products/categories`, `GET/POST /products`, `GET /products/:id` |
| **Inventory** | `GET/POST /inventory/batches`, `GET/PATCH /inventory/batches/:id`, `GET /inventory/near-expiry`, `GET/PUT /inventory/rules` |
| **Listings** | `GET/POST /listings`, `GET/PATCH/DELETE /listings/:id`, `GET /listings/eligibility-check` |
| **Offers** | `GET/POST /offers`, `GET /offers/incoming`, `POST /offers/:id/accept`, `/reject`, `/cancel` |
| **Reservations** | `GET /reservations`, `GET/POST /reservations/:id`, `POST /reservations/:id/cancel` |
| **Transactions** | `GET /transactions`, `POST /transactions/from-reservation/:id`, `POST /transactions/:id/dispatch`, `/:id/confirm-receipt` |
| **Reports** | `GET /reports/near-expiry`, `/expired-loss`, `/recoverable-value`, `/top-products`, `/branch-comparison` |
| **Notifications** | `GET /notifications`, `/unread-count`, `POST /:id/read`, `/read-all` |
| **Admin** | `GET /admin/approvals`, `/compliance`, `/audit-logs`, `/moderation`, `/settings`, `PUT /admin/settings/:key` |

---

## Seed Data

After running `python seeds/seed.py`, the database contains:

- **1** super admin user
- **3** pharmacy organizations (1 approved, 1 pending, 1 suspended)
- **5** branches across organizations
- **30** products across 6 categories
- **60** inventory batches:
  - 20 healthy (>180 days)
  - 15 yellow zone (90-180 days)
  - 15 orange zone (30-90 days)
  - 10 red zone (<30 days, critical)
- **10** active marketplace listings
- **8** offers (mixed statuses)
- **5** completed transactions with full lifecycle

---

## Application Screens

### Public / Auth
- `/login` — Email + password login
- `/register` — 3-step pharmacy registration
- `/pending-review` — Post-registration waiting page
- `/forgot-password`, `/reset-password`

### Dashboard
- `/dashboard` — KPI cards, near-expiry summary, inventory health chart, incoming offers

### Inventory
- `/inventory/batches` — All batches with expiry status coloring
- `/inventory/batches/new` — Add inventory batch
- `/inventory/batches/:id` — Batch detail + FEFO recommendations
- `/inventory/near-expiry` — Near-expiry filtered view
- `/inventory/products` — Product catalog

### Marketplace
- `/marketplace` — Discovery with category/search filters
- `/marketplace/:id` — Listing detail + offer submission
- `/marketplace/create` — Create listing with eligibility check

### My Account
- `/my/listings` — Seller's listings management
- `/my/offers` — Buyer's submitted offers
- `/my/incoming-offers` — Seller's received offers (accept/reject)
- `/my/reservations` — Active reservations
- `/my/transactions` — Transaction history (dispatch/confirm receipt)

### Organization
- `/org/profile` — Organization profile + compliance status
- `/org/branches` — Branch management (inline add/edit)
- `/org/branches/:id` — Branch detail + storage compliance

### Reports
- `/reports/near-expiry` — Near-expiry by branch with charts
- `/reports/expired-loss` — Expired stock loss analysis
- `/reports/recoverable-value` — Recoverable value dashboard
- `/reports/top-products` — Most requested products
- `/reports/branch-comparison` — Branch performance comparison

### Admin (super_admin role only)
- `/admin/approvals` — Pending pharmacy approval queue
- `/admin/compliance` — Storage compliance review
- `/admin/settings` — Platform-wide settings
- `/admin/categories` — Category exchange rules
- `/admin/moderation` — Marketplace listing moderation
- `/admin/audit-logs` — Full audit trail

---

## Eligibility Rules

Before a batch can be listed on the marketplace, all 10 rules must pass:

1. Organization status = `approved`
2. Organization `is_licensed` = true
3. Branch `is_active` = true
4. Product `is_active` = true, not restricted, not controlled
5. Batch `is_opened` = false
6. Batch `is_patient_dispensed` = false
7. Batch `storage_condition_status` = `compliant`
8. Batch `expiry_date` > today
9. Days until expiry ≥ `min_days_for_listing` (org rule)
10. Product category `is_exchange_allowed_default` = true

---

## Expiry Zone Colors

| Zone | Days | Color |
|---|---|---|
| Healthy | > 180 days | Green |
| Notice | 90–180 days | Yellow |
| Warning | 30–90 days | Orange |
| Critical | < 30 days | Red |

---

## Deployment

### Cloud Run (Google Cloud)

```bash
# Build and push images
docker build -t gcr.io/PROJECT/pharmacy-api apps/api
docker build -t gcr.io/PROJECT/pharmacy-web apps/web
docker push gcr.io/PROJECT/pharmacy-api
docker push gcr.io/PROJECT/pharmacy-web

# Deploy
gcloud run deploy pharmacy-api --image gcr.io/PROJECT/pharmacy-api --platform managed
gcloud run deploy pharmacy-web --image gcr.io/PROJECT/pharmacy-web --platform managed
```

### VPS (Ubuntu)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and configure
git clone <repo> && cd tickitss
cp apps/api/.env.example apps/api/.env
# Edit .env with production values

# Start
cd infra/docker && docker compose up -d
docker compose exec api alembic upgrade head
```

**Production checklist:**
- [ ] Strong `SECRET_KEY` and `REFRESH_SECRET_KEY` (min 64 chars)
- [ ] `ENVIRONMENT=production` (disables API docs)
- [ ] `ALLOWED_ORIGINS` set to your domain only
- [ ] `REQUIRE_CLOUDFLARE=true` if behind Cloudflare
- [ ] SSL certificates configured in Nginx
- [ ] Regular PostgreSQL backups enabled
- [ ] `LOG_LEVEL=WARNING`

---

## License

Private — All rights reserved.
