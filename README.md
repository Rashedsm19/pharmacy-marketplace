# Pharmacy Near-Expiry Marketplace (سوق الصيدليات)

A B2B marketplace platform for Saudi Arabian pharmacies to trade near-expiry pharmaceutical inventory — reducing waste and recovering value through a regulated, compliance-first exchange system.

**New here? Start with the documentation:**

| Document | What it answers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | How the system fits together, the layers, the key flows, the data model |
| [docs/directory-structure.md](docs/directory-structure.md) | Where every kind of file lives, and where to go to change X |
| [docs/contributing.md](docs/contributing.md) | How to run it, and how to add an endpoint, service, table, screen or test |

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
cd pharmacy-marketplace

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

## Tests, lint and type checks

```bash
# Backend — needs a PostgreSQL database; DATABASE_URL is read from the environment
cd apps/api
pip install -r requirements-dev.txt
pytest -q              # full suite, run in-process against the real app over ASGI
pytest -m slow -q      # the ten-thousand-row import, excluded from the default run
ruff check .
mypy . --ignore-missing-imports

# Frontend
cd apps/web
npm run type-check
npm run lint
npm run build
```

CI runs all of the above on every push and pull request
(`.github/workflows/ci.yml`). Note that the test database schema is built with
`create_all`, which adds missing tables but not missing columns — drop and
recreate it after a migration that alters an existing table.

---

## Environment Variables

### Backend (`apps/api/.env`)

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async URL | `postgresql+asyncpg://postgres:postgres@localhost/pharmacy_marketplace` |
| `SECRET_KEY` | Application secret | — (set it in any deployment) |
| `JWT_SECRET_KEY` | JWT signing key (access and refresh) | — (set it in any deployment) |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `http://localhost:3000` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `NOLOG` | Disable all logging | `false` |
| `REQUIRE_CLOUDFLARE` | Enforce Cloudflare IP header | `false` |
| `REQUIRE_APPCHECK` | Enforce Firebase App Check JWT | `false` |
| `FIREBASE_PROJECT_ID` | Firebase project ID (App Check) | — |
| `APP_ENV` | `development`, `staging` or `production` (production hides `/docs`) | `development` |
| `EMAIL_BACKEND` | `stub`, `resend` or `smtp` | `stub` |
| `WHATSAPP_BACKEND` | `stub` or `meta` | `stub` |
| `ZATCA_MODE` | `stub`, `sandbox` or `production` | `stub` |
| `RUN_MIGRATIONS_ON_STARTUP` | Run `alembic upgrade head` at startup | `false` |
| `SEED_ON_STARTUP` | Seed demo data if the database is empty | `false` |

`apps/api/.env.example` is the complete, commented list — every variable the
backend reads is in it. The table above is the subset you will usually set.

### Frontend (`apps/web/.env.local`)

| Variable | Description | Default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Where the browser sends API calls. Relative (`/api/v1`) in a deployment, so calls go through this app's own proxy route | `http://localhost:8000/api/v1` |
| `API_URL` | Upstream the proxy route forwards to, server-side. Required whenever `NEXT_PUBLIC_API_URL` is relative | — |
| `NEXT_OUTPUT_STANDALONE` | Emit `.next/standalone`; the Dockerfile needs it | `false` |

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
| **Disputes** | `POST /disputes`, `GET /disputes`, `/disputes/queue`, `POST /:id/evidence`, `/:id/respond`, `/:id/resolve` |
| **Invoices** | `GET /invoices`, `/invoices/:id`, `/invoices/:id/xml`, `/invoices/admin/failed` |
| **Ratings** | `POST /ratings`, `GET /ratings/organization/:id`, `/ratings/organization/:id/list` |
| **Inventory import** | `GET /inventory/import/template`, `/capacity`, `POST /inventory/import`, `GET /inventory/import/:id`, `/:id/errors` |
| **Admin** | `GET /admin/approvals`, `/compliance`, `/audit-logs`, `/moderation`, `/settings`, `PUT /admin/settings/:key`, `GET /admin/inventory`, `/admin/products/drafts`, `/admin/imports` |
| **Support console** | `GET /admin/users`, `/admin/customers`, `POST /admin/users/:id/reset-link`, `/deactivate`, `/impersonate`, `POST /admin/moderation/:id/remove`, `DELETE /admin/inventory/batches/:id`, `DELETE /admin/organizations/:id` |
| **API keys** | `GET /api-keys`, `/api-keys/scopes`, `POST /api-keys`, `DELETE /api-keys/:id` |
| **External (X-API-Key)** | `GET /external/health`, `/external/inventory/near-expiry`, `/external/listings`, `POST /external/inventory/sync` |

Full route list, grouped by domain, is in [docs/architecture.md](docs/architecture.md).

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
- `/inventory/import` — Spreadsheet upload with job status and error report
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
- `/my/disputes` — Disputes this organization raised or must answer

### Organization
- `/org/profile` — Organization profile + compliance status
- `/org/branches` — Branch management (inline add/edit)
- `/org/branches/:id` — Branch detail + storage compliance
- `/org/api-keys` — Issue and revoke keys for the organization's own systems

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
- `/admin/customers`, `/admin/customers/:id` — Customer accounts and their activity
- `/admin/users` — User administration (reset links, deactivate, impersonate)
- `/admin/disputes` — Dispute resolution queue
- `/admin/inventory` — Cross-pharmacy inventory visibility
- `/admin/drafts` — Draft products awaiting promotion to the shared catalog
- `/admin/imports` — Every customer's import jobs

### Other
- `/notifications` — Notification centre
- `/docs/integration` — Integration guide for customers using the external API

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

### Render (the live deployment)

`render.yaml` declares both services: `pharmacy-api` (Python, rooted at
`apps/api`, started with `uvicorn main:app`) and `pharmacy-web` (Node, rooted at
`apps/web`). The API runs with `RUN_MIGRATIONS_ON_STARTUP=true`, because there
is no separate release step to run migrations in, and `SEED_ON_STARTUP=true`,
which is a no-op once the database has users.

The frontend is given `NEXT_PUBLIC_API_URL=/api/v1` so the browser calls the
web app's own proxy route, and `API_URL` pointing at the API service so that
route knows where to forward.

Two things to know before touching the deployment:

- **The database is not on Render.** Free Render Postgres expires after 30 days
  and the API crash-looped when it did, so the database was moved to Neon. The
  `databases:` block still in `render.yaml`, and the `fromDatabase` reference
  that reads from it, describe a database that no longer exists — the deployed
  service takes `DATABASE_URL` from its own environment instead. Treat that part
  of the file as stale, and check the live service before changing it.
- Both services are on the free plan and spin down when idle. The first request
  after an idle period can take a minute, which is why the frontend's HTTP
  client uses a long timeout rather than the default.

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
git clone <repo> && cd pharmacy-marketplace
cp apps/api/.env.example apps/api/.env
# Edit .env with production values

# Start
cd infra/docker && docker compose up -d
docker compose exec api alembic upgrade head
```

**Production checklist:**
- [ ] Strong `SECRET_KEY` and `JWT_SECRET_KEY` (min 64 chars)
- [ ] `APP_ENV=production` (disables API docs)
- [ ] `ALLOWED_ORIGINS` set to your domain only
- [ ] `REQUIRE_CLOUDFLARE=true` if behind Cloudflare
- [ ] SSL certificates configured in Nginx
- [ ] Regular PostgreSQL backups enabled
- [ ] `LOG_LEVEL=WARNING`

---

## License

Private — All rights reserved.
