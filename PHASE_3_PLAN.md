# Phase 3 plan — RBAC enforcement, SLA/escalation engine, workflow automation

Per `FEATURES_AND_PLAN.md`, Phase 3 covers communication & automation.
Phase 2's exit criteria are met (lead capture integrations shipped and
verified — see `PHASE_2_PLAN.md`). This plan covers everything in
Phase 3 that does **not** depend on a new external provider:

- RBAC row-level scoping (Admin/Manager/Staff) — `REQUIREMENTS.md` §1
- SLA policy engine + escalation lifecycle — `REQUIREMENTS.md` §3-4
- Workflow rule engine (trigger/condition/action, Celery-backed) — `REQUIREMENTS.md` §2
- Auto-assignment — realized as the workflow engine's first rule type, not a
  separate subsystem (see §7)

**Explicitly out of scope, by user decision this session**: WhatsApp
outbound (templates/reminders/2-way chat) and email integration. Both are
new external provider integrations — per `CLAUDE.md`'s "what to ask about"
list and `DEVELOPMENT_PLAN.md` §9 ("WhatsApp/email providers → architect
first"), they need an `architect` pass (provider choice, credentials,
mock-backed build approach — the same shape Phase 2's Meta/Google/WhatsApp
went through) before they can be feature-planned. The workflow engine's
`send_message` action type is included in this plan's schema so a later
migration isn't needed, but its execution is a recorded no-op until that
architect work lands (see §7.4).

Also explicitly out of scope: `audit_log` (listed under Platform features in
`FEATURES_AND_PLAN.md` with no assigned phase — flagged as a gap in
`DEVELOPMENT_PLAN.md` §8 already, not resolved here either; worth a human
decision on which phase owns it).

## 1. Prerequisites check

Phase 2 exit criteria met (verified this session — 4 lead-capture pipelines
working end-to-end against the mock, tenant isolation proven). No blockers
to starting Phase 3's unblocked work.

**Celery is already decided, not a new architecture question.**
`DEVELOPMENT_PLAN.md` §8 resolved "Celery, not BullMQ" back in Phase 0 and
reserved `/backend/app/workers` for it (currently empty — Phase 0 didn't
actually scaffold the package despite its own exit-criteria table claiming
to). §9 explicitly names Phase 3 as "first real Celery work." This plan
treats the broker/backend choice (Redis, already required infra) and the
worker location as settled, not something to re-litigate or send back to
`architect`.

## 2. Affected layers

| Layer | Touched? | What changes |
|---|---|---|
| Frontend | Yes, substantial | Manager/Admin escalations queue, follow-up flags list, SLA policy config screen (admin), workflow rule builder (admin/manager-propose), row-scoped contact/deal/task views already existing screens just start returning fewer rows for Staff |
| BFF | No changes | Same generic `/api/v1` proxy as every resource so far — no new BFF code needed |
| Backend | Yes, substantial | Row-scoping dependency, 7 new tables, workflow rule CRUD + evaluation, SLA policy CRUD + state computation, escalation lifecycle, follow-up flags, `users.manager_id` |
| Database | Yes | 7 new tables (2 hash-partitioned), 1 new column (`users.manager_id`) |
| Background jobs | Yes — first real use | New `worker` and `beat` Compose services (same `backend` image, different `CMD`) — event-triggered rule evaluation (queued), periodic SLA-state computation + time-based rule scanning (scheduled) |

## 3. Database changes

All tables follow `DATABASE_SCHEMA.md` §2's standard pattern exactly (copy,
do not deviate) — including `tenant_sla_settings` below, even though it's
conceptually one row per tenant, per that doc's explicit instruction.

### 3.1 `users.manager_id` (RBAC — team mapping)

```sql
ALTER TABLE users ADD COLUMN manager_id UUID NULL;
ALTER TABLE users ADD CONSTRAINT users_manager_id_fkey
    FOREIGN KEY (manager_id, tenant_id) REFERENCES users (id, tenant_id);
CREATE INDEX idx_users_tenant_manager ON users (tenant_id, manager_id);
```

