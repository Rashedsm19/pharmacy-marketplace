# AGENTS.md — Pharmacy Near-Expiry Marketplace
# Agent Execution Instructions (Codex)

## IDENTITY

You are a senior full-stack architect and autonomous implementation agent.
Your sole task is to fully build the **Pharmacy Near-Expiry Marketplace** platform for Saudi Arabia as defined in this file.
You do not ask for permission. You do not stop between phases. You do not simplify scope.
You create every file, write every line, and finish every phase before reporting back.

---

## EXECUTION RULES (NON-NEGOTIABLE)

1. Read this entire file before writing a single line of code.
2. Execute phases in strict order: 1 → 2 → 3 → 4 → 5.
3. Never stop mid-phase. If a file is large, continue until it is complete.
4. Never reduce scope. Never skip a module, screen, or feature.
5. Never use placeholder comments like `# TODO` or `# implement later` unless it is an explicitly marked external integration stub.
6. Every file must be production-ready and runnable on first try.
7. After each phase completes, print a one-line summary: `✅ Phase N complete — X files created` then immediately start the next phase.
8. Do not ask the user anything. If ambiguous, use the safest, most complete interpretation.
9. If a file exceeds context, split it into logical parts and create both parts before moving on.
10. After Phase 5, run a final self-check: list any file that is missing or incomplete and fix it.

---

## TECH STACK (MANDATORY — NO SUBSTITUTIONS)

### Backend
- Python 3.12
- FastAPI with `default_response_class=ORJSONResponse`
- `docs_url=None`, `redoc_url=None`, `openapi_url=None` in production
- uvloop (enable when available, graceful fallback)
- orjson
- SQLAlchemy 2.0 async + asyncpg
- PostgreSQL
- Alembic for migrations
- Pydantic v2
- One shared `httpx.AsyncClient` with HTTP/2 (singleton pattern)
- JWT access + refresh tokens
- argon2 password hashing
- APScheduler for periodic near-expiry scans
- Logging via `LOG_LEVEL` / `NOLOG` env vars
- Firebase App Check toggle via `REQUIRE_APPCHECK` env var
- Cloudflare header guard via `REQUIRE_CLOUDFLARE` env var

### Frontend
- Next.js 15+ App Router
- TypeScript (strict mode)
- Tailwind CSS
- shadcn/ui
- React Hook Form + Zod
- TanStack Query v5
- next-intl (Arabic ar-SA primary, English en secondary)
- RTL-first layout (`dir="rtl"` on html, all layouts RTL)
- Responsive — desktop-optimized, mobile-friendly

### Infrastructure
- Docker + docker-compose (full local dev stack)
- Nginx reverse proxy config
- `.env.example` for all apps
- GitHub Actions CI skeleton

---

## MONOREPO STRUCTURE (CREATE THIS EXACTLY)

```
/
├── apps/
│   ├── api/          # FastAPI backend
│   └── web/          # Next.js frontend
├── packages/
│   └── types/        # Shared TypeScript types/contracts
├── infra/
│   └── docker/       # docker-compose + nginx
├── docs/
│   └── architecture.md
├── AGENTS.md         # This file
└── README.md
```

---

## PHASE 1 — Monorepo Structure + Backend Foundation

Create:
- Root `README.md` (placeholder, will be completed in Phase 5)
- Root `package.json` (workspaces config)
- `apps/api/` full FastAPI foundation:
  - `main.py` — app factory with all middleware, CORS, health endpoint, uvloop bootstrap
  - `config.py` — all env vars via pydantic-settings
  - `database.py` — async SQLAlchemy engine + session factory
  - `dependencies.py` — FastAPI dependency injectors (db session, current user, role guards)
  - `auth/` — JWT utilities, token creation, refresh, password hashing
  - `middleware/` — Cloudflare guard, App Check guard, logging middleware
  - `models/` — ALL SQLAlchemy models (see Data Model section below)
  - `schemas/` — ALL Pydantic v2 schemas for every model
  - `alembic/` — configured Alembic with initial migration
  - `requirements.txt` — all pinned dependencies
  - `.env.example` — all env vars with descriptions
  - `Dockerfile`

---

## PHASE 2 — Backend Modules + Migrations + Seeds

Create all routers, services, and repositories:

