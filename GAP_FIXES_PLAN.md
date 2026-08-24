# Gap-fix batch — 7 slices needing no new external secrets

Source: an architect gap-audit comparing `FEATURES_AND_PLAN.md` against
actual code, filtered down to findings that don't require connecting to
WhatsApp/Meta/Google (or any other new third-party credential). Each item
below is independent — a standalone reviewable PR, not one combined
feature. None of these are blocked on a `FEATURES_AND_PLAN.md` phase's
exit criteria: they're bugfix/hardening gaps inside phases already marked
done, not new phase work, so `feature-builder` can pick any of them up in
any order.

---

## 1. Tasks board view is a decorative stub

**Found in**: Phase 1 (Core CRM). `frontend/src/pages/TasksPage.tsx`'s
`load()` hardcodes `status: "open"` on every fetch regardless of which
view is active, so the Board view's "Done" column renders a header with
no data — completed tasks are never even requested.

### Affected layers
- **Frontend only.** `backend/app/api/tasks.py`'s `GET /api/v1/tasks`
  already accepts `status` as a filter — confirmed no backend change
  needed.
- Backend, database, BFF, background jobs: untouched.

### Database changes
None.

### API contract
None new. Reuses the existing `GET /api/v1/tasks?status=done&...` shape.

### Task breakdown
1. Add a `doneTasks` state slice to `TasksPage.tsx`.
2. Fetch `status: "done"` tasks only when `view === "board"` (a second
   `listTasks` call, gated on the view toggle — don't fetch it for list
   view, which stays open-only exactly as today).
3. Render `doneTasks` in the Board view's "Done" column in place of the
   current empty `<h2>Done</h2>` with nothing under it.
4. Extend `frontend/src/__tests__/TasksPage.test.tsx` with a board-view
   test: switching to Board issues a `status: "done"` request and renders
   the returned tasks in the Done column.

### Acceptance criteria
- Switching to Board view issues a request for `status=done` tasks.
- A task completed via the List view's complete action appears in the
  Done column the next time Board view is opened.
- List view's existing behavior (open-only, overdue/today/upcoming
  grouping) is unchanged.

---

## 2. No embeddable web-form widget

**Found in**: Phase 2 (Lead capture integrations). The ingestion endpoint
already exists and is real: `POST /webhooks/web` (`backend/app/webhooks/web.py`),
keyed by `embed_key` (== `LeadSourceConnection.external_account_id` for a
`source: "web"` connection — generated server-side in
`lead_source_connection_service.create_connection`, already returned to
the frontend today via the existing `createConnection` response, just
never surfaced as a usable snippet). `ConnectSourcePanel.tsx` only shows
"an embeddable form key is generated automatically" with no actual embed
code to copy.

### A dependency this item surfaces: `/webhooks/*` has no public ingress path yet
`ARCHITECTURE.md` (§6, line ~218) already documents the intended design:
`/webhooks/*` needs a **second, public** ingress path on the same ALB as
`backend`, distinct from `/api/v1/*` (internal-only, BFF-reachable only).
But `deploy/helm/backend/values.yaml` currently has a single
`ingress.enabled: false` toggle for the whole chart — there is no
path-split implementing that documented design yet. Locally this doesn't
matter (`docker-compose.yml` already publishes the backend's port
directly), but the embed snippet built here would be unreachable from a
real tenant's landing page in an actual Helm deployment without this.
This is implementing an **already-decided** architecture note, not a new
structural decision, so it doesn't need a fresh architect pass — just
needs to be in scope for this slice, not silently skipped.

