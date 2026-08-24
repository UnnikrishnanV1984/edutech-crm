# Pipeline generalization: deal value, invoicing, and stage templates

**Status: proposed, architect-reviewed, not yet built.** This is a design
document, matching the style of `PHASE_1_PLAN.md`–`PHASE_4B_CONVERSIONS_PLAN.md`
— it describes target schema/behavior for a future phase
(`FEATURES_AND_PLAN.md` §2 Phase 6), not code that exists. Written against
the actual current models (`backend/app/models/deal.py`,
`pipeline_stage.py`) — not a guess. Architect review (2026-08-24) resolved
the open questions inline, marked **Architect review** — migration safety
confirmed, `pipeline_stage_templates`'s RLS exception confirmed as the
`tenants`-style case, the `invoices`/`payments` composite-FK question
resolved (and both tables newly recommended for hash-partitioning from
creation), Phase 6/Phase 5 sequencing confirmed independent, and the
flag-vs-enum choice upheld. Ready to hand to `feature-planner`.

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
- **Architect review note**: confirmed additive at the DB layer against
  the live schema (alembic head 0019 as of this review; `deals` — 0005 —
  has no later migration touching it, `course_id` is a plain `NOT NULL`
  column with no CHECK/trigger depending on it). Relaxing it to nullable
  is a safe `ALTER COLUMN ... DROP NOT NULL` with no backfill required.
  That said, it is **not** purely a DB-layer change: `DealCreate.course_id`
  and `DealOut.course_id` (`backend/app/schemas/deal.py`) are both
  currently non-optional `uuid.UUID`, and `report_service`'s
  course-grouped views and `PipelinePage.tsx`'s `courseName()` lookup both
  assume a resolvable id. None of these crash on `None` (the frontend
  lookup degrades to a blank label), but the schema/service/frontend
  changes are real follow-on work in the same slice, not a side effect of
  the migration alone — size the task breakdown accordingly.

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

**Architect review — flags confirmed over an enum, at this scale.** Four
flags split cleanly into two independent concern-pairs — terminal status
(`is_won`/`is_lost`) and mid-pipeline financial triggers
(`is_invoice_stage`/`is_rework_stage`) — not one mutually-exclusive
category, which is what a single `stage_type` enum would actually model
well. A stage can be an invoice-stage on its way toward a *later*,
separate won stage (the proposal's own example flow treats them as
distinct stages), so collapsing all four into one enum column would either
force awkward combined values (`invoice_won`, `invoice_lost`, ...) or
still need two enums side by side — no simpler than four named booleans,
and less readable at the query site (`stage.is_won` vs.
`stage.terminal_status == 'won'`). Not strained yet. Revisit this once a
*third* independent concern-pair gets proposed (a different vertical
wanting its own stage-trigger flag) — boolean columns stop scaling well
past a small, stable set, and a `stage_triggers` tag table becomes the
better shape at that point, not before.

### 2.4 `invoices` — new table

Composite FK to `deals`: `(deal_id, tenant_id) REFERENCES deals (id,
tenant_id)`. This is the `workflow_runs.workflow_rule_id`-style pattern
(target table not partitioned → no obstacle), not the `escalations`-style
plain-UUID exception — `deals` has never been hash-partitioned (alembic
0005) and this proposal doesn't change that.

**Architect review — partition `invoices` from creation.** Not part of
the original sketch, added on review: `invoices` is a per-stage-transition
transactional table, the same shape as `activities`/`workflow_runs` (an
event/artifact per occurrence, not a stable per-entity row like `deals`
itself) — exactly `DATABASE_SCHEMA.md` §3's criterion for hash-partitioning
from the start. `documents` was left plain at creation despite fitting
that same criterion and needed an expensive create-copy-swap migration
later to fix (`GAP_FIXES_PLAN.md` item 7) — `invoices` should be
partitioned by `tenant_id` in its creating migration instead of repeating
that mistake. Columns unchanged: `invoice_number`, `amount`, `status`
(`draft` / `sent` / `rework_requested` / `paid` / `cancelled`), `issued_at`,
`due_date`.

### 2.5 `payments` — redefine, don't duplicate