### Routers (all under `/api/v1/`)
- `auth` — register, login, refresh, logout, forgot-password, reset-password
- `organizations` — CRUD + approval workflow
- `branches` — CRUD per organization
- `products` — product catalog CRUD
- `inventory` — batch CRUD, FEFO query, near-expiry filter
- `listings` — create listing (with eligibility validation), list, update, cancel
- `offers` — submit offer, accept, reject, cancel
- `reservations` — create, expire, confirm
- `transactions` — seller dispatch, buyer receipt, completion
- `reports` — all 10 reports (see Reports section)
- `admin` — approvals queue, moderation, platform settings, audit logs
- `notifications` — list, mark read, preferences

### Services
One service class per domain. Services hold all business logic.
Services never call other routers. Services call repositories only.

### Repositories
One repository per model. Repositories hold all DB queries.
All queries must filter by `organization_id` to enforce tenant isolation.
Super admin bypass is explicit and gated by role check only.

### Near-Expiry Scanner
- APScheduler job running every 6 hours
- Scans all `inventory_batches` for approaching expiry
- Creates notifications for 180 / 90 / 30 day thresholds
- Optionally triggers auto-listing if org rule `allow_auto_listing=True`

### Eligibility Engine
All 10 eligibility rules from the spec must be enforced as a service function
`check_listing_eligibility(batch_id, org_id) -> EligibilityResult`
returning pass/fail per rule with reasons. This is called on every listing creation.

### Migrations
- `alembic revision --autogenerate` for full schema
- Include seed migration or separate `seeds/seed.py` script

### Seed Data
Create `apps/api/seeds/seed.py`:
- 1 super admin user
- 3 pharmacy organizations (1 approved, 1 pending, 1 suspended)
- 5 branches (distributed across orgs)
- 30 products across all categories
- 60 inventory batches:
  - 15 batches expiring in 180 days (yellow zone)
  - 15 batches expiring in 90 days (orange zone)
  - 10 batches expiring in 30 days (red zone)
  - 20 batches healthy (>180 days)
- 10 active marketplace listings
- 8 listing offers (mix of statuses)
- 5 completed transactions

---

## PHASE 3 — Frontend Foundation + Auth + Dashboard

### Setup
- `apps/web/` Next.js 15 App Router project
- `tailwind.config.ts` with RTL support and Frova-style neutral palette
- `next.config.ts` with next-intl plugin
- `messages/ar.json` and `messages/en.json` — all UI strings in both languages
- `lib/api.ts` — typed Axios/fetch API client pointing to backend
- `lib/auth.ts` — auth state, token management
- `components/ui/` — shadcn/ui components
- `components/layout/` — Sidebar, Navbar, RTL-aware Shell
- `middleware.ts` — next-intl locale detection + auth guard

### Auth Screens
- `/login` — email/password login, RTL form
- `/register` — org registration multi-step form (org info → branch info → documents)
- `/pending-review` — post-registration waiting page
- `/forgot-password` and `/reset-password`

### Dashboard Screen (`/dashboard`)
- KPI cards: active listings, near-expiry batches, pending offers, monthly recovered value
- Near-expiry summary table (top 10 urgent batches)
- Active listings summary
- Incoming offers widget
- Expiry risk chart by month (bar chart using Recharts or shadcn charts)
- Inventory health donut chart

---

## PHASE 4 — Inventory + Marketplace UI

### Inventory Screens
- `/inventory/products` — product catalog table with search/filter
- `/inventory/batches` — all batches with expiry status color coding
- `/inventory/batches/new` — add batch form
- `/inventory/batches/[id]` — batch detail + FEFO recommendation panel
- `/inventory/near-expiry` — filtered view, status badges (yellow/orange/red)

### Marketplace Screens
- `/marketplace` — listings discovery with full filter sidebar
- `/marketplace/[id]` — listing detail with offer/reserve/buy actions
- `/marketplace/create` — create listing flow with eligibility check result
- `/my/listings` — seller's own listings management
- `/my/offers` — buyer's submitted offers
- `/my/incoming-offers` — seller's received offers
- `/my/reservations` — active reservations
- `/my/transactions` — transaction history

### Organization + Branches
- `/org/profile` — org info, compliance status, documents
- `/org/branches` — branch list + add/edit inline
- `/org/branches/[id]` — branch detail + storage compliance

### Reports
- `/reports/near-expiry` — near expiry by branch
- `/reports/expired-loss` — expired stock loss
- `/reports/recoverable-value` — recoverable value dashboard
- `/reports/top-products` — most requested products
- `/reports/branch-comparison` — branch performance comparison

---