### Affected layers
- **Frontend**: `ConnectSourcePanel.tsx` (or a new small component) to
  render the copy-paste embed snippet once a `web` connection exists;
  needs to know the backend's public base URL for the target deployment
  (check whether a `VITE_*` env var for this already exists — if not,
  add one, since it's deployment-specific and must not be hardcoded).
- **Backend**: none — endpoint already works as-is.
- **Helm** (`deploy/helm/backend`): add the public `/webhooks/*` ingress
  path per `ARCHITECTURE.md` §6, alongside the existing internal-only
  path. No application code change.
- Database, BFF, background jobs: untouched.

### Database changes
None.

### API contract
None new. Documents the existing `POST /webhooks/web` contract
(`embed_key`, `full_name`, `email`, `phone`, `course_code`,
`idempotency_key`) inside the generated snippet/instructions.

### Task breakdown
1. Confirm/add a frontend env var for the backend's public base URL
   (deployment-specific — do not hardcode a domain, matching this repo's
   existing `.env`/`.env.example` split convention).
2. Build a minimal embeddable snippet (a small vanilla-JS form POST, no
   framework dependency, since it must run on an arbitrary external
   landing page) that submits to `POST {backend_base_url}/webhooks/web`
   with the connection's `embed_key`.
3. Surface a "Copy embed code" UI in `ConnectSourcePanel.tsx` (or a
   follow-up detail view) once a `web` connection is created/selected.
4. Add the `/webhooks/*` public ingress path to
   `deploy/helm/backend/values.yaml` + `templates/ingress.yaml` (or
   equivalent), following the existing chart's pattern for `web`/`bff`'s
   ingress blocks. Run `helm lint deploy/helm/backend` and
   `helm template` to verify.
5. Manual end-to-end check: generate a connection locally, submit the
   snippet against the local stack, confirm a contact/deal appears.

### Acceptance criteria
- A newly created `web` lead-source connection shows a working,
  copy-pasteable embed snippet.
- Submitting that snippet against the local docker-compose stack creates
  a contact (verified manually, matching this session's existing
  live-stack verification convention).
- `helm lint deploy/helm/backend` passes with the new ingress path added.
- The internal `/api/v1/*` ingress path remains unchanged (still
  BFF-only, per `ARCHITECTURE.md` §6) — this only adds a second path, it
  doesn't loosen the first.

---

## 3. No territory-based auto-assignment

**Found in**: Phase 3 (Communication & automation). Only round-robin
exists today (`lead_ingestion_service.py`'s Redis-cursor round robin, and
the `assign_round_robin` workflow-rule action in `app/workers/rules.py`).
No `territory` concept exists anywhere in the schema.

**Scope decision**: no current lead source (connector or real webhook)
emits any location/territory signal on a raw lead — `RawLead`
(`app/connectors/base.py`) has no such field, and none of Meta/Google/web
form/WhatsApp payloads are mapped to one today. Building full "assign by
the lead's detected territory" would require deciding how a lead's
territory gets populated in the first place, which is out of scope for a
no-new-integration slice. Minimal viable version instead: an **admin-set**
`territory` on both `users` and `contacts`, matched by a new workflow-rule
action — usable today for contacts an admin/counselor manually tags, and
ready for a real connector to populate later without a further schema
change.

### Affected layers
- **Database**: two nullable-column migrations (`users.territory`,
  `contacts.territory`) — see below.
- **Backend**: `app/schemas/user.py` / `user_service.py` (or wherever
  territory should be settable — likely admin-only, alongside
  `manager_id`'s existing pattern); `app/schemas/contact.py`'s
  `ContactUpdate` gets a `territory` field; new `assign_by_territory`
  action in `app/workers/rules.py`, mirroring `assign_round_robin`'s
  existing shape, falling back to round-robin when no counselor in the
  contact's territory exists.
- **Frontend**: territory becomes a settable field wherever
  owner/assignment is edited (contact edit, workflow-rule action picker)
  — scope precisely during implementation; not a full admin console.
- BFF, document/document upload: untouched.

### Database changes
Two additive, nullable-column migrations — not new tables, so no new RLS
policy needed (existing table policies already cover the new column):

```sql
ALTER TABLE users ADD COLUMN territory TEXT;
ALTER TABLE contacts ADD COLUMN territory TEXT;
```

Per `DATABASE_SCHEMA.md` §5, no composite index is required for a
low-cardinality, optionally-filtered column unless a query pattern
demands it — defer adding one unless the implementation ends up filtering
lists by territory at scale.

### API contract
- `PATCH /api/v1/users/{id}` (existing admin-only route) gains an
  optional `territory` field, same envelope.
- `PATCH /api/v1/contacts/{id}` (existing route) gains an optional
  `territory` field, same envelope.
- No new endpoints.

### Multi-tenancy check
Both columns live on already tenant-scoped, RLS-protected tables — no new
cross-tenant surface. The new workflow action only ever queries
counselors within the rule's own `tenant_id` (same pattern
`assign_round_robin` already follows).

### Task breakdown
1. Alembic migration: add `territory` to `users` and `contacts`.
2. Backend: extend `UserUpdate`/`ContactUpdate` schemas + services.
3. Backend: `assign_by_territory` action in `app/workers/rules.py` —
   match `contact.territory` against active counselors' `users.territory`
   in the same tenant; if none match, fall back to the existing
   round-robin path (don't leave a contact unassigned).
4. Frontend: expose `territory` as an editable field on the contact
   detail page and (if the rule-builder UI enumerates action types by
   name) as a selectable action in `CreateWorkflowRulePanel.tsx`.
5. Tests: backend unit test for the fallback-to-round-robin path, and a
   tenant-isolation test proving the match never crosses tenants.

### Acceptance criteria
- A contact with `territory = "north"` and an active counselor with
  `territory = "north"` in the same tenant: the `assign_by_territory`
  action assigns that counselor.
- A contact with no territory match in its tenant: falls back to
  round-robin, never left unassigned.
- A counselor with a matching `territory` in a *different* tenant is
  never selected (tenant-isolation test).

---

## 4. No systemic per-tenant rate limiting

**Found in**: Phase 5 (Multi-tenancy hardening). Today's only rate
limiter (`backend/app/core/rate_limit.py`) protects a single
unauthenticated endpoint (`POST /webhooks/web`), keyed by embed key.
`API_CONVENTIONS.md` §8 already specifies where this belongs: **"Enforced
at the BFF layer, keyed by tenant_id, backed by Redis... FastAPI returns
429 if it independently detects abuse (defense in depth), but primary
enforcement lives in the BFF."** So this isn't a new design decision —
it's implementing a documented-but-unbuilt contract.

### Affected layers
- **BFF** (primary): a new rate-limit middleware in `bff/src/middleware/`,
  applied to the existing `app.use("/api/v1", requireAuth,
  createBackendProxy())` chain in `bff/src/app.ts` — keyed by the already-
  validated `tenant_id` (available post-`requireAuth`), backed by the
  BFF's existing Redis connection (confirm one already exists for the BFF
  process; if not, this is the one place a new dependency might be
  needed — a Redis *client*, not a new external service, since `redis` is
  already in the stack).
- Backend: unchanged — its own defense-in-depth 429 already exists in
  spirit for the one endpoint it covers; extending that further is
  optional, not required for this slice.
- Database: untouched.

### Database changes
None.

### API contract
No new routes. On limit exceeded, the BFF returns the existing error
envelope shape with `code: "RATE_LIMITED"`, `429` — already a documented
standard code in `API_CONVENTIONS.md` §4, just not yet emitted by this
layer.

### Task breakdown
1. Add a Redis client to the BFF if one doesn't already exist (check
   `bff/src` for existing Redis usage first).
