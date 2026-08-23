# Database schema conventions

## 1. Core entities (initial set)

| Table | Purpose | Notes |
|---|---|---|
| `tenants` | One row per client | No `tenant_id` column (this table is global) |
| `users` | Platform users (counselors, managers, admins) | `tenant_id`, role |
| `contacts` | Leads/students | `tenant_id`, `stage`, `lead_source`, `owner_id` |
| `pipeline_stages` | Configurable per-tenant pipeline stages | `tenant_id`, ordering |
| `deals` | Optional — if a contact can have multiple concurrent applications/courses | `tenant_id`, `contact_id`, `course_id` |
| `courses` | Program/course catalog | `tenant_id` |
| `activities` | Calls, emails, WhatsApp messages, stage changes | `tenant_id`, high write volume — hash-partitioned |
| `tasks` | Follow-ups, reminders | `tenant_id`, `assignee_id`, `due_at` |
| `documents` | Metadata for uploaded files (actual file in S3/MinIO) | `tenant_id`, `contact_id` |
| `workflow_rules` | Automation rule definitions | `tenant_id` |
| `workflow_runs` | Execution log of triggered workflows | `tenant_id`, high write volume |
| `payments` | Fee/EMI records | `tenant_id`, `contact_id` |

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
