# Pipeline generalization: deal value, invoicing, and stage templates

**Status: proposed, not yet built.** This is a design document, matching the
style of `PHASE_1_PLAN.md`–`PHASE_4B_CONVERSIONS_PLAN.md` — it describes
target schema/behavior for a future phase (`FEATURES_AND_PLAN.md` §2 Phase
6), not code that exists. Written against the actual current models
(`backend/app/models/deal.py`, `pipeline_stage.py`) — not a guess.

The CRM was built EdTech-first. This generalizes the pipeline engine so any
vertical (IT hardware, services, generic B2B sales) can configure its own
pipeline — with deal value, invoicing, and revenue KPIs as first-class —
while EdTech keeps working unchanged.

## 1. Current state (what actually exists today)

- `Deal` (`backend/app/models/deal.py`): `contact_id`, `course_id`
  (**not nullable** — hard EdTech coupling), `stage_id`, `owner_id`. **No
  `value` column.** `FEATURES_AND_PLAN.md` Phase 4 already flags this
  explicitly: forecasting is "a weighted headcount... `deals` has no
  value/price column yet, so this isn't a $ figure."
- `PipelineStage` (`pipeline_stage.py`): `name`, `sort_order`, `is_won`,
  `is_lost`, `win_probability_pct`. The `is_won`/`is_lost` pattern — fixed
  meaning on a boolean flag, independent of the tenant-editable `name` — is
  the existing convention this proposal extends, not replaces.
- `payments` is listed in `DATABASE_SCHEMA.md` as "Fee/EMI records" but is
  **not yet built** (`FEATURES_AND_PLAN.md` Phase 4 exit-criteria note:
  "fee-paid" events remain blocked on the still-unbuilt `payments`
  feature).
- No `accounts`, `invoices`, or `pipeline_stage_templates` table exists.

## 2. Proposed schema changes

### 2.1 `deals` — add value, generalize the account link

- Add `value NUMERIC(12,2) NOT NULL DEFAULT 0` and
  `currency TEXT NOT NULL DEFAULT 'INR'` (or tenant-configured default).
- Add `account_id` — nullable composite FK to a new `accounts` table
  (Section 2.2). Nullable because individual-contact verticals like EdTech
  don't need it; B2B verticals do.
- Relax `course_id` from `NOT NULL` to nullable — it's an EdTech-specific
  concept, not a general "what is this deal for" field. A generic `title`
  or `description` column may be worth adding alongside it, but that's a
  smaller, separable decision from this one.
- Migration must be additive (new nullable/defaulted columns) — existing
  EdTech deals get `value = 0` until backfilled, and continue to resolve
  `course_id` exactly as before; no behavior change for the shipped EdTech
  flow.

### 2.2 `accounts` — new table (B2B organization)

Standard tenant-scoped table (`DATABASE_SCHEMA.md` §2 pattern): `name`,
`owner_id`. A deal's `account_id` points here when the buyer is an
organization rather than an individual contact.

### 2.3 `pipeline_stages` — extend the existing flag pattern

Add `is_invoice_stage BOOLEAN NOT NULL DEFAULT false` and
`is_rework_stage BOOLEAN NOT NULL DEFAULT false`, following the exact
precedent `is_won`/`is_lost` already set: fixed meaning on a flag, separate
from the tenant-editable `name`. **Not** a new `stage_type` enum — that
would duplicate a pattern that already exists and works.

Behavior these flags drive:
- A deal entering an `is_invoice_stage = true` stage prompts invoice
  creation/send in the UI.
- A deal entering an `is_rework_stage = true` stage sets its linked
  invoice's `status` to `rework_requested` and reopens it for editing.

### 2.4 `invoices` — new table

Standard tenant-scoped pattern, composite FK to `deals` (same shape as
`workflow_runs.workflow_rule_id` or `conversion_events.deal_id` — see
`DATABASE_SCHEMA.md` for which existing pattern applies once this is
planned in detail): `invoice_number`, `amount`, `status` (`draft` / `sent`
/ `rework_requested` / `paid` / `cancelled`), `issued_at`, `due_date`.

### 2.5 `payments` — redefine, don't duplicate