2. Add `bff/src/middleware/rateLimit.ts`: fixed-window (or sliding-window)
   counter keyed by `tenant_id`, mirroring the pattern already used in
   `backend/app/core/rate_limit.py` (same shape, different key).
3. Wire it into the `/api/v1` chain in `app.ts`, after `requireAuth` (so
   `tenant_id` is available) and before `createBackendProxy()`.
4. Make the limit configurable via env var (Helm value + `.env.example`
   entry), not hardcoded — this needs to differ between a small
   single-tenant deployment and pooled SaaS.
5. BFF test: a burst of requests past the configured limit gets a 429
   with the correct envelope; requests from a different tenant are
   unaffected by another tenant's limit (proves the per-tenant keying,
   not a global limiter).

### Acceptance criteria
- Exceeding the configured per-tenant request rate returns `429` /
  `RATE_LIMITED` in the standard error envelope.
- Tenant A hitting its limit does not affect tenant B's requests in the
  same window.
- Limit is configurable per deployment (env var / Helm value), not a
  hardcoded constant.

---

## 5. No load testing

**Found in**: Phase 5 (Multi-tenancy hardening). No k6/locust/artillery
scripts exist anywhere in the repo.

### Affected layers
- New top-level `loadtest/` directory (script + config only — no
  application code touched).
- `CLAUDE.md`'s Commands section gets a new entry documenting how to run
  it, matching this repo's existing convention of every runnable command
  being listed there.
- Nothing else — this doesn't touch frontend/bff/backend/db source.

