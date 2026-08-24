# Database schema conventions

## 1. Core entities (initial set)

| Table | Purpose | Notes |
|---|---|---|
| `tenants` | One row per client | No `tenant_id` column (this table is global) |
| `users` | Platform users (counselors, managers, admins) | `tenant_id`, role, `manager_id` (self-referencing, nullable — the RBAC team mapping; no separate mapping table, `PHASE_3_PLAN.md` §3.1/§4). `role`/`status` stay JIT-refreshed from Keycloak on every request; an admin-triggered change goes through Keycloak's Admin API first and only writes here on that call's success — never the other way around — `ARCHITECTURE.md` §4a |
| `contacts` | Leads/students | `tenant_id`, `lead_source`, `owner_id` — **not** `stage`: a contact can hold multiple concurrent `deals`, each with its own stage, so stage lives on `deals` (resolved in Phase 1 — see `DATABASE_SCHEMA.md` §2's `deals` row and `PHASE_1_PLAN.md` §2) |
| `pipeline_stages` | Configurable per-tenant pipeline stages | `tenant_id`, `sort_order`, `is_won`/`is_lost` (not the tenant-editable name) is what later phases read; `win_probability_pct` (default `0`) drives Phase 4's stage-weighted forecast — `PHASE_4_PLAN.md` §3.1 |
| `deals` | One row per application — a contact can have several concurrent (resolved in Phase 1, was "optional") | `tenant_id`, `contact_id`, `course_id`, `stage_id` |
| `courses` | Program/course catalog | `tenant_id` |
| `activities` | Calls, emails, WhatsApp messages, stage changes | `tenant_id`, high write volume — hash-partitioned |
| `tasks` | Follow-ups, reminders | `tenant_id`, `assignee_id`, `due_at` |
| `documents` | Metadata for uploaded files (actual file in S3/MinIO) | `tenant_id`, `contact_id` |
| `workflow_rules` | Automation rule definitions (trigger/conditions/actions as JSONB) | `tenant_id`; `status` includes `pending_approval` — a Manager-authored rule is always forced into that status server-side regardless of what the request claims (`REQUIREMENTS.md` §2.4, `PHASE_3_PLAN.md` §7.3) |
| `workflow_runs` | Execution log — one row per (rule, trigger source), not per action | `tenant_id`, hash-partitioned (high write volume), `workflow_rule_id` **is** a composite FK (unlike the exceptions below — `workflow_rules` isn't partitioned, so no obstacle) |
| `payments` | Fee/EMI records | `tenant_id`, `contact_id` |
| `lead_source_connections` | Per-tenant Meta/Google/WhatsApp/web connection credentials | `tenant_id`, but **no RLS** — a second documented global exemption alongside `tenants`: a webhook has to look up `external_account_id` to *discover* `tenant_id` before `app.tenant_id` can be set, so a policy keyed on that session variable can't gate this table. Every query against it filters `tenant_id` explicitly in application code instead — see `PHASE_2_PLAN.md` §3. `conversion_target_id` (nullable — the Meta Pixel/Dataset ID or Google conversion action resource name) reuses this table's existing encrypted credentials for outbound conversion sends rather than a second credentials table — `ARCHITECTURE.md` §7d, `PHASE_4B_CONVERSIONS_PLAN.md` |
| `conversion_events` | Delivery tracking for outbound Meta/Google conversion sends | `tenant_id`, `deal_id` composite FK — one row per (deal, platform), upserted rather than insert-only so a retried/duplicate send updates the same row — `ARCHITECTURE.md` §7d, `PHASE_4B_CONVERSIONS_PLAN.md` |
| `tenant_sla_settings` | Business hours + holidays the SLA clock computes against | `tenant_id`; one row per tenant enforced by a unique index, **not** a different PK shape — still `(id, tenant_id)` per §2's "do not deviate," `PHASE_3_PLAN.md` §3.2 |
| `sla_policies` | Tenant-configured SLA targets per stage/task type | `tenant_id` — see `REQUIREMENTS.md` Section 3, `PHASE_3_PLAN.md` §3.3 |
| `sla_states` | Computed on_track/at_risk/breached state per tracked item | `tenant_id`, hash-partitioned (high write volume) — computed by a Celery Beat task, never written by a request handler, `PHASE_3_PLAN.md` §6 |
| `escalations` | Escalation records with lifecycle and resolution notes | `tenant_id` — see `REQUIREMENTS.md` Section 4. `sla_state_id`/`workflow_run_id` are plain `UUID`, **not** composite FKs — both would reference a non-partition-key column of a hash-partitioned table, which Postgres can't express cleanly here (`PHASE_3_PLAN.md` §3.5) |
| `follow_up_flags` | Manager's personal follow-up reminders on leads | `tenant_id`, `manager_id` |
| `audit_log` | Configuration change history for Admin visibility | `tenant_id`, append-only — **not yet built**; no phase has claimed it (`DEVELOPMENT_PLAN.md` §8's original flag still stands after Phase 3) |

Role-based access (Admin/Manager/Staff) is enforced at the application layer
on top of these tables, not as additional RLS policies — see
`REQUIREMENTS.md` Section 1.3 for why.

## 2. Standard tenant-scoped table pattern

Every tenant-scoped table follows this shape. Copy this pattern for each new
table — do not deviate.

```sql
CREATE TABLE <table_name> (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    -- ... table-specific columns ...
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
);

CREATE INDEX idx_<table_name>_tenant_<common_filter>
    ON <table_name> (tenant_id, <common_filter_column>, created_at DESC);

ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_<table_name> ON <table_name>
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

Notes:
- `tenant_id` is part of the primary key so the table can be converted to a
  partitioned table later without a rewrite.
- Pick `<common_filter_column>` based on the table's most frequent query
  pattern (e.g., `stage` for `contacts`, `type` for `activities`).
- `FORCE ROW LEVEL SECURITY` is required — without it, the owning role
  bypasses RLS.

## 3. High-volume tables: hash partitioning

Tables expected to grow fast (`activities`, `workflow_runs`) are
hash-partitioned by `tenant_id` from the start:

```sql
CREATE TABLE activities (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    contact_id  UUID NOT NULL,
    type        TEXT NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
) PARTITION BY HASH (tenant_id);

-- 16 partitions to start; indexes created on the parent propagate
-- to all partitions automatically.
DO $$
BEGIN
    FOR i IN 0..15 LOOP
        EXECUTE format(
            'CREATE TABLE activities_p%s PARTITION OF activities
                FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
    END LOOP;
END $$;
```

RLS and indexing follow the same standard pattern above, applied to the
parent table.

## 4. Session tenant context

Every request handler in FastAPI must set the session variable before
running any query:

```sql
SELECT set_config('app.tenant_id', :tenant_id, false);
```

With PgBouncer in transaction-pooling mode, use `SET LOCAL` per transaction
instead, since pooled connections are shared across tenants between
transactions.

## 5. Migrations

- Use Alembic for all schema changes.
- Every migration that adds a tenant-scoped table must include the RLS
  policy and composite index in the same migration — not as a follow-up.
- Never write a migration that drops or weakens an RLS policy without
  explicit review (see `CLAUDE.md`).

## 6. Single-tenant deployments

Same DDL is used for single-tenant/VPC deployments. `tenant_id` and RLS
policies remain in the schema even though there's only one tenant — this
keeps the schema identical across both deployment modes and avoids
maintaining a second migration path.
