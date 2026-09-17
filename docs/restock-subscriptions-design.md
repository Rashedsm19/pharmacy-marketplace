# Design — Smart Re-Stock Intelligence + Organization SaaS Subscriptions

Reference for the two capabilities added on top of the existing FastAPI + Next.js
marketplace. Product context: `product-comparison-v2.pdf` (gaps 2 and 3).
Aumet evidence: `smart_restock` module (restock_days 1–180, safety stock %,
velocity aging <30d moving / <90d moderate / else stagnant) and
`/subscription-plans` (starter/growth/scale tiers, monthly/annual, trial days,
usage limits with 80% alerts, paid add-ons, reactivation endpoint).

## Shared conventions

- Org isolation: every query filters by `organization_id` from the caller's
  membership; super-admin bypass stays explicit.
- Every state-changing action writes an `AuditService` entry and (where a user
  should hear about it) a bilingual `NotificationService` record.
- New `NotificationType` values already added: `TEAM_MEMBER_JOINED` (fixes the
  `rbac_service` crash), `RESTOCK_RECOMMENDATION`, `USAGE_LIMIT_WARNING`,
  `SUBSCRIPTION_TRIAL_ENDING`, `SUBSCRIPTION_PAYMENT_FAILED`,
  `SUBSCRIPTION_EXPIRED`, `SUBSCRIPTION_RENEWED`.
- No entitlement caching: checks hit the database per request, so an effective
  subscription change applies immediately by construction.
- New tunables live in `platform_settings` (catalog entries in
  `services/settings_catalog.py`), never hard-coded.

## 1. Smart Re-Stock & Listing Intelligence

### Data reality (verified)

- Demand signal: `inventory_movements` rows of type `dispensed` are the only
  honest consumption record. Marketplace `sold`/`transferred` movements are
  inter-pharmacy transfers and are never counted as consumption.
- Nothing recorded → `evidence_strength = insufficient` and no quantity is
  suggested. Fallbacks are configurable, never invented numbers.
- No supplier lead-time data exists; `restock.lead_time_days` (default 7) is a
  documented configurable fallback.
- `inventory_batches.quantity_available` is already net of live listings and
  reservations; expired batches are excluded from usable supply.

### Model — `restock_recommendations` (extends the WIP model)

Added columns: `kind` (`replenishment` | `listing`), `status`
(`new` | `viewed` | `accepted` | `dismissed` | `acted` | `superseded`),
`batch_id` (nullable, the batch behind a listing recommendation),
`evidence_strength` (`sufficient` | `sparse` | `insufficient`),
`demand_window_days`, `incoming_qty`, `inputs` (JSONB snapshot of every
calculation input), `reason_en`.
Unique constraint becomes `(branch_id, product_id, kind)`.

### Calculations (reproducible)

- `daily_velocity = dispensed_total(window) / window_days`,
  `window = restock.demand_window_days` (default 90).
- `usable_stock = Σ quantity_available` over active, unexpired batches.
- `days_of_cover = usable_stock / daily_velocity` (null when velocity = 0).
- `reorder_point = (lead_time_days + restock.safety_stock_days[7]) × velocity`.
- `target_stock = (lead_time + safety + restock.review_period_days[14]) × velocity`.
- `suggested_qty = max(0, ceil(target − usable − incoming))`; `incoming` =
  open reservations + in-flight purchases by this org for this product.
- Expiry cap: a suggested purchase never exceeds the demand consumable before
  the matched listing's remaining shelf life.
- Evidence: `insufficient` when dispensed history spans <
  `restock.min_evidence_days` (14) or is zero; `sparse` below half the window;
  else `sufficient`.

### Buyer replenishment

Action `buy_from_marketplace` when a matching active listing exists (same
product, quantity available, remaining shelf life ≥ `restock.min_buy_shelf_life_days`
(60), lowest unit price first); else `reorder_supplier`; `hold` when cover is
healthy or evidence insufficient. `matched_listing_id` links the deal; acting
on it records `acted` and hands the user to the existing offer/reserve flow.

### Seller listing recommendations

For each branch/product with unexpired `quantity_available > 0` and
`days_to_expiry ≤` the org's yellow threshold (default 180) and ≥
`min_days_for_listing`: `surplus = max(0, available − velocity × days_to_expiry)`
(velocity unknown → surplus = available, evidence marked). Suggested price
evidence chain: median unit price of completed transactions for the same
product (180 days) → `product.standard_price` → none (user must enter a price);
each multiplied by the zone discount (`near_expiry_rules.auto_listing_discount_pct`,
documented fallback). `inputs` records which evidence was used.

### Lifecycle

Recompute is an upsert keyed by the unique constraint; `acted`/`accepted` rows
are left untouched; a `dismissed` row is not regenerated until its input
signature changes or `restock.dismiss_cooldown_days` (7) passes; stale rows
whose inputs no longer hold become `superseded`. Actions: view, dismiss, act
(seller: creates a real listing through `ListingService` — eligibility and
entitlements are revalidated at submit time). All actions are audited.

### Endpoints (`/api/v1/restock`)

`GET /recommendations` (filters kind/status/branch), `GET /recommendations/{id}`,
`POST /recommendations/refresh` (org recompute, idempotent),
`POST /recommendations/{id}/dismiss`, `POST /recommendations/{id}/act`,
plus `POST /inventory/movements` (record `dispensed`/`adjusted` — the honest
demand source). Scheduler job `restock_recompute` every 6 h after the expiry
scan. Feature-gated by entitlement `restock_intelligence`.