`payments` already exists as a name in `DATABASE_SCHEMA.md` ("Fee/EMI
records") but is unbuilt. Redefine it here rather than adding a second
table: `invoice_id` (composite FK to `invoices`), `amount`, `paid_at`,
`method`. An invoice is `paid` once its payments sum to its `amount`.
EdTech's fee/EMI collection becomes a special case of this — multiple
`payments` rows against one `invoices` row — not a separate mechanism.

### 2.6 `pipeline_stage_templates` — new, global table

The one deliberately non-tenant-scoped, no-RLS table added by this
proposal — alongside the two existing documented exceptions
(`tenants` itself, and `lead_source_connections`'s RLS exemption for a
different reason — see `DATABASE_SCHEMA.md` §1). Columns: `name`,
`category` (e.g., "EdTech admissions", "B2B sales", "Generic"),
`default_sort_order`, `is_won`, `is_lost`, `is_invoice_stage`,
`is_rework_stage`, `default_win_probability_pct`.

**Selection model**: an Admin configuring their tenant's pipeline sees this
library in the pipeline config screen (`PipelineConfigPage.tsx` already
exists and would be extended, not replaced) and adds any subset to build
their tenant's `pipeline_stages`. Selecting a template **copies** it into a
tenant-owned row — not a live reference — so the tenant can freely rename,
reorder, remove, or add stages the library doesn't have. Admins can still
define fully custom stages; the library is a starting point, not a
constraint.

Suggested seed rows include the existing EdTech stages already in
production use (so nothing is lost) plus general ones:

| Template stage | Flags | Typical use |
|---|---|---|
| Inquiry / Lead | — | Universal starting point |
| Qualification | — | Confirm fit before investing effort |
| Demo Scheduled | — | EdTech, product-led sales (existing) |
| Proposal Sent | — | B2B, services |
| Invoice Sent | `is_invoice_stage` | Any vertical selling something priced |
| Invoice Rework | `is_rework_stage` | The case this request started from |
| Negotiation | — | B2B |
| Payment Received / Enrolled / Won | `is_won` | Terminal success |
| Lost / Dropped | `is_lost` | Terminal loss |

## 3. Example flow (IT hardware company)

1. Deal created at stage **Inquiry**, `value` estimated.
2. Deal reaches **Proposal Sent** — value refined.
3. Deal reaches **Invoice Sent** (`is_invoice_stage`) — staff creates an
   `invoice`, enters the amount, sends it.
4. Customer requests a change → staff moves the deal to **Invoice Rework**
   (`is_rework_stage`) — invoice `status` auto-flips to `rework_requested`.
5. Staff revises the amount, re-sends → `status` back to `sent`.
6. Payment recorded as a `payments` row; once the invoice is fully paid, the
   deal typically moves to a `is_won` stage.

## 4. Dashboard KPIs this unlocks

Extends the dashboards in `REQUIREMENTS.md` Section 5 (marked *proposed,
Phase 6* there) — money-based views on the same stage/escalation data, not
a separate dashboard:

- **Pipeline value by stage** — `SUM(deal.value)` grouped by stage
- **Weighted forecast ($)** — `value × win_probability_pct`, extending
  Phase 4's existing headcount-based forecast to a dollar figure — this is
  also the fix for the "cost-per-enrollment-in-dollars" open item noted in
  `FEATURES_AND_PLAN.md` Phase 4's exit criteria
- **Invoiced vs. paid vs. outstanding** — per period
- **Invoice rework rate** — % of invoices that passed through an
  `is_rework_stage` at least once
- **Average time in an `is_invoice_stage`** — feeds the existing SLA
  framework (`REQUIREMENTS.md` Section 3) if a tenant sets an SLA on it

## 5. What stays EdTech-specific vs. what generalizes

- **Generalizes**: `deals` (value, account link), `pipeline_stages`
  (new flags), `invoices`, `payments`, `pipeline_stage_templates`. The
  workflow engine, SLA/escalation framework, and RBAC already generalize —
  nothing about them is EdTech-specific, so they need no changes here.
- **Stays EdTech-specific, unaffected**: `courses` catalog,
  WhatsApp/telephony integrations, the existing admission-funnel template
  stages. These become one tenant's particular choice of stages/tables —
  not special-cased in the core engine.

## 6. Suggested sequencing

This is new scope, not a continuation of Phase 5 (hardening) —
`FEATURES_AND_PLAN.md` should record it as **Phase 6**. Per `CLAUDE.md`'s
working agreement, run this through `architect` first (it touches
production tables — `deals`, `pipeline_stages` — and adds one of the
documented RLS exceptions), then `feature-planner` for the detailed
task breakdown before `feature-builder` starts.
