# Directory structure

A map of where everything lives, and where new code should go. Paths are from
the repository root.

---

## Repository

```
/
├── apps/
│   ├── api/            FastAPI backend — all business logic and data access
│   └── web/            Next.js frontend — all UI
├── infra/
│   └── docker/         docker-compose stack + nginx reverse proxy config
├── docs/               Architecture and developer documentation (you are here)
├── .github/workflows/  CI (lint, type check, tests, build) and keep-alive ping
├── render.yaml         Render deployment: the API service, the web service, the database
├── package.json        npm workspaces root — frontend scripts only
└── CLAUDE.md           The original build specification for the platform
```

The two apps deploy independently and share nothing at runtime except the HTTP
contract. There is no shared build step between them.

---

## Backend — `apps/api/`

The backend is a flat Python package rooted at `apps/api`, which is on
`sys.path` (`pythonpath = .` in `pytest.ini`, `prepend_sys_path = .` in
`alembic.ini`). That is why imports read `from services.listing_service import …`
rather than a package prefix.

```
apps/api/
├── main.py             ← ENTRY POINT. App factory, middleware stack, router
│                         registration, startup/shutdown, /health and /ready.
├── config.py             Every environment variable, via pydantic-settings.
│                         If a setting is not here, the app does not read it.
├── database.py           Async engine + AsyncSessionLocal session factory.
├── dependencies.py       FastAPI injectables: DbSession, CurrentUser, SuperAdmin,
│                         OrgAdminOrAbove, ApiKeyAuth, require_scope, impersonation
│                         context. Authorization lives here.
├── scheduler.py          APScheduler jobs: near-expiry scan, reservation sweep,
│                         invoice clearance retry, import worker.
├── httpx_client.py       The one shared HTTP/2 client (singleton).
│
├── auth/                 JWT encode/decode, argon2 hashing, actor context.
├── middleware/           Cross-cutting request handling: logging, Cloudflare
│                         guard, App Check guard, auth throttle.
│
├── routers/              HTTP layer. One module per domain. Parses input,
│                         calls a service, shapes the response. No SQL here.
│   └── support/          The support console, split by the thing acted on
│                         (accounts, organizations, moderation, inventory,
│                         imports, impersonation, customers).
├── services/             Business logic. One class or module per domain.
│   └── integrations/     Adapters for systems outside the platform:
│                         email (Resend/SMTP), ZATCA e-invoicing, file storage.
├── repositories/         Database queries. Every org-scoped query filters by
│                         organization_id here.
├── models/               SQLAlchemy ORM models — one module per table group.
│                         models/__init__.py imports all of them so Alembic
│                         autogenerate can see the full metadata.
├── schemas/              Pydantic v2 request/response models, plus validators.
│
├── alembic/versions/     Migrations, applied in numbered order.
├── seeds/                seed.py (demo dataset) and create_superadmin.py.
├── tests/                pytest suite. Drives the real app in-process over ASGI.
│
├── requirements.txt      Runtime dependencies (what the deployment installs).
├── requirements-dev.txt  Adds pytest, ruff, mypy. CI and local only.
├── .env.example          Every environment variable, documented.
├── alembic.ini, pytest.ini, Dockerfile
```

### The layering rule

```
routers/  →  services/  →  repositories/  →  models/  →  PostgreSQL
             ↘ services/integrations/  →  the outside world
```

A router never queries the database directly and never calls another router.
A service calls repositories, other services, and integrations. A repository
only builds and runs queries. Follow the arrow; do not skip backwards.

---

## Frontend — `apps/web/`

