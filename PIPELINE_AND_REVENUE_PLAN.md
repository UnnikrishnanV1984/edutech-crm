# Pipeline generalization — implementation plan

Detailed task breakdown for `PIPELINE_AND_REVENUE.md` (Phase 6,
`FEATURES_AND_PLAN.md` §2), which is architect-reviewed and approved
(2026-08-24) — this plan does not revisit any of that document's design
decisions, including its inline "Architect review" resolutions. It exists
to turn that design into reviewable-commit-sized implementation steps
following this skill's own 8-section process.

## 1. Located

Phase 6 in `FEATURES_AND_PLAN.md` §2, already recorded with its own exit
criteria and an explicit note that it's parallel-track with Phase 5, not
sequential after it.

## 2. Prerequisites check

None. Phase 6 is confirmed independent of Phase 5's exit criteria
(`PIPELINE_AND_REVENUE.md` §6's architect review) — no prerequisite-check
blocker applies here.

## 3. Affected layers

- **Database**: 3 new tables (`accounts`, `invoices` [partitioned],
  `payments` [partitioned]), 1 new global no-RLS table
  (`pipeline_stage_templates` + its seed data), 2 altered tables (`deals`,
  `pipeline_stages`).
- **Backend**: new schemas/services/routes for all four new tables; changes
  to `deal.py`/`deal_service.py`/`app/api/deals.py` (value/currency/
  account_id/nullable course_id, rework-stage auto-flip hook); changes to
  `pipeline_stage.py`/`pipeline_stage_service.py`/`app/api/pipeline_stages.py`
  (two new creation-only flags); `report_service.py` extended with $ figures.
- **BFF**: none — generic proxy, no route-specific changes needed (same
  conclusion as every other backend-only feature this session).
- **Frontend**: `PipelineConfigPage.tsx` extended (template picker),
  `PipelinePage.tsx` (deal value, nullable course_id), new invoice UI on
  the deal detail page, a minimal accounts picker, `AdminDashboard.tsx` /
  `ManagerDashboard.tsx` new $ KPI cards.
- **Background jobs**: none. Nothing here needs an async worker — invoice/
  payment state changes are synchronous request-response actions, not
  event-driven side effects requiring Celery (unlike the workflow engine's
  own actions, which are untouched by this plan).

## 4. Database changes

All new tables follow `DATABASE_SCHEMA.md` §2's standard pattern unless
noted. Migration numbers assume this is the next work after alembic head
0019 (confirmed current head at architect-review time) — renumber if other
migrations land first.

### 4.1 `accounts` (new, migration 0020)

```sql
CREATE TABLE accounts (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    name        TEXT NOT NULL,
    owner_id    UUID NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
);
CREATE INDEX idx_accounts_tenant_owner ON accounts (tenant_id, owner_id, created_at DESC);
-- + ENABLE/FORCE ROW LEVEL SECURITY + tenant_isolation_accounts policy,
--   standard shape.
```

### 4.2 `deals` — alter (migration 0021)

```sql
ALTER TABLE deals ADD COLUMN value NUMERIC(12,2) NOT NULL DEFAULT 0;
ALTER TABLE deals ADD COLUMN currency TEXT NOT NULL DEFAULT 'INR';
ALTER TABLE deals ADD COLUMN account_id UUID NULL;
ALTER TABLE deals ADD CONSTRAINT deals_account_id_tenant_id_fkey
    FOREIGN KEY (account_id, tenant_id) REFERENCES accounts (id, tenant_id);
CREATE INDEX idx_deals_tenant_account ON deals (tenant_id, account_id);
ALTER TABLE deals ALTER COLUMN course_id DROP NOT NULL;
```

Purely additive/relaxing — no backfill, no data loss, confirmed against
the live 0005 schema during architect review.

### 4.3 `pipeline_stages` — alter (migration 0022)

```sql
ALTER TABLE pipeline_stages ADD COLUMN is_invoice_stage BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE pipeline_stages ADD COLUMN is_rework_stage BOOLEAN NOT NULL DEFAULT false;
```

No new index — same reasoning `DATABASE_SCHEMA.md` §5 already gives for
`is_won`/`is_lost`: low-cardinality flags with no filtered-list query
pattern of their own yet.

### 4.4 `invoices` (new, migration 0023) — hash-partitioned

Follows the `0006_activities.py`/`0019_documents_partition.py` pattern
(partitioned from creation, no create-copy-swap needed since this is a
brand-new table):

```sql
CREATE TABLE invoices (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES tenants(id),
    deal_id        UUID NOT NULL,
    invoice_number TEXT NOT NULL,
    amount         NUMERIC(12,2) NOT NULL,
    status         TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','sent','rework_requested','paid','cancelled')),
    issued_at      TIMESTAMPTZ NULL,
    due_date       DATE NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id)
) PARTITION BY HASH (tenant_id);
-- 16 partitions, same DO $$ loop as 0006/0012/0014/0019.
CREATE UNIQUE INDEX uq_invoices_tenant_number ON invoices (tenant_id, invoice_number);
CREATE INDEX idx_invoices_tenant_deal ON invoices (tenant_id, deal_id, created_at DESC);
-- + RLS, standard shape.
```

### 4.5 `payments` (new, migration 0024) — hash-partitioned, plain-UUID FK

```sql
CREATE TABLE payments (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    invoice_id  UUID NOT NULL,  -- plain UUID, not a composite FK — invoices
                                -- is hash-partitioned (escalations-style
                                -- exception, per architect review)
    amount      NUMERIC(12,2) NOT NULL,
    paid_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    method      TEXT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
) PARTITION BY HASH (tenant_id);
-- 16 partitions.
CREATE INDEX idx_payments_tenant_invoice ON payments (tenant_id, invoice_id, paid_at DESC);
-- + RLS, standard shape.
```

No FK constraint on `invoice_id` at all (plain UUID with no reference, same
as `escalations.sla_state_id`/`workflow_run_id`) — application code is the
only guarantee that `invoice_id` resolves to a real row, exactly matching
the existing precedent this pattern is copied from.

### 4.6 `pipeline_stage_templates` (new, migration 0025) — global, no RLS

```sql
CREATE TABLE pipeline_stage_templates (
    id                          UUID NOT NULL DEFAULT gen_random_uuid(),
    name                        TEXT NOT NULL,
    category                    TEXT NOT NULL,
    default_sort_order          INTEGER NOT NULL,
    is_won                      BOOLEAN NOT NULL DEFAULT false,
    is_lost                     BOOLEAN NOT NULL DEFAULT false,
    is_invoice_stage            BOOLEAN NOT NULL DEFAULT false,
    is_rework_stage             BOOLEAN NOT NULL DEFAULT false,
    default_win_probability_pct INTEGER NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- No tenant_id column, no RLS — the tenants-style global exception
-- (architect review, PIPELINE_AND_REVENUE.md §2.6). No FORCE ROW LEVEL
-- SECURITY, no policy — deliberately absent, not an oversight.
```

Same migration seeds the rows from `PIPELINE_AND_REVENUE.md` §2.6's table
(Inquiry/Lead, Qualification, Demo Scheduled, Proposal Sent, Invoice Sent,
Invoice Rework, Negotiation, Payment Received/Enrolled/Won, Lost/Dropped)
via `op.execute(INSERT ...)` — a data migration, not application-seeded,
since this is platform content, not dev-only fixture data (contrast with
`backend/app/db/seed.py`, which is dev-only and never runs in production).

## 5. API contract

All new/changed routes follow `API_CONVENTIONS.md`'s existing envelope/
error/pagination shapes.

### 5.1 `POST/GET /api/v1/accounts`

Minimal CRUD, same shape as `courses` (`app/api/courses.py`): `POST`
(any authenticated role, `owner_id` defaults to acting user) and `GET`
(list, tenant-scoped). No `PATCH`/`DELETE` in this pass — not asked for
by the design doc, and deals reference accounts by id so deleting one
needs a decision (block if in use? nullify referencing deals?) this plan
isn't making. Add `PATCH`/`DELETE` as a follow-up if a real need shows up.

```
POST /api/v1/accounts        { name, owner_id? } -> AccountOut
GET  /api/v1/accounts        -> AccountOut[]
```

### 5.2 `PATCH /api/v1/deals/{id}`, `POST /api/v1/contacts/{id}/deals` — extended

`DealCreate`/`DealUpdate`/`DealOut` gain `value`, `currency`,
`account_id`; `course_id` becomes optional on all three. No new routes —
existing deal endpoints just accept/return the new fields.

**New behavior in `PATCH /api/v1/deals/{id}`** (`app/api/deals.py`,
alongside the existing stage-change side effects — activity log,
workflow-rule trigger, conversion send): when a stage change lands on a
stage with `is_rework_stage = true`, find the deal's most recent
non-cancelled invoice (if any) and set its `status` to
`rework_requested`. No-op if the deal has no invoice yet — the rework flag
firing before an invoice exists isn't an error, just nothing to flip.
`is_invoice_stage` entry has **no backend behavior** — the design doc
frames it as a UI prompt ("prompts invoice creation/send in the UI"), not
a server-side action; the frontend shows a "Create invoice" CTA when a
deal is in an `is_invoice_stage` stage with no open invoice.

### 5.3 `pipeline_stages` — extended, not new routes

`PipelineStageCreate` gains `is_invoice_stage: bool = False`,
`is_rework_stage: bool = False` — settable only at creation, same
creation-only rule already applied to `is_won`/`is_lost` (excluded from
`PipelineStageUpdate`, per the existing code comment: later logic reads
these as a stable signal). `PipelineStageOut` gains both fields as
read-only output.

### 5.4 `invoices`

```
POST   /api/v1/deals/{deal_id}/invoices   { invoice_number, amount, due_date? } -> InvoiceOut (status=draft)
GET    /api/v1/deals/{deal_id}/invoices   -> InvoiceOut[]
GET    /api/v1/invoices/{id}              -> InvoiceOut
PATCH  /api/v1/invoices/{id}              { amount?, due_date?, status? } -> InvoiceOut
```

`PATCH`'s `status` only accepts client-triggerable forward transitions —
`draft -> sent`, `rework_requested -> sent` (after revision), or `-> cancelled`
from any non-terminal state — mirroring `escalation_service`'s
`_ALLOWED_TRANSITIONS` table pattern. `rework_requested` and `paid` are
**not** acceptable client-supplied values: `rework_requested` is only ever
set by the stage-entry hook (§5.2), and `paid` is only ever set by the
payments service (§5.5) when a sum check passes — same "system states
aren't client-settable" precedent `escalation_service.py` already
establishes for its own status field.

### 5.5 `payments`

```
POST /api/v1/invoices/{id}/payments   { amount, method?, paid_at? } -> PaymentOut
GET  /api/v1/invoices/{id}/payments   -> PaymentOut[]
```

Creating a payment recomputes the parent invoice's paid total; if
`SUM(payments.amount) >= invoices.amount`, the service flips the invoice's
`status` to `paid` in the same transaction. This is the only path that can
ever set `status = 'paid'` — not accepted via `PATCH /api/v1/invoices/{id}`
(§5.4).

### 5.6 `pipeline_stage_templates` — read-only, hard requirement

```
GET /api/v1/pipeline-stage-templates -> PipelineStageTemplateOut[]
```

**This is the only route this table ever gets.** No `POST`/`PATCH`/`DELETE`
under any tenant-facing path, ever — per the architect review, that's the
entire justification for skipping RLS on this table, not just a documented
intent. Gate the `GET` with `require_admin` (same dependency
`app/api/pipeline_stages.py`'s mutating routes already use) since the only
consumer is the admin pipeline-config screen — no other role has a reason
to see it. Selecting a template is **not** a separate "apply" endpoint: the
frontend calls the existing `POST /api/v1/pipeline-stages` with the
template's field values pre-filled into the create form, so the write
lands on the tenant's own RLS-protected `pipeline_stages` row through the
exact same path a fully custom stage already uses — no new write surface
at all.

### 5.7 `reports` — extended, not new endpoints (except one)

- `GET /api/v1/reports/funnel`: each row gains a `value` field (`SUM(deal.value)`
  for that stage) alongside the existing `count` — additive, non-breaking.
- `GET /api/v1/reports/forecast`: response gains `expected_value` (`Σ
  value × win_probability_pct / 100`) alongside the existing
  `expected_enrollments` — this is Phase 4's headcount forecast gaining a
  dollar figure, not a separate forecast. Also resolves the
  "cost-per-enrollment-in-dollars" open item from Phase 4's exit criteria.
- **New**: `GET /api/v1/reports/invoices` (manager/admin-gated, same as
  `sla-compliance`) — one aggregate: invoiced total, paid total,
  outstanding total (all for a configurable period, default current
  month), invoice rework rate (% of invoices that ever passed through
  `rework_requested`), and average time spent in an `is_invoice_stage`
  stage (feeds the existing SLA framework if a tenant later sets a policy
  on it — no SLA-framework changes needed here, it already generalizes).

## 6. Multi-tenancy check

- `accounts`, `invoices`, `payments`: standard `tenant_id NOT NULL` +
  `ENABLE`/`FORCE ROW LEVEL SECURITY` + tenant-scoped policy, composite
  index leading with `tenant_id`, composite `(id, tenant_id)` primary key
  — all per `DATABASE_SCHEMA.md` §2, no deviation.
- `invoices`/`payments` additionally hash-partitioned by `tenant_id` per
  §3 of the same doc — RLS and indexing on the parent table apply
  uniformly to every partition, same as `activities`/`sla_states`/
  `workflow_runs`/`documents`.
- `pipeline_stage_templates`: confirmed the no-RLS status is matched by an
  **actual absence of any tenant-facing mutating route** in §5.6 above —
  not just documented as an intent. The one `GET` route returns identical
  data to every tenant; there is nothing tenant-specific to leak or
  cross-contaminate.
- `deals.account_id`: nullable composite FK, same tenant-scoping shape as
  every other optional deal reference (`deal_id` on tasks/documents) —
  can't point at another tenant's account, enforced by the composite FK
  itself (`(account_id, tenant_id) REFERENCES accounts (id, tenant_id)`).
- `payments.invoice_id` has no FK at all (§4.5) — the service layer must
  explicitly verify the invoice belongs to `context.tenant.id` before
  accepting a payment against it (the `GET /api/v1/invoices/{id}` 404-if-
  not-found-in-this-tenant check already does this same verification
  pattern elsewhere in this codebase; reuse it, don't rely on the FK to
  catch a cross-tenant `invoice_id`).
- Rework-stage auto-flip (§5.2) and the paid-threshold check (§5.5) both
  run inside the same request-scoped, tenant-context-set transaction as
  the triggering action — no background job, no cross-tenant risk.

## 7. Task breakdown

Each numbered item is one reviewable commit, in dependency order.

1. **`accounts` migration + schema/service/api** (§4.1, §5.1) — no
   dependents yet, safe to land alone.
2. **`deals` migration** (§4.2) — DB only, no application code in this
   commit (matches this session's own established pattern of isolating a
   schema change from its consumers when the two are separable).
3. **`deals` schema/service/frontend update** — `DealCreate`/`DealUpdate`/
   `DealOut` gain `value`/`currency`/`account_id`/optional `course_id`;
   `report_service`'s course-grouped views and `PipelinePage.tsx`'s
   `courseName()` handle a null `course_id` gracefully (architect review
   — called out explicitly so it isn't folded silently into commit 2).
4. **`pipeline_stages` migration + schema/service/api** (§4.3, §5.3) —
   `is_invoice_stage`/`is_rework_stage`, creation-only, same shape as
   `is_won`/`is_lost`.
5. **`invoices` migration (partitioned) + schema/service/api** (§4.4,
   §5.4) — status state machine with the client-settable-vs-system-only
   split from §5.4.
6. **Rework-stage auto-flip hook** in `PATCH /api/v1/deals/{id}` (§5.2) —
   depends on 4 and 5 both existing; its own commit since it's a genuine
   cross-cutting behavior, not part of either table's CRUD.
7. **`payments` migration (partitioned) + schema/service/api** (§4.5,
   §5.5) — the paid-threshold check depends on `invoices` (5) existing.
8. **`pipeline_stage_templates` migration + seed data + read-only api**
   (§4.6, §5.6) — independent of 1-7, could land any time after 4 (needs
   `is_invoice_stage`/`is_rework_stage` to exist as columns on the
   template rows).
9. **`report_service` $ extensions** (§5.7) — depends on 3 (deal.value)
   and 5/7 (invoices/payments) existing.
10. **Frontend: `PipelineConfigPage.tsx` template picker** (§2.6's
    "Selection model") — depends on 8. Flag to `ui-designer`/`ux-designer`
    first per this repo's own skill-routing convention (`CLAUDE.md`
    routes "purely visual/UX" work there) — this plan states the
    functional requirement (list templates, prefill the existing create
    form, submit through the existing endpoint), not a pixel-level layout.
11. **Frontend: deal value + invoice UI** — `PipelinePage.tsx`/deal detail
    page show `value`/`currency`, an "Create invoice" CTA on
    `is_invoice_stage` entry, invoice detail/status/payments UI. Depends
    on 3, 5, 7. Same `ui-designer`/`ux-designer` routing note as 10 — this
    is the largest single piece of new UI in the whole plan and deserves
    real flow design, not an inline sketch here.
12. **Frontend: `AdminDashboard.tsx`/`ManagerDashboard.tsx` $ KPI cards**
    — depends on 9. Update the existing "Weighted headcount, not revenue"
    forecast caption once `expected_value` exists; add pipeline-value,
    invoiced/paid/outstanding, and rework-rate cards.

## 8. Acceptance criteria

- An EdTech tenant that never touches any Phase 6 feature sees zero
  behavior change: existing deals keep resolving `course_id` exactly as
  before, `value` defaults to `0` and is invisible unless surfaced in UI
  a tenant chooses to use.
- Creating a deal with no `course_id` succeeds (B2B/generic vertical) and
  does not error in `report_service`'s funnel/forecast, which return `0`/
  omit that deal from course-grouped views rather than raising.
- A deal in tenant A cannot reference an `account_id` belonging to tenant
  B — rejected the same way a cross-tenant `owner_id`/`contact_id` already
  is (FK violation surfaced as 400, per `app/api/deals.py`'s existing
  `IntegrityError` handling).
- Moving a deal into an `is_rework_stage` stage flips its most recent
  non-cancelled invoice's `status` to `rework_requested`; a deal with no
  invoice yet moves into that stage without error.
- `payments` rows summing to >= an invoice's `amount` flip that invoice's
  `status` to `paid` automatically; `PATCH /api/v1/invoices/{id}` with
  `status: "paid"` in the request body is rejected (`VALIDATION_ERROR`) —
  proving it's system-only, not client-settable.
- `GET /api/v1/pipeline-stage-templates` returns identical data
  regardless of which tenant's token calls it — proving there is no
  tenant-specific content to leak. No route under
  `/api/v1/pipeline-stage-templates` accepts `POST`/`PATCH`/`DELETE`
  (`405 Method Not Allowed` or route-not-found, not just "no UI button
  for it").
- A `payments` row can only be created against an `invoice_id` belonging
  to the caller's own tenant — a cross-tenant `invoice_id` in the request
  body returns `404`, proving the service-layer check (not the absent FK)
  is what enforces this.
- `invoices`/`payments` are confirmed hash-partitioned (`\d+ invoices`/
  `\d+ payments` show `Partitioned table` / `PARTITION BY HASH`) before
  this plan is considered done — not deferred to a future retrofit.
- Selecting a template in the pipeline-config UI produces a new row in
  the tenant's own `pipeline_stages` (RLS-protected, independently
  editable afterward) — not a live reference to the template, proven by
  renaming the tenant's copy and confirming the template library row is
  unchanged.