## 2. Organization SaaS Subscriptions

### Tables

- `subscription_plans` — code, bilingual names/descriptions, `version`
  (unique `(code, version)`), `monthly_price`, `annual_price`, `currency`,
  `trial_days`, `limits` JSONB, `is_active`, `is_public`, `sort_order`.
- `organization_subscriptions` — one per org: `plan_id`, `plan_snapshot` JSONB
  (frozen at subscribe/change so plan edits never rewrite history),
  `status` (`trialing` | `active` | `past_due` | `cancelled` | `expired`),
  `billing_cycle` (`monthly` | `annual`), `current_period_start/end`
  (null end = complimentary, renewal job skips), `trial_start/end`,
  `cancel_at_period_end`, `grace_until`, `pending_plan_id` (downgrade at period
  end), `proration_credit`.
- `subscription_events` — append-only lifecycle history with payloads.
- `subscription_invoices` — per-period billing records (idempotent per
  `(subscription_id, period_start)`), provider refs, VAT. Kept separate from
  the ZATCA marketplace invoice chain; ZATCA e-invoicing of subscription fees
  is a declared follow-up, not claimed here.
- `payment_events` — webhook inbox, unique `(provider, event_id)`, processed
  flag + result; duplicate/out-of-order safe.
- `organization_addons` — paid limit boosters (`code`, `quantity`, window,
  status) that add on top of plan limits.
- `usage_counters` — `(org_id, period_start, metric)` counts with
  `warned_80` flag; increments go through `usage_ledger` idempotency keys so
  retries never double-count.

### Limits and entitlements (plan `limits` JSONB)

`max_active_listings`, `max_branches`, `max_team_members` (active resources,
counted live), `max_listings_per_period` (per-period usage, resets each billing
period), and boolean features `advanced_reports`, `restock_intelligence`,
`api_access`. `null` = unlimited. Defined precisely in the admin UI copy.

### Lifecycle policy (explicit, configurable)

- Trial: once per organization ever (`organizations.trial_used_at`); expires to
  `expired` when unpaid; a 3-day-before reminder fires once.
- Activation/renewal only via verified webhook (never a browser redirect).
- Upgrade from a paid period: immediate; prorated difference recorded as an
  invoice/credit (`billing.proration_policy`, default `immediate_prorated`).
- Upgrade from a complimentary (legacy, no-period) subscription: treated as a
  full purchase — checkout for the whole cycle, plan switches only when the
  invoice settles via webhook; a failed payment clears the pending upgrade and
  leaves the organization on its current plan (never `past_due`).
- Downgrade: scheduled to the next period start (`pending_plan_id`).
- Cancel: `cancel_at_period_end`; access keeps working until period end.
- Failed renewal: `past_due` + `grace_until = now + billing.grace_period_days`
  (default 3); success inside grace restores `active`; grace lapse → `expired`.
- Expired orgs keep every record; new limited actions are blocked, nothing is
  deleted. Reactivation: pick a plan, pay, back to `active`.
- A paid subscription never overrides org suspension, licensing, eligibility or
  any compliance control.

### Enforcement (server-side)

`EntitlementService` (public API consumed by other domains):

- `get_entitlements(org_id) -> Entitlements` — plan snapshot + active add-ons,
  gated by subscription status (`trialing`/`active`/`past_due` in grace are
  entitled; complimentary never expires).
- `require_feature(org_id, feature)` — 403 with upgrade hint.
- `check_resource_limit(org_id, limit_key, current_count)` — 403 at the cap.
- `record_usage(org_id, metric, amount, idempotency_key)` — ledger-guarded.
- `usage_summary(org_id)` — live counts + counters + ratios for meters.

Hooks: listing creation (resource + per-period), branch creation, team
invites, API-key creation, advanced reports (`recoverable-value`,
`branch-comparison`), restock endpoints. Count-checked writes take a row lock
on the org's subscription (`SELECT … FOR UPDATE`) so concurrent requests
cannot both pass. 80% crossings notify owners once per metric per period.
Commercial status never gates compliance-critical reads.

### Existing organizations (migration policy)

A data migration creates a `legacy` plan (prices 0, generous limits matching
the current platform settings, all features on, marked non-public) and a
complimentary `active` subscription with no period end for every existing
organization — nobody is locked out by the upgrade.

### Billing boundary

Reuses `services/integrations/payment_service.py` (`PaymentProvider` protocol,
HMAC-verified webhooks; HyperPay/Moyasar stay loud 501s until credentialed).
`POST /api/v1/subscriptions/webhook` verifies the signature, stores the event,
and processes it idempotently. The stub backend settles through the same
webhook code path via a clearly-labeled dev endpoint that only exists while
`PAYMENT_BACKEND=stub`. Simulated payments are visually marked in the UI.

### Seed (development fixtures only)

`starter` / `growth` / `scale` plans with placeholder prices, explicitly
labeled غير معتمدة / unapproved development fixtures; seeding stays behind
`SEED_ON_STARTUP` which production disables.

## 3. Frontend

- `/inventory/restock` — tabs replenishment/listing, evidence badges,
  insufficient-data empty states, dismiss/act dialogs, refresh.
- `/org/subscription` — current plan, period, usage meters, plan comparison,
  upgrade/downgrade/cancel/reactivate, billing history, sandbox banner.
- `/admin/plans` — plan list, new version editor, availability toggles.
- `/reports` index (the sidebar already links there).
- New API modules in `lib/api.ts`; full ar/en message coverage; entitlement
  errors surface an upgrade call-to-action.