```
apps/web/
├── src/
│   ├── app/
│   │   ├── layout.tsx           ← ROOT LAYOUT. Metadata and globals.css only;
│   │   │                        it renders its children untouched.
│   │   ├── globals.css          Tailwind layers and design tokens.
│   │   ├── [locale]/            Every screen. The folder is the URL.
│   │   │   ├── layout.tsx       The real document: <html lang dir>, fonts, and
│   │   │   │                    the next-intl and TanStack Query providers.
│   │   │   │                    Screens pull in <Shell> themselves.
│   │   │   ├── login/ register/ forgot-password/ reset-password/ pending-review/
│   │   │   ├── dashboard/       KPIs, charts, urgent batches
│   │   │   ├── inventory/       products, batches, near-expiry, import
│   │   │   ├── marketplace/     discovery, listing detail, create listing
│   │   │   ├── my/              the signed-in org's own listings, offers,
│   │   │   │                    reservations, transactions, disputes
│   │   │   ├── org/             profile, branches, API keys
│   │   │   ├── reports/         the five report screens
│   │   │   ├── admin/           super-admin only screens
│   │   │   ├── notifications/   notification centre
│   │   │   └── docs/integration External API documentation for customers
│   │   └── api/v1/[...path]/    Server-side proxy to the backend, so the
│   │                            browser never calls it cross-origin.
│   ├── components/
│   │   ├── ui/                  Presentational primitives — button, card, badge,
│   │   │                        data-table, expiry-badge, kpi-card, brand-logo.
│   │   ├── layout/              Shell, navbar, sidebar, impersonation banner.
│   │   ├── features/            Components tied to one feature and shared by
│   │   │   ├── disputes/        more than one screen in it.
│   │   │   └── organization/
│   │   └── providers.tsx        TanStack Query + toaster composition root.
│   ├── lib/
│   │   ├── api.ts               Typed API client. One exported object per
│   │   │                        backend domain (authApi, inventoryApi, …).
│   │   ├── auth.ts              Auth store (zustand) and token cookies.
│   │   ├── impersonation.ts     Support impersonation state.
│   │   ├── errors.ts            Turns any failure into a message worth showing.
│   │   └── utils.ts             cn(), currency and date formatting, expiry zones.
│   ├── i18n/                    next-intl configuration.
│   └── middleware.ts            Locale detection + route auth guard.
├── messages/ar.json, en.json    Every UI string. Arabic is primary.
├── public/                      Static assets.
├── next.config.ts, tailwind.config.ts, tsconfig.json, eslint.config.mjs
└── .env.example, Dockerfile
```

---

## Where do I go to change X?

| I want to… | Go to |
|---|---|
| Change what the API exposes over HTTP | `apps/api/routers/<domain>.py` |
| Change a business rule | `apps/api/services/<domain>_service.py` |
| Change a database query or add an index-friendly filter | `apps/api/repositories/<domain>.py` |
| Add or change a table or column | `apps/api/models/` + a new `apps/api/alembic/versions/` migration |
| Change a request or response shape | `apps/api/schemas/<domain>.py` |
| Change who is allowed to call something | `apps/api/dependencies.py` (guards), then the route's dependency |
| Change token lifetime, hashing, or claims | `apps/api/auth/` |
| Change listing eligibility | `apps/api/services/eligibility_service.py` |
| Change a background job or its schedule | `apps/api/scheduler.py` |
| Change email, ZATCA, or file storage behaviour | `apps/api/services/integrations/` |
| Add an environment variable | `apps/api/config.py` **and** `apps/api/.env.example` |
| Change something support staff can do | `apps/api/routers/support/` |
| Add or change a screen | `apps/web/src/app/[locale]/…/page.tsx` |
| Change how the frontend calls the API | `apps/web/src/lib/api.ts` |
| Change a shared UI primitive | `apps/web/src/components/ui/` |
| Change the sidebar, navbar, or shell | `apps/web/src/components/layout/` |
| Change Arabic or English wording | `apps/web/messages/ar.json`, `en.json` |
| Change expiry zone colours or thresholds | `apps/web/src/lib/utils.ts` (display) and `apps/api/config.py` (notifications) |
| Add a backend test | `apps/api/tests/test_<area>.py` |
| Change the local Docker stack | `infra/docker/docker-compose.yml` |
| Change the deployed services | `render.yaml` |
| Change CI | `.github/workflows/ci.yml` |
