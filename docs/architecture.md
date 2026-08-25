# Architecture — Pharmacy Near-Expiry Marketplace

A B2B marketplace where licensed Saudi pharmacies list pharmaceutical stock that
is approaching expiry, and other pharmacies buy it before it has to be
destroyed. Everything else in the system exists to make that exchange safe:
licence checks, storage-condition rules, an audit trail, ZATCA e-invoicing and a
support console for acting on a customer's behalf.

- **Directory map and "where do I change X":** [directory-structure.md](directory-structure.md)
- **How to add features, endpoints, migrations and tests:** [contributing.md](contributing.md)
- **Setup, credentials and deployment:** [../README.md](../README.md)

---

## System overview

```
                       Browser (Arabic, RTL)
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │  Next.js 15 App Router  ·  apps/web           │
        │  Screens under /[locale]/…                    │
        │  /api/v1/[...path] proxy route ───────────┐   │
        └──────────────────────────────────────────┼───┘
                                                   │ server-side
                                                   ▼
        ┌──────────────────────────────────────────────┐
        │  FastAPI  ·  apps/api  ·  /api/v1/…          │
        │                                              │
        │  middleware → routers → services → repos     │
        │                    ↘ services/integrations   │
        │  APScheduler: expiry scan, reservation sweep,│
        │               invoice retry, import worker   │
        └───────────────┬──────────────────┬───────────┘
                        │                  │
                        ▼                  ▼
                 PostgreSQL          Email · ZATCA · file storage
```

In deployment the browser never calls the API directly. It calls the Next.js
app's own `/api/v1/[...path]` route, which forwards server-side to `API_URL`.
In local development `NEXT_PUBLIC_API_URL` points straight at
`http://localhost:8000/api/v1` and the proxy is bypassed.

Locally, `infra/docker/docker-compose.yml` puts nginx in front of both
(`/api` → FastAPI, `/` → Next.js). The live deployment is Render, described in
`render.yaml`.

---

## Backend layers

```
routers/          HTTP. Parse, authorize via dependencies, call one service,
                  return a schema. No SQL, no cross-router calls.
services/         Business rules, transactions, audit writes, notifications.
services/integrations/   Email, ZATCA, file storage — the outside world.
repositories/     Queries. Org-scoped ones filter by organization_id here.
models/           SQLAlchemy tables and enums.
schemas/          Pydantic v2 in/out shapes.
```

Supporting modules that cut across all of it:

| Module | Responsibility |
|---|---|
| `main.py` | App factory: middleware order, router registration, startup/shutdown, `/health`, `/ready`, and the Arabic validation-error handler |
| `config.py` | Every environment variable, with defaults, via pydantic-settings |
| `database.py` | Async engine and `AsyncSessionLocal` |
| `dependencies.py` | `DbSession`, `CurrentUser`, `SuperAdmin`, `OrgAdminOrAbove`, `ApiKeyAuth`, `require_scope`, impersonation context |
| `auth/` | JWT creation and decoding, argon2 hashing, actor context |
| `middleware/` | Request logging with a request id, Cloudflare guard, Firebase App Check guard, auth throttle |
| `scheduler.py` | The four APScheduler jobs |
| `httpx_client.py` | One shared HTTP/2 client for all outbound calls |

### Request lifecycle

```
Request
 ├─ AppCheckMiddleware        (if REQUIRE_APPCHECK)
 ├─ CloudflareGuardMiddleware (if REQUIRE_CLOUDFLARE)
 ├─ CORSMiddleware            (ALLOWED_ORIGINS — never a wildcard in production)
 ├─ LoginThrottleMiddleware   (if THROTTLE_AUTH; auth endpoints only)
 ├─ LoggingMiddleware         (X-Request-ID, timing)
 └─ Route handler
      ├─ get_current_user  → decode JWT → load user → build actor context
      ├─ role guard        → SuperAdmin / OrgAdminOrAbove / require_role
      └─ service → repository → PostgreSQL
```

Note the middleware order in `main.py` is the reverse of the order it runs in:
Starlette applies the last-added middleware outermost.

### Authentication and authorization

- **Sessions**: JWT access token plus refresh token; argon2 password hashing.
- **Two role axes**: a platform `UserRole` (`super_admin`, `org_admin`,
  `pharmacist`, `viewer`) on the user, and a `MembershipRole` (`owner`, `admin`,
  `pharmacist`, `viewer`) on the user's membership of an organization.