## PHASE 5 — Admin + Docker + README + Final Validation

### Admin Screens (role: super_admin only)
- `/admin/approvals` — pending pharmacy approval queue with approve/reject actions
- `/admin/compliance` — compliance review queue
- `/admin/settings` — platform-wide settings (eligibility thresholds, listing rules)
- `/admin/categories` — restricted category rules management
- `/admin/moderation` — marketplace listing moderation
- `/admin/audit-logs` — full audit trail table with filters

### Notification System
- Backend: `notifications` table + service that creates records on every trigger event
- Frontend: bell icon in navbar, dropdown list, mark-as-read, badge count
- Adapter interfaces for email (Resend/SMTP stub) and WhatsApp (Meta Cloud API stub)

### Infrastructure
- `infra/docker/docker-compose.yml` — postgres, redis (for future use), api, web, nginx
- `infra/docker/nginx.conf` — reverse proxy: `/api` → FastAPI, `/` → Next.js
- `apps/api/Dockerfile` and `apps/web/Dockerfile`
- `.github/workflows/ci.yml` — lint + test skeleton for both apps

### README
Complete `README.md` at root:
- Project description
- Architecture diagram (text/ASCII)
- Prerequisites
- Local dev setup (docker-compose up)
- Manual setup steps (backend + frontend)
- Seed data instructions
- Env var reference
- API endpoint summary table
- Deployment notes (Cloud Run or VPS)

### Final Validation
After all files are created:
1. Print the complete file tree
2. Identify any file that references an import not yet created and fix it
3. Confirm every API route has a matching frontend screen
4. Confirm every env var in code exists in `.env.example`
5. Print: `✅ BUILD COMPLETE — Pharmacy Near-Expiry Marketplace ready for local dev`

---

## DATA MODEL (IMPLEMENT ALL)

Tables (exact field names must match):
`users`, `pharmacy_organizations`, `pharmacy_branches`,
`user_organization_memberships`, `product_categories`, `products`,
`inventory_batches`, `near_expiry_rules`, `marketplace_listings`,
`listing_views`, `listing_offers`, `reservations`, `transactions`,
`inventory_movements`, `audit_logs`, `notifications`,
`notification_preferences`, `platform_settings`

All tables must have:
- `id` as UUID primary key
- `created_at` / `updated_at` as timezone-aware timestamps
- Soft delete via `deleted_at` nullable timestamp where applicable

All foreign keys must have proper SQLAlchemy relationships.
All enums must be Python `enum.Enum` classes, not raw strings.

---

## SECURITY RULES (ENFORCED IN CODE)

- Every protected endpoint must call `get_current_user` dependency
- Every org-scoped query must filter by `organization_id` from the token
- Super admin bypass must be explicit: `if current_user.role == UserRole.SUPER_ADMIN`
- CORS must be configured from env var `ALLOWED_ORIGINS` — no wildcard in production
- All file uploads must validate mime type + size before storage
- Audit log must be written for: listing create/update/cancel, offer accept/reject, org approve/reject, transaction complete, admin setting change

---

## MARKETPLACE ELIGIBILITY RULES (ALL MUST BE ENFORCED)

Function `check_listing_eligibility` must validate:
1. Organization status == `approved`
2. Organization `is_licensed` == True
3. Branch `is_active` == True
4. Product `is_active` == True and not `is_restricted` and not `is_controlled`
5. Batch `is_opened` == False
6. Batch `is_patient_dispensed` == False
7. Batch `storage_condition_status` == `compliant`
8. Batch `expiry_date` > today
9. Days until expiry >= `min_days_for_listing` from org's `near_expiry_rules`
10. Product category `is_exchange_allowed_default` == True (or explicitly overridden)

Return structured result per rule with pass/fail + reason string.

---

## UX RULES (ALL SCREENS)

- `dir="rtl"` and `lang="ar"` on html element
- All labels, buttons, placeholders in Arabic by default
- Expiry status colors:
  - `> 180 days` → green badge
  - `90–180 days` → yellow badge
  - `30–90 days` → orange badge
  - `< 30 days` → red badge
- Tables must have: search, column filters, pagination, row actions
- All forms must have: validation messages in Arabic, loading states, success/error toasts
- Empty states must have helpful Arabic copy + action button
- All currency displayed as `ر.س` (SAR)

---

## BEGIN EXECUTION

Start immediately with Phase 1.
Create every file.
Do not stop until `✅ BUILD COMPLETE` is printed.