### Database changes
None.

### API contract
None — it's a client of the existing API, not a new endpoint.

### Tool choice
**k6**, run via its official Docker image (`grafana/k6`) rather than
adding an npm/pip dependency to any of the three services — keeps this
slice fully isolated from `frontend`/`bff`/`backend`'s own dependency
trees, and matches how this repo already treats one-off tooling (e.g.
the cross-service E2E test in `/tests` has its own
`tests/requirements.txt`, separate from `backend`'s).

### Task breakdown
1. `loadtest/scenarios/mixed-traffic.js` — a k6 script simulating the
   plan's stated exit criterion: skewed multi-tenant traffic (e.g. one
   "large tenant" VU pool hitting contacts/pipeline/tasks list endpoints
   at higher volume, one "small tenant" pool at lower volume), against
   real seeded tenant IDs/tokens from the local stack.
2. A short `loadtest/README.md` covering prerequisites (stack must be
   running via `docker compose up`) and how tokens are obtained for the
   script (reuse the same Keycloak direct-grant approach
   `tests/test_tenant_isolation.py` already uses, if applicable, rather
   than inventing a second auth method).
3. Add the run command to `CLAUDE.md`'s Commands section.
4. Do one real run against the local stack and record baseline numbers
   (p50/p95 latency, error rate) in `loadtest/README.md` as a reference
   point for future comparisons — not a hard pass/fail gate for this
   slice, since no SLO has been set yet.

### Acceptance criteria
- `loadtest/scenarios/mixed-traffic.js` runs successfully against a local
  `docker compose up` stack via a documented one-line command.