- **Tenant isolation**: every org-scoped repository query filters by
  `organization_id` taken from the token, not from the request body. A super
  admin bypass is always written explicitly as a role check.
- **Impersonation**: support staff can open a scoped session as a customer.
  It is recorded in `impersonation_sessions`, surfaced in the UI by a banner,
  and endpoints that must never run as someone else depend on
  `forbid_impersonation`.
- **Machine access**: customers' own systems authenticate with `X-API-Key`
  against `/api/v1/external/*`, scoped per key by `require_scope`.

### Audit trail

`services/audit_service.py` writes an `audit_logs` row for listing
create/update/cancel, offer accept/reject, organization approve/reject,
transaction completion, admin setting changes, and every support console action
(each of which must also carry a reason).

---

## Domains and endpoints

130 routes under `/api/v1`. One router module per domain, one service behind it.

| Domain | Router | Notes |
|---|---|---|
| Auth | `auth.py` | register, login, refresh, logout, forgot/reset password, me |
| Organizations | `organizations.py` | profile, approval workflow, compliance documents |
| Branches | `branches.py` | per-organization branches and storage compliance |
| Products | `products.py` | catalog and categories, including per-org draft products |
| Inventory | `inventory.py` | batches, FEFO, near-expiry view, near-expiry rules |
| Inventory import | `imports.py` | spreadsheet template, upload, job status, error file |
| Listings | `listings.py` | marketplace listings + eligibility check |
| Offers | `offers.py` | submit, accept, reject, cancel |
| Reservations | `reservations.py` | hold created when an offer is accepted |
| Transactions | `transactions.py` | dispatch, receipt, cold-chain temperature log |
| Disputes | `disputes.py` | raise, evidence, respond, resolve |
| Invoices | `invoices.py` | ZATCA-cleared invoices and their XML |
| Ratings | `ratings.py` | counterparty ratings |
| Reports | `reports.py` | the five reporting endpoints |
| Notifications | `notifications.py` | list, read, preferences |
| Admin | `admin.py` | approvals, compliance, audit logs, moderation, platform settings, cross-pharmacy inventory, draft products, imports |
| Support console | `support/` | accounts, org lifecycle, moderation, customer inventory, acting for a customer, impersonation, customer dashboard |
| API keys | `api_keys.py` | issue and revoke keys, list scopes |
| External | `external.py` | `X-API-Key` integration surface for customer systems |

---

## Key flows

### Listing creation

```
1. Seller picks a batch          GET  /listings/eligibility-check?batch_id=…
2. EligibilityService runs the 10 rules and returns a pass/fail per rule
3. Seller submits                POST /listings
4. ListingService.create_listing re-runs eligibility, checks the quantity
   against the batch, flips the batch to "listed", writes the listing and an
   audit entry
```

The ten rules live in `services/eligibility_service.py`: organization approved
and licensed, branch active, product active and neither restricted nor
controlled, batch unopened and not patient-dispensed, storage compliant, not yet
expired, at least `min_days_for_listing` remaining, and the product category
allowed for exchange.

### Offer → reservation → transaction

```
POST /offers                             buyer offers
POST /offers/{id}/accept                 seller accepts
   → other pending offers on the listing are rejected
   → a Reservation is created with an expiry from platform settings
POST /transactions/from-reservation/{id} transaction opens
POST /transactions/{id}/dispatch         seller dispatches (+ temperature log)
POST /transactions/{id}/confirm-receipt  buyer confirms
   → batch sold, InventoryMovement recorded, listing closed, invoice raised,
     audit entry written
```

A dispute can be raised against a transaction, with evidence, a seller response
and a resolution.

### Inventory import

A pharmacy with thousands of lines uploads the generated spreadsheet rather than
typing batches in. `POST /inventory/import` stores the file and queues an
`import_jobs` row; the scheduler's import worker picks it up, matches products
via `product_matching_service`, writes batches, and produces a downloadable
error file for the rows it could not accept.

---

## Background jobs

`scheduler.py`, started in the app's startup hook and reported by `/ready`:

| Job | Interval | What it does |
|---|---|---|
| `scan_near_expiry_batches` | `NEAR_EXPIRY_SCAN_INTERVAL_HOURS` (6) | Notifies at the 180/90/30-day thresholds, once each, and auto-lists when the organization allows it |
| `expire_stale_reservations` | `RESERVATION_SWEEP_INTERVAL_HOURS` (1) | Releases listings held by reservations nobody completed |
| `retry_invoice_clearance` | `INVOICE_RETRY_INTERVAL_MINUTES` (15) | Re-submits invoices ZATCA has not accepted |
| `process_import_jobs` | `IMPORT_POLL_INTERVAL_SECONDS` (20) | Runs queued inventory imports |

If the scheduler fails to start, `/ready` returns 503 — with it down there is no
expiry scanning, no reservation sweep and no import processing.

---

## Integrations

All of them live in `services/integrations/`, all are selected by an environment
variable, and all default to a stub so that local development and CI never reach
the network.

| Integration | Env | Backends |
|---|---|---|
| Email | `EMAIL_BACKEND` | `stub`, `resend`, `smtp` |
| ZATCA e-invoicing | `ZATCA_MODE` | `stub` (locally signed, marked cleared), `sandbox`, `production` |
| File storage | `STORAGE_*` | local filesystem, with durable copies kept in `stored_files` |

WhatsApp notification delivery is selected by `WHATSAPP_BACKEND` and dispatched
from `services/notification_service.py`.

---

## Data model

25 tables. Every one has a UUID primary key and timezone-aware
`created_at` / `updated_at`; those that can be withdrawn rather than destroyed
also carry `deleted_at`.

```
users ── user_organization_memberships ── pharmacy_organizations
                                              ├── pharmacy_branches
                                              ├── near_expiry_rules
                                              └── api_keys

product_categories ── products                (categories are self-referential)

inventory_batches ── inventory_movements
import_jobs                                   (a queued spreadsheet upload)

marketplace_listings ── listing_views
        └── listing_offers ── reservations ── transactions
                                                   ├── invoices
                                                   ├── disputes
                                                   └── ratings

audit_logs · notifications · notification_preferences · platform_settings
impersonation_sessions · stored_files
```

Migrations are Alembic revisions in `apps/api/alembic/versions/`, numbered
`0001`…`0013`, applied in order. `models/__init__.py` imports every model so
autogenerate sees the whole metadata.

---

## Frontend architecture

- **Routing**: App Router, every screen under `src/app/[locale]/`. The folder
  path is the URL. `middleware.ts` handles locale detection and the auth guard.
- **Language**: next-intl with `ar-SA` primary and `en` secondary; strings live
  in `messages/`. The document is `dir="rtl"` for Arabic.
- **Data**: TanStack Query v5 over the typed client in `lib/api.ts`, which
  exposes one object per backend domain. Auth tokens are held by `lib/auth.ts`
  (zustand + cookies) and attached by an axios interceptor.
- **Components**: `components/ui/` for primitives, `components/layout/` for the
  shell, `components/features/` for components tied to one feature.
- **Errors**: `lib/errors.ts` turns any failure — including a network timeout on
  a cold-started backend — into an Arabic sentence worth showing someone.

Expiry zones are shown consistently everywhere: green over 180 days, yellow
90–180, orange 30–90, red under 30.

---

## Known gaps and drift

Accurate as of this writing, and worth knowing before you go looking for
something that is not there:

- **Invoices and ratings have no UI.** `/api/v1/invoices/*` (4 endpoints) and
  `/api/v1/ratings/*` (3 endpoints) work, are tested, and are reachable by API,
  but nothing in `apps/web` calls them yet. The invoice is raised and cleared
  through ZATCA by the transaction flow regardless.
- **`/api/v1/external/*` is deliberately not called by the web app.** It exists
  for customers' own systems, authenticated by `X-API-Key`, and is documented
  for them on the `/docs/integration` screen.
- **`render.yaml` still declares a Render `databases:` block** for a database
  that no longer exists; the live database is on Neon and `DATABASE_URL` is set
  on the service. See the deployment section of the root README.
- **`packages/types` is listed in the root `package.json` workspaces but does
  not exist.** npm ignores the missing entry, so nothing breaks; shared types
  currently live in `apps/web/src/lib/api.ts`.
- **Docker container names and volumes are prefixed `tickitss_`,** a name from
  before this project was called what it is. Renaming them would orphan existing
  local volumes, so they have been left alone.
