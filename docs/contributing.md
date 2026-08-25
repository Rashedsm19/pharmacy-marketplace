# Working on this project

How to run it, how to add to it, and the conventions worth keeping. Read
[architecture.md](architecture.md) first if you have not.

---

## Running it

### Backend

```bash
cd apps/api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # requirements.txt + pytest/ruff/mypy
cp .env.example .env                       # then set DATABASE_URL and the secrets
alembic upgrade head
python seeds/seed.py
uvicorn main:app --reload --port 8000
```

`/docs` and `/redoc` are served whenever `APP_ENV` is not `production`.

### Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local                 # NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm run dev                                # http://localhost:3000/ar/login
```

### Everything at once

```bash
cd infra/docker && docker compose up -d    # postgres, redis, api, web, nginx on :80
```

---

## Tests, lint, types

```bash
cd apps/api
pytest -q                 # the whole suite; drives the real app in-process over ASGI
pytest -m slow -q         # the ten-thousand-row import, excluded from the default run
ruff check .
mypy . --ignore-missing-imports

cd apps/web
npm run type-check        # tsc --noEmit, strict
npm run lint
npm run build
```

The backend suite needs a PostgreSQL database and takes `DATABASE_URL` from the
environment (`conftest.py` defaults to `postgres:postgres@localhost/pharmacy_test`).
`conftest.py` builds the schema with `Base.metadata.create_all`, which adds
missing **tables** but never missing **columns** — after a migration that alters
an existing table, drop and recreate the test database or the suite will run
against the old schema.

---

## Adding an API endpoint

1. **Schema** — request and response models in `apps/api/schemas/<domain>.py`.
2. **Repository** — any new query in `apps/api/repositories/<domain>.py`, filtered
   by `organization_id` unless it is deliberately platform-wide.
3. **Service** — the rule itself in `apps/api/services/<domain>_service.py`:
   validation, the state change, the audit entry, the notification.
4. **Router** — the route in `apps/api/routers/<domain>.py`. Take `DbSession` and
   the right identity dependency (`CurrentUser`, `OrgAdminOrAbove`, `SuperAdmin`,
   or `ApiKeyAuth` + `require_scope`). Parse, call the service, return the schema.
5. **Register** — a new router module must be included in `_register_routers()`
   in `main.py`. Registration order decides which route wins when two could
   match the same path, so add it where its prefix does not shadow an existing one.
6. **Client** — add the call to the matching object in `apps/web/src/lib/api.ts`.
7. **Test** — `apps/api/tests/test_<area>.py`.

## Adding a service

New domain logic goes in `apps/api/services/`, one module per domain. A service
may call repositories, other services and integrations; it must not import a
router. Anything that talks to a system outside the platform belongs in
`services/integrations/` instead, behind an env-selected backend with a `stub`
default so tests and local development never reach the network.

## Adding a table or column

1. Add or edit the model in `apps/api/models/`, and export it from
   `models/__init__.py` — Alembic autogenerate only sees what is imported there.
2. `alembic revision --autogenerate -m "what changed"`, then read the generated
   migration before trusting it.
3. Keep the numbered filename convention: `00NN_short_name.py`.
4. Recreate the test database before running the suite (see above).

Every table gets a UUID primary key and timezone-aware `created_at` /
`updated_at`; add `deleted_at` when the row should be withdrawn rather than
destroyed.

## Adding a screen

1. Create `apps/web/src/app/[locale]/<path>/page.tsx` — the folder path is the URL.
2. Wrap the content in `<Shell>` from `@/components/layout/shell` if it is an
   authenticated screen, and add it to the sidebar in
   `@/components/layout/sidebar` if it deserves a link.
3. Fetch through `@/lib/api` with TanStack Query; do not call axios directly.
4. Put strings in `messages/ar.json` and `messages/en.json`. Arabic is the
   primary language: no diacritics, professional register.
5. A component used by more than one screen in the same feature goes in
   `components/features/<feature>/`; a generic one goes in `components/ui/`.
6. If the screen is public, add its path to `PUBLIC_PATHS` in
   `apps/web/src/middleware.ts`, otherwise the auth guard will redirect it.

## Adding an environment variable

Add it to `apps/api/config.py` **and** `apps/api/.env.example` (or
`apps/web/.env.example` for the frontend), with a default that is safe in
development. If a deployment needs it, add it to `render.yaml` and to
`infra/docker/docker-compose.yml`.

## Adding a background job

Write the coroutine in `apps/api/scheduler.py` and register it in
`create_scheduler()` with an interval that comes from `config.py`, not a
literal.

## Adding a test

`apps/api/tests/test_<area>.py`. `conftest.py` gives you a `client` fixture
bound to the real app over ASGI, an `admin_token`, a `seller_token` and a
`buyer_token`, and a database seeded once for the session. The seeded accounts
are listed in `SEEDED` there.
Tests exercise the real app over ASGI, so a test failure is a real request
failing — write them against endpoints rather than calling services directly
unless the unit genuinely stands alone.

---

## Conventions

- **Arabic user-facing text.** Error messages, notifications and UI copy are
  Arabic, without diacritics, in the register a Saudi business writes in.
- **Explain refusals.** A guard returns a reason a person can act on, never a
  silent no-op.
- **Audit anything done to someone else's data.** Support console actions take a
  reason and write an `audit_logs` entry.
- **Never trust the request for identity.** `organization_id` comes from the
  token; a body that carries one is input to validate, not a source of truth.
- **Comments explain why**, not what. The existing code is written that way;
  match it.
