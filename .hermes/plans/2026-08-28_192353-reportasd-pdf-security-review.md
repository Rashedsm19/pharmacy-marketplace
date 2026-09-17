# تقرير تحسينات وثغرات نظام صيدليات Near-Expiry — خطة إعداد reportasd.pdf

> **For Hermes:** Execute in one shot — generate the PDF with reportlab (already installed). No code changes to the system. Read-only analysis already done.

**Goal:** Produce a professional, read-only PDF report (`reportasd.pdf`) documenting system strengths, vulnerabilities/gaps, and recommended improvements — without deleting or modifying anything in the system.

**Architecture:** Single standalone Python script (reportlab, system python3 with reportlab 5.0.1 installed via pip --user) generates a styled PDF: cover page, executive summary, severity-classified findings table, per-domain sections (Security, Testing, Infra, Data, UX), recommendations roadmap. Arabic text rendered with a system Arabic-capable TTF font (macOS: /System/Library/Fonts — e.g. GeezaPro / SF Arabic); RTL shaping via `arabic_reshaper` fallback: if unavailable, report is authored in English with Arabic terms transliterated/quoted — verify font shaping first; if shaping is broken, ship bilingual (English body, Arabic quoted strings) to guarantee readability.

**Tech Stack:** Python 3.13 (system) + reportlab 5.0.1; no project dependencies touched.

---

## Verified evidence gathered (source of report content — all measured, not assumed)

### Build / Test status (measured this session)
- Lint (web): PASS — 1 minor warning (`no-page-custom-font` in `src/app/[locale]/layout.tsx:35`).
- Next.js build: PASS (all routes compile).
- Backend tests: 157/158 PASS, 1 FAIL — `tests/test_support_actions.py::test_the_dashboard_summarises_every_customer` (flaky: assumes a `batches>0` org is within first 50 rows ordered by `created_at desc`; ~65 test-created orgs push seeded orgs off page 1).
- Test env: `tests/conftest.py` hardcodes `postgres:postgres@localhost:5432/pharmacy_test`; local brew postgres@16 has no `postgres` role → 158 errors without manual `DATABASE_URL`. Local DB has 67 orgs / 148 batches (test residue present).

### Strengths found (verified in code)
- Argon2 password hashing (`apps/api/auth/password.py`), JWT with `jti` field, separate access/refresh expiries (`auth/jwt.py`).
- Refresh blocked for suspended orgs (`services/auth_service.py` refresh gate, `_BLOCKED_STATUSES`).
- Forgot-password returns generic message (no email enumeration), hashed reset tokens with expiry.
- Auth throttle middleware per-path with Retry-After in Arabic (`middleware/throttle.py`); nginx `limit_req` zones (`infra/docker/nginx.conf`).
- File upload validation: extension allowlist + XLSX zip magic-byte check + size cap (`services/integrations/storage_service.py:156`).
- Seed refuses default passwords in production (`seeds/seed.py:68`); `render.yaml` sets `SEED_ON_STARTUP=false`.
- Audit logging present across admin/support/listings/organizations (`services/audit_service.py`).
- Impersonation has reason field, session review, blocks minting API keys, cannot target super_admin (tested).
- Cold-chain temperature log enforced before dispatch (tested).
- CORS from env, Cloudflare/AppCheck toggles, health endpoint, migrations-on-startup.

### Gaps / findings (verified)
1. **Logout is stateless** — comment at `routers/auth.py:43`: no server-side revocation of access tokens after logout/compromise; `jti` exists but no denylist. Severity: MEDIUM.
2. **No refresh-token rotation/revocation** — same refresh token reusable until expiry (7 days). Severity: MEDIUM.
3. **Secrets have insecure defaults** — `config.py:26,52` fallback strings; app runs if env missing instead of failing fast. Severity: LOW (render.yaml generates) — recommend startup check.
4. **No security headers from the API itself** — headers only in nginx (X-Frame-Options etc.); no HSTS, no CSP anywhere. Severity: LOW-MEDIUM (depends on deployment).
5. **Throttle is in-process** — per-instance limits on multi-worker deployment; comment admits it. No Redis. Severity: LOW-MEDIUM.
6. **Failing/flaky dashboard test** — `test_the_dashboard_summarises_every_customer` fails when test-created orgs exceed page 1. Severity: MEDIUM (CI signal loss).
7. **Test DB URL hardcoded** — `tests/conftest.py:23` breaks on non-default local postgres (reproduced: 158 errors). Severity: LOW.
8. **`listing_views` table has no router usage** — listed in data model, no write path found; view-count feature dead. Severity: LOW (product gap).
9. **Minor lint warning** — custom font loaded in layout, not `_document`. Severity: LOW.
10. **Test residue in local DB** — 67 orgs incl. many `Sahha Pharmacies <hash>` leftovers; no test-DB teardown strategy between runs. Severity: LOW.
11. **`.env.render` in repo dir** — properly gitignored (`git check-ignore` confirmed, mode 600). Report as OK/verified, no action.
12. **Frontend offer/reserve UX, notifications bell, RTL** — not deeply audited this session; report scope note.

### Improvement roadmap (report Section 5)
- P1: Fix flaky test (query across pages or order by seed marker); fix conftest DATABASE_URL override.
- P1: Token revocation via `jti` denylist (Redis or DB) + refresh rotation.
- P2: Fail-fast secret validation in `config.py`; HSTS/CSP in nginx; security headers middleware for API.
- P2: Centralized throttle store (Redis) when scaling >1 instance.
- P3: Wire up `listing_views` or drop from spec docs; add test-DB cleanup fixture; lint warning fix.

---

## Execution plan (single task)

### Task 1: Generate reportasd.pdf

**Files:**
- Create: `/Users/rashed/phr/.hermes/plans/` (already), and script at `/Users/rashed/phr/.hermes/plans/gen_reportasd.py` (temp, outside project source)
- Output: `/Users/rashed/phr/reportasd.pdf`

**Step 1:** Probe Arabic font shaping: list `/System/Library/Fonts/Supplemental/GeezaPro*.ttf`, test render with reportlab; if `arabic_reshaper`+`python-bidi` not installed, `pip3 install --user arabic-reshaper python-bidi` (allowed — tooling only, not project).
**Step 2:** Write `gen_reportasd.py` implementing:
- Cover page (title, date, repo, commit 2ddb095, "read-only analysis — no system changes").
- Executive summary with severity counts (from findings above).
- Verified-strengths table with file:line references.
- Findings table: ID, severity, file:line, description, recommendation.
- Test/build measured results table.
- Prioritized roadmap P1/P2/P3.
- Footer with page numbers; professional layout (colors, section rules, headers).
**Step 3:** Run script → verify PDF exists, open page count, spot-check text extraction (`pdftotext` if present, else reportlab sanity).
**Step 4:** Confirm zero modifications to project source: `git status` clean except untracked `reportasd.pdf`.

**Verification:** `ls -la /Users/rashed/phr/reportasd.pdf` + page count + `git status` shows no modified tracked files.