- The script exercises at least two tenants concurrently at different
  traffic volumes (the plan's "skewed tenant sizes" requirement).
- A baseline results snapshot exists in `loadtest/README.md`.

---

## 6. No audit log

**Found in**: listed in `FEATURES_AND_PLAN.md`'s feature set, not tied to
a specific phase's exit criteria. `DATABASE_SCHEMA.md` §1 already lists
`audit_log` in its entity table with the note "not yet built; no phase
has claimed it" — confirming this is a known, intentionally-deferred gap,
not an oversight.

**Scope decision for v1**: DB-only, write-side only, no API/UI yet.
Building a full admin-facing audit viewer is a second slice on top of
this one — keeping this one to "the data actually gets captured" avoids
combining a schema decision with a UI decision in one PR.

**Deviation from the original plan, found once actually in the code**:
`user role/status changes` isn't a real call site — `UserUpdate`
deliberately excludes `role`/`status` (see its own docstring:
Keycloak JIT-provisioning refreshes `role` from the token claim on every
request, so an in-app role change would be silently reverted). The only
real user-mutation path today is `update_user_manager` (manager
reassignment). v1's three logged events are: user manager reassignment,
deal stage changes, and escalation acknowledge/resolve/reassign actions.

### Affected layers
- **Database**: new `audit_logs` table (append-only, standard
  tenant-scoped pattern).
- **Backend**: a small `audit_log_service.py` with one `record()`
  function, called from the existing service functions that already
  perform the v1 event set (`user_service.update_user_manager`/role-path,
  `deal_service`'s stage-change path, `escalation_service.update_escalation`).
  No new API route in this slice.
- Frontend, BFF, background jobs: untouched in this slice.

### Database changes
Standard tenant-scoped pattern per `DATABASE_SCHEMA.md` §2, append-only
(no `updated_at`, since rows are never modified):

```sql
CREATE TABLE audit_logs (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    actor_id    UUID NOT NULL,
    event_type  TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   UUID NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (actor_id, tenant_id) REFERENCES users (id, tenant_id)
);

CREATE INDEX idx_audit_logs_tenant_entity
    ON audit_logs (tenant_id, entity_type, entity_id, created_at DESC);

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

Not hash-partitioned in v1 — audit events are far lower-volume than
`activities`/`sla_states`/`workflow_runs`; revisit if that assumption
turns out wrong.

### API contract
None in this slice (v1 is write-only, no read endpoint yet — noted above).

### Task breakdown
1. Alembic migration for `audit_logs` (table + RLS + index, one
   migration, per `DATABASE_SCHEMA.md` §5).
2. `app/services/audit_log_service.py`: `record(db, tenant_id, actor_id,
   event_type, entity_type, entity_id, payload)`.
3. Call sites: role/status change in `user_service.py`, stage-change in
   `deal_service.py`, and `escalation_service.update_escalation`'s
   status/reassign transitions — one `record()` call each, inside the
   same transaction as the change being logged.
4. Backend tests: each call site actually writes a row with the correct
   `tenant_id`/`event_type`; a tenant-isolation test proving tenant A's
   audit rows are invisible under tenant B's `app.tenant_id`.

### Acceptance criteria
- A role change, a deal stage change, and an escalation
  acknowledge/resolve/reassign each produce exactly one `audit_logs` row.
- A row's `tenant_id` always matches the change it recorded (no
  cross-tenant writes possible even in principle, since it's written
  inside the same RLS-scoped transaction).
- Querying `audit_logs` under tenant A's `app.tenant_id` never returns
  tenant B's rows (automated test, not just manual check).

---

## 7. `documents` isn't hash-partitioned like its high-volume siblings

**Found in**: Phase 5 (partial). `activities` (0006), `sla_states`
(0012), and `workflow_runs` (0014) are already hash-partitioned by
`tenant_id`. `documents` (0008) isn't, despite being a similarly
tenant-scoped, potentially high-row-count table.

**Complication checked**: no other table holds a composite FK referencing
`documents(id, tenant_id)` (confirmed by search) — so converting it
doesn't cascade into other tables' constraints, unlike a table something
else points at. The real complication is mechanical: Postgres can't
`ALTER TABLE ... PARTITION BY` an existing populated table in place — the
migration has to create a new partitioned table, copy existing rows,
then swap names, rather than a one-line DDL change like the original
`CREATE TABLE` migrations for `activities`/`sla_states`/`workflow_runs`
had the luxury of (those were partitioned from creation, before any data
existed).

### Affected layers
- **Database only.** No application code changes — `app/models/document.py`
  et al. don't need to change; SQLAlchemy addresses the parent table name
  exactly as it does today, same as `activities`.
- Backend service/API code: untouched (confirmed no code depends on
  `documents` being a plain table vs. partitioned — no direct SQL
  outside the ORM layer referencing it).

### Database changes
One migration, following `0006_activities.py`'s partitioning shape but as
a create-copy-swap:

```sql
-- 1. Create the new partitioned table under a temp name, same columns/
--    constraints as the existing 0008 migration.
CREATE TABLE documents_new (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    contact_id   UUID NOT NULL,
    deal_id      UUID,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   BIGINT NOT NULL,
    s3_key       TEXT NOT NULL,
    uploaded_by  UUID NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
    FOREIGN KEY (uploaded_by, tenant_id) REFERENCES users (id, tenant_id)
) PARTITION BY HASH (tenant_id);

-- 2. 16 partitions, same pattern as 0006/0012/0014.
-- 3. INSERT INTO documents_new SELECT * FROM documents;
-- 4. DROP TABLE documents; ALTER TABLE documents_new RENAME TO documents.
-- 5. Recreate idx_documents_tenant_contact, uq_documents_tenant_s3_key,
--    RLS + policy (indexes/RLS on the old table are dropped with it).
```

`downgrade()` needs the mirror-image swap back to a plain table — write
it, don't skip it, since every other migration in this repo has a real
downgrade.

### API contract
None — purely internal storage change, `documents` API responses are
unaffected.

### Task breakdown
1. Write the migration exactly as sketched above (adapt from
   `0006_activities.py`'s partition-creation loop and `0008_documents.py`'s
   original column/constraint list — both already read for this plan).
2. Run it against the local stack; verify `documents` still round-trips
   correctly (upload → list → download) via the existing document tests.
3. Verify `alembic downgrade -1` correctly reverts to a plain table
   without data loss (run it against a copy with real seeded documents).
4. Re-run `backend/tests/test_documents_endpoint.py` and the tenant-
   isolation DB test to confirm RLS still holds post-migration.

### Acceptance criteria
- `documents` is hash-partitioned (16 partitions, same as its siblings),
  confirmed via `\d+ documents` showing `PARTITION BY HASH`.
- All existing document rows survive the migration with no data loss.
- `alembic downgrade -1` cleanly reverts.
- Existing document upload/list/download flow and its tests pass
  unchanged.