`payments` already exists as a name in `DATABASE_SCHEMA.md` ("Fee/EMI
records") but is unbuilt. Redefine it here rather than adding a second
table: `invoice_id`, `amount`, `paid_at`, `method`. An invoice is `paid`
once its payments sum to its `amount`. EdTech's fee/EMI collection becomes
a special case of this — multiple `payments` rows against one `invoices`
row, likely the highest-volume table this proposal adds — not a separate
mechanism.

**Architect review — `invoice_id` is a plain UUID, not a composite FK.**
This resolves the "still open" question the original draft flagged.
Because `invoices` is now recommended hash-partitioned (§2.4 above),
referencing it from `payments` hits the same obstacle
`DATABASE_SCHEMA.md` already documents for
`escalations.sla_state_id`/`workflow_run_id`: a composite FK into a
hash-partitioned table's non-partition-key id isn't something this
codebase's existing pattern supports cleanly. `payments` should also be
hash-partitioned by `tenant_id` from creation, for the same reason as
`invoices` above — it's the more write-heavy table of the two (EMI/
installment schedules mean several `payments` rows per `invoices` row).

### 2.6 `pipeline_stage_templates` — new, global table

The one deliberately non-tenant-scoped, no-RLS table added by this
proposal — alongside the two existing documented exceptions
(`tenants` itself, and `lead_source_connections`'s RLS exemption for a
different reason — see `DATABASE_SCHEMA.md` §1). Columns: `name`,
`category` (e.g., "EdTech admissions", "B2B sales", "Generic"),
`default_sort_order`, `is_won`, `is_lost`, `is_invoice_stage`,
`is_rework_stage`, `default_win_probability_pct`.

**Architect review — this is the `tenants` exception, not the
`lead_source_connections` one, and that's the right fit, not just a
convenient one.** `lead_source_connections`'s exemption exists because a
webhook must query it to *discover* `tenant_id` before `app.tenant_id`
can be set — a bootstrapping-order problem, and that table still has a
real `tenant_id` column RLS just can't gate on. `pipeline_stage_templates`
has no such problem and no `tenant_id` column at all: it's genuinely
global content, seeded once for every tenant to read from, the same shape
as `tenants` itself rather than a workaround. The safety of skipping RLS
here rests entirely on one fact that should be stated as a hard
requirement, not left implicit: **no tenant-facing write path may ever
exist for this table.** Selecting a template copies its values into a
tenant's own `pipeline_stages` row (RLS-protected); nothing lets a tenant
admin write back into the shared library — the API surface for this table
should be read-only (list/get), full stop, with any future write path
(adding new templates) restricted to platform-operator tooling outside
the tenant-facing API entirely.

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

**Architect review — Phase 6 does not need to wait for Phase 5 to close,
and should proceed in parallel.** `FEATURES_AND_PLAN.md` §3's "work phase
by phase" line is a *suggested working agreement*, not one of `CLAUDE.md`'s
eight non-negotiable rules — and this codebase already has precedent for
sequencing by actual dependency rather than strict number order: Phase 2-4
lead-capture/automation/reporting work shipped well ahead of Phase 5's
infra hardening starting at all. The reason to gate Phase N+1 is when it
would build feature work on top of an unfinished or untested Phase N
*foundation* — that's not the relationship here. Phase 5's remaining scope
(per-tenant rate limiting, load testing, the first real EKS deployment,
single-tenant path validation, and hash-partitioning of the *existing*
high-volume tables) touches deployment/ops and a disjoint set of tables
from Phase 6's (`deals`, `pipeline_stages`, and three new tables). Neither
phase's migrations, endpoints, or infra changes collide with the other's.
The one soft dependency worth naming: validating a real EKS deployment
sooner rather than much later is still worth doing before the app's
schema surface grows a lot more, simply so the deployment pipeline gets
proven against a realistic footprint — a scheduling preference, not a
blocker on starting Phase 6's design or build work.
`FEATURES_AND_PLAN.md` §2 should record Phase 6 as explicitly
parallel-track with Phase 5 rather than sequential after it, so this
doesn't read as silently skipping the working agreement.