Nullable — a Staff user with no `manager_id` set has no manager (an admin
must assign one; see §5.1's new endpoint). Self-referencing composite FK,
same shape as every other `(x_id, tenant_id) REFERENCES table (id,
tenant_id)` pattern already in this schema.

### 3.2 `tenant_sla_settings` — business hours + holidays

```sql
CREATE TABLE tenant_sla_settings (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    timezone      TEXT NOT NULL DEFAULT 'UTC',
    business_hours JSONB NOT NULL DEFAULT
        '{"mon":[["09:00","18:00"]],"tue":[["09:00","18:00"]],"wed":[["09:00","18:00"]],
          "thu":[["09:00","18:00"]],"fri":[["09:00","18:00"]],"sat":[],"sun":[]}',
    holidays      JSONB NOT NULL DEFAULT '[]',  -- ["2026-01-26", ...]
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
);
CREATE UNIQUE INDEX uq_tenant_sla_settings_tenant ON tenant_sla_settings (tenant_id);
-- RLS + policy, standard pattern.
```

One row per tenant (enforced by the unique index, not the PK — the PK stays
`(id, tenant_id)` per the standard pattern). A tenant with no row yet uses
hardcoded UTC 9-6 Mon-Fri defaults (service-layer fallback, not a DB
default row) — avoids a seed-data dependency for every existing tenant.

### 3.3 `sla_policies`

```sql
CREATE TABLE sla_policies (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    applies_to      TEXT NOT NULL CHECK (applies_to IN ('stage_entry', 'task_due')),
    stage_id        UUID NULL,   -- required when applies_to = 'stage_entry'
    task_type       TEXT NULL,   -- free-text label when applies_to = 'task_due'; NULL = any task
    target_minutes  INT NOT NULL CHECK (target_minutes > 0),
    warning_threshold_pct INT NOT NULL DEFAULT 80 CHECK (warning_threshold_pct BETWEEN 1 AND 99),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (stage_id, tenant_id) REFERENCES pipeline_stages (id, tenant_id),
    CONSTRAINT ck_sla_policies_applies_to_fields CHECK (
        (applies_to = 'stage_entry' AND stage_id IS NOT NULL) OR
        (applies_to = 'task_due' AND stage_id IS NULL)
    )
);
CREATE INDEX idx_sla_policies_tenant_applies_to ON sla_policies (tenant_id, applies_to);
```

`applies_to = 'stage_entry'` covers "first contact within 30 min of
inquiry" / "demo scheduling within 24h of first contact" style rules — the
clock starts when a deal enters `stage_id`. `applies_to = 'task_due'`
covers "any assigned task, by its due date" — the clock is the task's own
`due_at`, this policy just supplies the warning threshold.

### 3.4 `sla_states` — hash-partitioned (high write volume, `DATABASE_SCHEMA.md` §3)

```sql
CREATE TABLE sla_states (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    sla_policy_id UUID NOT NULL,
    deal_id       UUID NULL,
    task_id       UUID NULL,
    target_at     TIMESTAMPTZ NOT NULL,
    warning_at    TIMESTAMPTZ NOT NULL,
    state         TEXT NOT NULL DEFAULT 'on_track'
                  CHECK (state IN ('on_track', 'at_risk', 'breached')),
    breached_at   TIMESTAMPTZ NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (sla_policy_id, tenant_id) REFERENCES sla_policies (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
    FOREIGN KEY (task_id, tenant_id) REFERENCES tasks (id, tenant_id),
    CONSTRAINT ck_sla_states_exactly_one_target CHECK (
        (deal_id IS NOT NULL)::int + (task_id IS NOT NULL)::int = 1
    )
) PARTITION BY HASH (tenant_id);
-- 16 partitions, DATABASE_SCHEMA.md §3's DO-block loop.
CREATE UNIQUE INDEX uq_sla_states_policy_target
    ON sla_states (tenant_id, sla_policy_id, deal_id, task_id);
CREATE INDEX idx_sla_states_tenant_state ON sla_states (tenant_id, state, target_at);
```

The unique index is how the periodic Celery Beat computation stays
idempotent — `INSERT ... ON CONFLICT (tenant_id, sla_policy_id, deal_id,
task_id) DO UPDATE SET state = ..., computed_at = ...` recomputes in place
rather than accumulating rows per tick.

### 3.5 `escalations`

```sql
CREATE TABLE escalations (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    source            TEXT NOT NULL
                      CHECK (source IN ('sla_breach', 'workflow_failure', 'rule_triggered', 'manual')),
    deal_id           UUID NULL,
    task_id           UUID NULL,
    sla_state_id      UUID NULL,       -- set when source = 'sla_breach'
    workflow_run_id   UUID NULL,       -- set when source = 'workflow_failure'
    raised_by         UUID NULL,       -- set when source = 'manual' (the counselor)
    assigned_to       UUID NOT NULL,   -- the manager (or admin, after the second-threshold step-up)
    status            TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'acknowledged', 'resolved', 'reassigned')),
    reason            TEXT NULL,       -- manual-raise reason
    resolution_note   TEXT NULL,
    opened_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at   TIMESTAMPTZ NULL,
    resolved_at       TIMESTAMPTZ NULL,
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
    FOREIGN KEY (task_id, tenant_id) REFERENCES tasks (id, tenant_id),
    FOREIGN KEY (raised_by, tenant_id) REFERENCES users (id, tenant_id),
    FOREIGN KEY (assigned_to, tenant_id) REFERENCES users (id, tenant_id),
    CONSTRAINT ck_escalations_source_fields CHECK (
        (source = 'sla_breach' AND sla_state_id IS NOT NULL) OR
        (source IN ('workflow_failure', 'rule_triggered') AND workflow_run_id IS NOT NULL) OR
        (source = 'manual' AND raised_by IS NOT NULL)
    )
);
CREATE INDEX idx_escalations_tenant_status ON escalations (tenant_id, status, opened_at DESC);
CREATE INDEX idx_escalations_tenant_assigned ON escalations (tenant_id, assigned_to, status);
```

`sla_state_id`/`workflow_run_id` are plain `UUID` columns, not composite
FKs into their (hash-partitioned) tables — Postgres doesn't support a
foreign key referencing a partitioned table's non-partition-key columns
cleanly here, and the tenant_id match is already guaranteed by both rows
sharing the same request/computation. Documented as a deliberate exception
to "every FK is composite," not an oversight. Manager→Admin step-up
(REQUIREMENTS.md §4.2's second escalation-SLA threshold) is **not** built
in this plan — flagged in §9 as a follow-up once the base lifecycle is
proven, to avoid shipping an escalation-SLA-on-an-escalation-SLA layer
before the first one has real usage.

### 3.6 `follow_up_flags`

```sql
CREATE TABLE follow_up_flags (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    manager_id  UUID NOT NULL,
    deal_id     UUID NULL,
    contact_id  UUID NULL,
    note        TEXT NOT NULL,
    remind_on   DATE NOT NULL,
    resolved_at TIMESTAMPTZ NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (manager_id, tenant_id) REFERENCES users (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
    FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
    CONSTRAINT ck_follow_up_flags_target CHECK (
        (deal_id IS NOT NULL)::int + (contact_id IS NOT NULL)::int = 1
    )
);
CREATE INDEX idx_follow_up_flags_tenant_manager ON follow_up_flags (tenant_id, manager_id, remind_on);
```

### 3.7 `workflow_rules`

```sql
CREATE TABLE workflow_rules (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    name          TEXT NOT NULL,
    trigger_type  TEXT NOT NULL
                  CHECK (trigger_type IN ('stage_changed', 'lead_created', 'task_overdue', 'elapsed_time')),
    trigger_config JSONB NOT NULL DEFAULT '{}',
    conditions    JSONB NOT NULL DEFAULT '[]',
    actions       JSONB NOT NULL DEFAULT '[]',
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'pending_approval', 'active', 'disabled')),
    created_by    UUID NOT NULL,
    approved_by   UUID NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (created_by, tenant_id) REFERENCES users (id, tenant_id),
    FOREIGN KEY (approved_by, tenant_id) REFERENCES users (id, tenant_id)
);
CREATE INDEX idx_workflow_rules_tenant_status_trigger
    ON workflow_rules (tenant_id, status, trigger_type);
```

Shapes (validated in the Pydantic schema, not a DB CHECK — these are
genuinely variable-shaped JSON, matching how `activities.payload` is
already handled):

- `trigger_config` — e.g. `{}` for `lead_created`/`task_overdue`; `{"to_stage_id": "<uuid>"}` (or `{}` for any stage) for `stage_changed`; `{"since": "assigned_at" | "stage_entered_at", "minutes": 1440}` for `elapsed_time`.
- `conditions` — `[{"field": "lead_source" | "course_id" | "stage_id", "op": "eq" | "in", "value": ...}]`, **AND-only** in this phase (REQUIREMENTS.md §2.2's AND/OR combinator is a deliberate simplification here, not an oversight — OR support is a follow-up once AND-only rules are proven).
- `actions` — ordered list of `{"type": "assign_round_robin" | "create_task" | "change_stage" | "notify_manager" | "raise_escalation" | "send_message", "config": {...}}`. `send_message` config-validates but always executes as a recorded no-op until the comms architect work lands (§7.4).

### 3.8 `workflow_runs` — hash-partitioned (high write volume, `DATABASE_SCHEMA.md` §3)

```sql
CREATE TABLE workflow_runs (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    workflow_rule_id    UUID NOT NULL,
    trigger_source_type TEXT NOT NULL CHECK (trigger_source_type IN ('deal', 'task', 'contact')),
    trigger_source_id   UUID NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('success', 'failed', 'retrying', 'skipped_unavailable')),
    attempt             INT NOT NULL DEFAULT 1,
    error_message       TEXT NULL,
    executed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
) PARTITION BY HASH (tenant_id);
-- 16 partitions, DATABASE_SCHEMA.md §3's DO-block loop.
CREATE UNIQUE INDEX uq_workflow_runs_dedupe
    ON workflow_runs (tenant_id, workflow_rule_id, trigger_source_type, trigger_source_id)
    WHERE status = 'success';
CREATE INDEX idx_workflow_runs_tenant_rule ON workflow_runs (tenant_id, workflow_rule_id, executed_at DESC);
```

The partial unique index is the "already fired" dedupe an `elapsed_time`
rule's periodic scan relies on (`INSERT ... ON CONFLICT DO NOTHING`, same
idempotency shape Phase 2's Redis keys used, but DB-backed here since this
needs to survive a scan re-running, not just redelivery). `workflow_run_id`
in `escalations` (§3.5) is not a composite FK for the same partitioned-table
reason noted there.

## 4. RBAC row-level scoping — API contract

New dependency `app/deps/scope.py`:

```python
@dataclass
class RowScope:
    owner_ids: list[uuid.UUID] | None  # None = admin, unrestricted

async def get_row_scope(context: TenantContext = Depends(get_tenant_context)) -> RowScope:
    if context.user_role == "admin":
        return RowScope(owner_ids=None)
    if context.user_role == "manager":
        team_ids = await user_service.list_team_member_ids(context.db, context.tenant.id, context.user.id)
        return RowScope(owner_ids=[context.user.id, *team_ids])
    return RowScope(owner_ids=[context.user.id])  # counselor (REQUIREMENTS.md's "Staff")
```

Applied to the **existing** Phase 1 endpoints, not new ones:

- `contact_service.list_contacts`/`get_contact`, `deal_service.list_deals`/`get_deal`,
  `task_service.list_tasks`/`get_task` each gain a required `owner_ids: list[uuid.UUID] | None`
  parameter — `None` adds no filter (Admin); otherwise `.where(Model.owner_id.in_(owner_ids))`
  (or `assignee_id` for tasks).
- A single-row `get_*` outside scope returns the same "not found" a
  cross-tenant row already does — `404`, not `403`, so a Staff user can't
  probe whether a lead exists outside their scope.
- Reassignment guard on `PATCH /api/v1/contacts/{id}`, `PATCH /api/v1/deals/{id}`
  (`owner_id`) and `PATCH /api/v1/tasks/{id}` (`assignee_id`): Staff changing
  the owner/assignee field at all → `403`; Manager changing it to someone
  outside their team → `403`; Admin unrestricted. Matches the permission
  matrix's "Reassign leads: Admin yes, Manager (within team) yes, Staff no."

New endpoint, admin-only (`require_admin`, already exists from Phase 2):

```
PATCH /api/v1/users/{id}
```

Body `{"role"?: "admin"|"manager"|"counselor", "manager_id"?: uuid|null}`.
Setting `manager_id` requires the target `manager_id` to reference a user
with `role = 'manager'` in the same tenant (`400 VALIDATION_ERROR`
otherwise) — this is how the "manager-to-team mappings"
(`REQUIREMENTS.md` §5.3) actually get configured; there's no separate
mapping table, `users.manager_id` **is** the mapping.

**Naming decision, not re-opened**: `REQUIREMENTS.md` §1.1 calls this role
"Staff," but its own table maps it 1:1 to "Counselor / telecaller." The
underlying value stays `counselor` everywhere it already exists (DB CHECK
constraint, Keycloak realm roles, `X-User-Role`, `API_CONVENTIONS.md` §1) —
renaming it would be a purely cosmetic breaking change across three
services, Keycloak, and every existing test, for no functional gain.
"Staff" is documentation language for the same role, not a new value.

## 5. SLA + escalation — API contract

```
GET    /api/v1/sla-policies                 admin-only
POST   /api/v1/sla-policies                 admin-only
PATCH  /api/v1/sla-policies/{id}             admin-only

GET    /api/v1/escalations                  row-scoped (RowScope from §4:
                                             manager sees own team's, admin
                                             sees all, staff sees none —
                                             raising is POST below, not a
                                             list view)
POST   /api/v1/escalations                  manual raise, any authenticated
                                             role — body {deal_id?, task_id?, reason}
PATCH  /api/v1/escalations/{id}              manager (own team) or admin —
                                             body {status: "acknowledged"|"resolved"|"reassigned",
                                             resolution_note?, reassign_to?}

GET    /api/v1/follow-up-flags              manager sees own, admin sees all
POST   /api/v1/follow-up-flags              manager or admin
PATCH  /api/v1/follow-up-flags/{id}          resolve — body {resolved: true}
```

`PATCH /api/v1/escalations/{id}` enforces the lifecycle transitions
(`open → acknowledged → resolved|reassigned`, no skipping) at the service
layer, `400 VALIDATION_ERROR` on an invalid transition (e.g. `resolved`
directly from `open`).

## 6. SLA state computation — Celery Beat periodic task

`app/workers/sla.py`, task `compute_sla_states(tenant_id: uuid.UUID)` —
required `tenant_id` first parameter per `CLAUDE.md` rule 6, `DATABASE_SCHEMA.md`
§4's `SET LOCAL app.tenant_id` set at the top of the task's own
transaction (a Celery task has no request-scoped session, mirrors how
`app/connectors/ingestion_service.py` already manages its own
sessions/tenant-context outside an HTTP request).

Beat schedule: one dispatcher task every 5 minutes, `for tenant in
active_tenants: compute_sla_states.delay(tenant.id)` — fan-out per tenant
so one tenant's slow computation can't delay another's (same principle as
`DATABASE_SCHEMA.md`'s per-tenant isolation, applied to job scheduling).

Per tenant, per active `sla_policies` row:
- `applies_to = 'stage_entry'`: find deals currently in `stage_id` with no
  `sla_states` row yet for `(policy_id, deal_id)` → compute `target_at`
  from `deal.stage_changed_at` walked forward by `target_minutes` of
  **business time** (skip outside `tenant_sla_settings.business_hours`,
  skip `holidays` dates) → insert `on_track`. For existing rows past
  `target_minutes`, elapsed check flips to `at_risk` (past `warning_at`)
  or `breached` (past `target_at`) via the `ON CONFLICT DO UPDATE` from
  §3.4. A row for a deal that has since left `stage_id` is deleted (SLA no
  longer applies) rather than left stale.
- `applies_to = 'task_due'`: same shape against open `tasks.due_at`.
- A transition **into** `breached` (not already breached) inserts an
  `escalations` row (`source = 'sla_breach'`, `assigned_to` = the deal's
  owner's `manager_id` — `422`-equivalent skip + logged warning if that
  owner has no manager set, rather than crashing the whole tenant's
  computation over one unassigned manager).

Business-hours math lives in `app/services/business_hours_service.py` —
a single `add_business_minutes(start: datetime, minutes: int, settings:
TenantSlaSettings) -> datetime` function, walking day-by-day against
`business_hours`/`holidays`. Kept as one small, directly-unit-testable
function rather than inlined into the Celery task, since this is the one
piece of this plan with genuine algorithmic risk (off-by-one across a
day/holiday boundary).

## 7. Workflow rule engine

### 7.1 Event-triggered rules

`PATCH /api/v1/deals/{id}` (stage change) and the lead-ingestion paths
(Phase 2's `POST /webhooks/*` and `app/connectors/ingestion_service.py`)
each enqueue `app/workers/rules.evaluate_event_rules.delay(tenant_id,
trigger_type, trigger_source_type, trigger_source_id, event_context)`
after their own transaction commits — evaluation itself never blocks the
triggering request. `task_overdue` has no natural write-time trigger (a
task doesn't get "touched" when it becomes overdue) and is instead scanned
by the same periodic mechanism as `elapsed_time` (§7.2), not listed twice.

### 7.2 Time-based rules

`app/workers/rules.py`, task `scan_time_based_rules(tenant_id)` on the same
5-minute Beat schedule as SLA computation (one dispatcher, two fan-out
task types per tenant). For each active `elapsed_time`/`task_overdue`
rule, finds matching deals/tasks whose `workflow_runs` dedupe index (§3.8)
shows no successful run yet, evaluates `conditions`, executes `actions` on
a match, and records the `workflow_runs` row via `ON CONFLICT DO NOTHING`
— a rule edited to re-fire (e.g. a wider condition) needs its target rows'
old `workflow_runs` entries cleared explicitly by an admin action; this
plan does not build an automatic re-fire path.

### 7.3 Rule CRUD and manager-proposal approval

```
GET    /api/v1/workflow-rules                admin sees all; manager sees
                                              their own proposals + active
                                              rules (read-only for the
                                              latter)
POST   /api/v1/workflow-rules                admin → status defaults 'active'
                                              (or 'draft' if body says so);
                                              manager → forced to
                                              'pending_approval' regardless
                                              of what the body requests
                                              (REQUIREMENTS.md §2.4 — never
                                              trust the client for this)
PATCH  /api/v1/workflow-rules/{id}            admin only — edit, or flip
                                              status (approve: pending_approval
                                              → active; reject: pending_approval
                                              → disabled)
```

### 7.4 Action execution

`app/workers/rules.py`'s `_execute_action` dispatches on `actions[].type`:

| Type | Behavior |
|---|---|
| `assign_round_robin` | Reuses `user_service.list_counselor_ids` + the same Redis `INCR`-based cursor pattern `lead_ingestion_service.py` already established (Phase 2) — not a new assignment algorithm. |
| `create_task` | Calls `task_service.create_task` directly (not the HTTP route) — same "write through the real service layer" principle as every connector. |
| `change_stage` | Calls `deal_service.update_deal` + `activity_service.log_deal_stage_changed`, actor = a fixed system user concept **does not exist yet** — reuses the deal's current `owner_id` as actor, same precedent Phase 2's `log_lead_captured` already set for "on behalf of" attribution. |
| `notify_manager` | Writes an `activities` row (`type='workflow_notification'`) on the relevant deal/contact, visible on the existing activity timeline and the Manager dashboard's escalations-adjacent view. **Not** a push/email/SMS delivery — no delivery channel exists yet (that's the architect-blocked comms work); this is an in-app, queryable signal only, sufficient for Phase 3's exit criterion ("notifies the right counselor") since REQUIREMENTS.md §6's entity list doesn't include a separate notifications table. |
| `raise_escalation` | Inserts an `escalations` row with `source='rule_triggered'` (§3.5), `workflow_run_id` = this action's own successful run — distinct from `workflow_failure`, which is the rule *itself* erroring rather than a deliberate action outcome. |
| `send_message` | Records `workflow_runs.status = 'skipped_unavailable'` with `error_message = 'comms provider not yet configured'`. Never silently succeeds. |

A rule whose action raises an unhandled exception records
`workflow_runs.status = 'failed'`, retries with Celery's built-in backoff
up to 3 attempts (`API_CONVENTIONS.md` has no stated retry policy for
background jobs; 3 is this plan's choice, configurable later), and on
final failure inserts an `escalations` row itself
(`source='workflow_failure'`, `assigned_to` = the rule's `created_by`'s
manager, falling back to `created_by` itself if they have no manager set)
— `REQUIREMENTS.md` §2.3's "automation failures should never fail
silently."

### 7.5 Auto-assignment — not a new subsystem

`FEATURES_AND_PLAN.md` lists "Auto-assignment" as its own bullet, but per
`REQUIREMENTS.md` §2.2's representative rule table it's just the
`lead_created` trigger's `assign_round_robin` + `create_task` actions —
built as the workflow engine's first realized rule type, not a parallel
mechanism. Two things worth flagging explicitly:

- Phase 2's inbound lead-capture paths (`app/services/lead_ingestion_service.py`,
  `app/connectors/ingestion_service.py`) **already** round-robin-assign an
  owner inline, before this plan's workflow engine exists to trigger from.
  This plan does not refactor that — it already works, is tested, and
  ingestion-time assignment has no natural "rule" to evaluate against yet
  at the moment a lead lands. It stays as-is.
- What Phase 3 actually adds: (a) round-robin assignment for **manually**
  created contacts (`POST /api/v1/contacts` today defaults `owner_id` to
  the creating user, never round-robins — a tenant can now configure a
  `lead_created` rule to override that), and (b) the "create a first-contact
  task due in 30 minutes" action, which has no Phase 1/2 equivalent at all.

## 8. Multi-tenancy check

- Every new table follows the standard `tenant_id` + RLS + leading
  composite index pattern (§3), except the two deliberately-flagged
  non-composite FKs (`escalations.sla_state_id`/`workflow_run_id` into
  hash-partitioned tables — §3.5/§3.8) and the two hash-partitioned tables
  themselves, which follow `DATABASE_SCHEMA.md` §3 instead of §2's simple
  index (both already tenant-scoped either way).
- `app/deps/scope.py`'s `RowScope` is an **application-layer** filter on
  top of RLS, not a second RLS policy — matches `REQUIREMENTS.md` §1.3's
  explicit reasoning (team membership changes over time, doesn't belong
  baked into a DB policy). RLS remains the tenant boundary; `RowScope`
  is the role boundary within a tenant.
- Every Celery task takes `tenant_id` as an explicit, required first
  parameter (`CLAUDE.md` rule 6) and sets `app.tenant_id` itself at the
  top of its own transaction — no task ever infers tenant from ambient
  state. The periodic dispatchers (`compute_sla_states`, `scan_time_based_rules`)
  fan out **one task per tenant**, never one task looping over every
  tenant in a single transaction — a slow or failing tenant can't block
  another's SLA computation.
- `workflow_rules.actions`/`conditions`/`trigger_config` are tenant-scoped
  JSONB, validated at write time (Pydantic) but never used to construct
  raw SQL — action execution dispatches on a fixed Python `type` enum,
  never `eval`s or dynamically builds a query string from rule content.

## 9. Task breakdown

Ordered, each a reviewable commit.

1. Migration: `users.manager_id` (§3.1).
2. Backend: `app/deps/scope.py` (`RowScope`, `get_row_scope`) +
   `user_service.list_team_member_ids`. Unit tests: admin unrestricted,
   manager gets self+team, counselor gets self-only.
3. Backend: apply `RowScope` to `contact_service`/`deal_service`/`task_service`
   list/get functions + their routes. Tests: a Staff user's list omits a
   teammate's lead; a Manager's list includes it; a single-row `get_*`
   outside scope is `404`.
4. Backend: reassignment guard (Staff `403` on any owner/assignee change,
   Manager `403` outside team) on the three `PATCH` routes. Tests per role.
5. Backend: `PATCH /api/v1/users/{id}` (role + `manager_id`, admin-only,
   validates target is actually a manager). Tests including the `400` on
   an invalid `manager_id`.
6. Migration: `tenant_sla_settings`, `sla_policies` (§3.2/§3.3).
7. Backend: `app/services/business_hours_service.py` —
   `add_business_minutes`. Unit tests: same-day, crosses a day boundary,
   crosses a weekend, crosses a holiday, crosses a DST-irrelevant
   timezone offset (tenant timezone, not server timezone).
8. Backend: `sla_policy_service.py` + `/api/v1/sla-policies` routes
   (admin-only). Tests including the `applies_to`/`stage_id` CHECK
   surfacing as `400`, not a raw `500`.
9. Migration: `sla_states` (hash-partitioned, §3.4).
10. Migration: `escalations`, `follow_up_flags` (§3.5/§3.6, with the
    `rule_triggered` source value from §7.4 included from the start —
    not added in a later migration).
11. Backend: `escalation_service.py` + `/api/v1/escalations` routes
    (manual raise, lifecycle-enforced `PATCH`). Tests: invalid transition
    is `400`; a Staff `PATCH` attempt to acknowledge/resolve is `403`;
    row-scoped `GET` per role.
12. Backend: `follow_up_flag_service.py` + `/api/v1/follow-up-flags`
    routes. Tests: a manager only sees their own flags; admin sees all.
13. `app/workers/` package: Celery app factory (`app/workers/celery_app.py`),
    configured against `REDIS_URL` as both broker and result backend.
    `docker-compose.yml`: new `worker` and `beat` services (`backend`
    image, `celery -A app.workers.celery_app worker`/`beat` as `CMD`,
    same `env_file: .env`). `backend/docker-entrypoint.sh` untouched —
    these are separate service entrypoints, not gated behind it.
14. Backend: `app/workers/sla.py` — `compute_sla_states(tenant_id)` +
    the Beat dispatcher. Tests (real Postgres/Redis, skip-cleanly
    convention already established): a deal past `target_minutes`
    transitions to `breached` and raises exactly one `escalations` row;
    re-running the tick doesn't duplicate it; a breached-owner with no
    `manager_id` logs a warning instead of crashing the tenant's tick.
15. Migration: `workflow_rules`, `workflow_runs` (§3.7/§3.8, hash-partitioned).
16. Backend: `workflow_rule_service.py` + `/api/v1/workflow-rules` routes,
    including the manager-proposal-forced-`pending_approval` guard and
    admin approve/reject. Tests per role, including that a manager's
    `POST` body claiming `status: "active"` is silently overridden to
    `pending_approval`, not honored or rejected.
17. Backend: `app/workers/rules.py` — `_execute_action` for
    `assign_round_robin`/`create_task`/`change_stage`/`notify_manager`/
    `raise_escalation`, and the `send_message` no-op recording. Unit
    tests per action type against a real Postgres (no Celery needed for
    these — test the dispatch function directly).
18. Backend: `evaluate_event_rules` task + enqueue call sites (deal
    stage-change route, Phase 2's ingestion paths). Tests: a
    `stage_changed` rule fires on the right transition and not others.
19. Backend: `scan_time_based_rules` task + Beat schedule entry. Tests:
    an `elapsed_time` rule fires once past the threshold, the dedupe
    index prevents a second fire on the next tick, a rule edited to
    widen its condition does not automatically re-fire on already-run
    rows (documented limitation from §7.2).
20. Backend: failure handling — retry-then-escalate on `_execute_action`
    exceptions (§7.4's tail paragraph). Test: an action forced to raise
    ends in exactly one `escalations` row after exhausting retries, not
    one per attempt.
21. Cross-service E2E (`tests/`): a configured `elapsed_time` rule
    ("no activity in 24h") fires against a real deal and creates the
    expected task/escalation within the running stack — this is
    `FEATURES_AND_PLAN.md`'s Phase 3 exit criterion, achieved without
    needing 24 real hours by seeding the deal's `stage_changed_at` in the
    past rather than waiting.
22. Frontend: Manager escalations queue (open/acknowledged, one-click
    acknowledge/resolve/reassign) + follow-up flags list. Admin SLA
    policy config screen (small — list + create, matching the
    Integrations screen's minimal-table-plus-form shape from Phase 2).
    Admin workflow rule list with pending-approval highlighting +
    approve/reject buttons. A full drag-and-drop rule *builder* UI is
    **not** included — admin/manager create rules via a structured form
    (trigger type dropdown, condition rows, action rows) mapping directly
    to the JSON shapes in §3.7, not a visual canvas; flagged as a
    `ux-designer`/`ui-designer` follow-up if the structured form proves
    too limiting in practice.
23. Docs: `DATABASE_SCHEMA.md` §1 gets all 7 new rows (`sla_policies`,
    `sla_states`, `escalations`, `follow_up_flags`, `workflow_rules`,
    `workflow_runs`, `tenant_sla_settings`) with their partitioning/FK
    notes; `ARCHITECTURE.md` gets a new section on the Celery worker/beat
    topology (local dev table + production EKS mapping, mirroring how §7a
    documented the connector pattern and §7b documented Phase 2's
    pipelines).

## 10. Acceptance criteria

1. A Staff user's `GET /api/v1/contacts` never includes a lead owned by a
   different Staff user in the same tenant; a Manager's list includes
   their direct reports' leads; an Admin's list is unfiltered.
2. A Staff `PATCH` changing `owner_id`/`assignee_id` on any of
   contacts/deals/tasks is `403`, even on their own record.
3. A Manager `PATCH` reassigning a lead to someone outside their team is
   `403`; reassigning within their team succeeds.
4. A deal sitting in a stage past its `sla_policies.target_minutes`
   (accounting for business hours/holidays) transitions to `breached` and
   raises exactly one `escalations` row assigned to the owner's manager —
   re-ticking the computation does not raise a second one.
5. `PATCH /api/v1/escalations/{id}` rejects `open → resolved` directly
   (`400`) but accepts `open → acknowledged → resolved`.
6. A configured `elapsed_time` workflow rule ("no activity in 24h, stage
   ≤ Contacted") fires exactly once per matching deal and creates the
   configured task — proven via the cross-service E2E test with a seeded
   past timestamp, not a real 24-hour wait.
7. A manager-authored workflow rule is `pending_approval` immediately
   after creation regardless of what `status` the request body claims;
   it only becomes `active` after an admin's explicit approval.
8. A `send_message` action never silently succeeds — it always records
   `workflow_runs.status = 'skipped_unavailable'`.
9. An action that raises on every retry attempt produces exactly one
   `escalations` row (`source='workflow_failure'`), not one per attempt.
10. Every new Celery task rejects being called without an explicit
    `tenant_id` argument (enforced by the function signature itself, not
    just convention) and sets `app.tenant_id` before its first query.
