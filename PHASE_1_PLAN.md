# Phase 1 plan — Core CRM

Produced by the `feature-planner` skill. **No application code is written by
this document.** Hand to `feature-builder` (or a human reviewer) before
implementation begins.

## 0. Prerequisite check

Per `CLAUDE.md` and `FEATURES_AND_PLAN.md` §3, Phase N+1 isn't planned until
Phase N's exit criteria are met. Phase 0's are:

> a logged-in user in tenant A cannot see tenant B's data, proven with an
> automated test; `docker compose up` brings up the full stack from a clean
> checkout with no manual steps.

Both hold: `tests/test_tenant_isolation.py` passes against the live stack,
and `docker compose up` has been verified twice from empty volumes with
default ports. Phase 1 is cleared to plan.

## 1. Scope

Per `FEATURES_AND_PLAN.md` §2, Phase 1 — Core CRM:

- Contacts/leads: CRUD, search, filters, dedupe on create
- Pipeline: stages (configurable per tenant), stage transitions, activity log
- Tasks: create, assign, due dates, list/board view
- Basic document upload (S3/MinIO)

**Exit criteria**: a counselor can manually create a lead, move it through
stages, attach a document, and complete a task.

## 2. Decision: a contact can hold multiple concurrent deals

`DATABASE_SCHEMA.md` flags `deals` as optional — *"if a contact can have
multiple concurrent applications/courses."* Confirmed: yes, a contact can
apply to more than one course at once. This changes the shape of the schema
materially, so it's recorded here rather than left implicit:

- **Pipeline stage lives on `deals`, not `contacts`.** `DATABASE_SCHEMA.md`
  §1's sketch lists `stage` as a `contacts` column — that sketch predates
  this decision. A contact with two open applications would have two
  different stages simultaneously, so a single stage field on `contacts`
  is wrong once deals exist. `contacts` becomes the person/lead record;
  `deals` is one row per application, each with its own stage and course.
  `DATABASE_SCHEMA.md`'s entity table gets corrected in this phase's docs
  step (§8 below) once built — not before, per the doc's own convention of
  reflecting what was actually built.
- Every place `FEATURES_AND_PLAN.md`/`DATABASE_SCHEMA.md` says "stage
  transitions" or "move it through stages," read that as **deal** stage
  transitions.

## 3. Affected layers

| Layer | Touched | Changes |
|---|---|---|
| **Database** | Yes | Five new tables: `courses`, `contacts`, `pipeline_stages`, `deals`, `tasks`, `documents`, plus `activities` (hash-partitioned, per `DATABASE_SCHEMA.md` §3). See §4. |
| **Backend** | Yes | CRUD services + routes for each resource, dedupe logic on contact create, stage-transition activity logging, S3/MinIO presigned-upload flow. |
| **BFF** | Yes | Proxy routes for every new `/api/v1/*` resource — no new auth logic; the existing `requireAuth` + header-forwarding from Phase 0 already covers this (`bff/src/app.ts`'s `/api/v1` mount applies to all of these). |
| **Frontend** | Yes | Contacts list + detail, pipeline board (drag-drop stage changes per `FEATURES_AND_PLAN.md`), task list/board, document upload. Route through `ui-designer`/`ux-designer` before building — this is the first phase with a real counselor-facing surface beyond the Phase 0 shell. |
| **Background jobs** | No | Nothing here needs Celery. `app/workers` stays structural-only until Phase 3, per `DEVELOPMENT_PLAN.md` §1. Document virus-scanning/thumbnailing would be a job — explicitly **out of scope** for Phase 1, not silently dropped. |

## 4. Database changes

All tables follow `DATABASE_SCHEMA.md` §2's standard pattern exactly:
`id`/`tenant_id` composite PK `(id, tenant_id)` — matching the actual Phase 0
`users` table, not a sketch — tenant_id-leading indexes, RLS enabled +
forced, and a `USING`/`WITH CHECK` policy on
`current_setting('app.tenant_id')::uuid` (the strict, raising form — see
`DEVELOPMENT_PLAN.md` §3.3, still the rule).

**Composite foreign keys, not bare ones.** Every FK from a new table to
`users` or between these new tables must reference `(id, tenant_id)` as a
pair, e.g. `FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id,
tenant_id)` — never a bare `owner_id UUID REFERENCES users(id)`. RLS blocks
a cross-tenant *read*, but a single-column FK doesn't stop a `contacts` row
in tenant A from being *linked* to a `users` row in tenant B at the
constraint level. This is the one new structural rule this phase adds to
the standard pattern and it must be repeated on every FK below.

### 4.1 `courses`

```sql
id, tenant_id, name, code, status ('active'|'inactive'), created_at, updated_at
UNIQUE (tenant_id, code)
INDEX (tenant_id, status, created_at DESC)
```

### 4.2 `pipeline_stages`

```sql
id, tenant_id, name, sort_order, is_won BOOLEAN, is_lost BOOLEAN,
created_at, updated_at
UNIQUE (tenant_id, name)
UNIQUE (tenant_id, sort_order)
INDEX (tenant_id, sort_order)
```

`is_won`/`is_lost` (not a hardcoded stage name) is what Phase 4's
forecasting/win-probability work reads — deciding this now avoids a
migration later. Default stages (`Inquiry → Contacted → Demo scheduled →
Demo attended → Application submitted → Fee paid → Enrolled`, `Dropped` as
`is_lost`) are **seeded lazily**, not at tenant-creation time — Phase 0 has
no tenant-provisioning flow yet (`DEVELOPMENT_PLAN.md` §8 already flags this
gap). A backend service function `ensure_default_stages(tenant_id)` runs
idempotently the first time a tenant's `pipeline_stages` list is empty and
requested. "Configurable per tenant" is read as: rename/reorder via API:
full drag-to-reorder admin UI is **out of scope** — that's Platform/admin
console territory, unassigned to a phase in `FEATURES_AND_PLAN.md`.

### 4.3 `contacts`

```sql
id, tenant_id, full_name, email, phone, lead_source,
owner_id, status ('active'|'archived'), created_at, updated_at
FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
UNIQUE (tenant_id, lower(email)) WHERE email IS NOT NULL
UNIQUE (tenant_id, phone) WHERE phone IS NOT NULL
INDEX (tenant_id, owner_id, created_at DESC)
INDEX (tenant_id, created_at DESC)
```

Dedupe is exact-match on email/phone within the tenant (partial unique
indexes), enforced at the DB layer, not just app-side — matches
`FEATURES_AND_PLAN.md`'s "dedupe on create." Fuzzy/cross-campaign duplicate
detection (`FEATURES_AND_PLAN.md`'s EdTech-specific "duplicate lead
detection across campaigns") is **not** in this phase — it's listed without
a phase assignment, and exact-match is what "dedupe on create" literally
asks for.

### 4.4 `deals`

```sql
id, tenant_id, contact_id, course_id, stage_id, owner_id,
stage_changed_at, created_at, updated_at
FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id)
FOREIGN KEY (course_id, tenant_id) REFERENCES courses (id, tenant_id)
FOREIGN KEY (stage_id, tenant_id) REFERENCES pipeline_stages (id, tenant_id)
FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
INDEX (tenant_id, stage_id, created_at DESC)   -- board view, grouped by stage
INDEX (tenant_id, contact_id)                  -- all deals for a contact
INDEX (tenant_id, owner_id, stage_id)
```

`stage_changed_at` is tracked now (cheap, one timestamp) even though
per-stage SLA alerting is Phase 3 automation work — avoids a migration to
add it retroactively when that phase needs it.

### 4.5 `activities` — hash-partitioned per `DATABASE_SCHEMA.md` §3

```sql
id, tenant_id, contact_id, deal_id NULL, type, actor_id, payload JSONB,
created_at
PARTITION BY HASH (tenant_id), 16 partitions, exactly the DDL in
DATABASE_SCHEMA.md §3
```

Phase 1 writes exactly one `type`: `deal_stage_changed` (old stage, new
stage, actor) — matching `FEATURES_AND_PLAN.md`'s "stage transitions,
activity log." Logging contact-create/task-complete/document-upload events
is a natural extension but **not required** for this phase's exit criteria;
don't add those writers unless asked, since each one is a real design
surface (what payload shape, what it's for) not a free extra.

### 4.6 `tasks`

```sql
id, tenant_id, contact_id, deal_id NULL, assignee_id, title, description,
due_at, status ('open'|'done'), completed_at NULL, created_at, updated_at
FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id)
FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id)
FOREIGN KEY (assignee_id, tenant_id) REFERENCES users (id, tenant_id)
INDEX (tenant_id, assignee_id, status, due_at)  -- "my open tasks, by due date"
INDEX (tenant_id, contact_id, created_at DESC)
```

### 4.7 `documents`

```sql
id, tenant_id, contact_id, deal_id NULL, filename, content_type,
size_bytes, s3_key, uploaded_by, created_at
FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id)
FOREIGN KEY (uploaded_by, tenant_id) REFERENCES users (id, tenant_id)
INDEX (tenant_id, contact_id, created_at DESC)
```

`s3_key` is a path the backend computes and controls
(`{tenant_id}/{contact_id}/{uuid}-{filename}`) — never accepted from the
client. See §6.

## 5. API contract

All follow `API_CONVENTIONS.md` §2–§5 exactly (envelope, error codes,
`?page=&page_size=`, `?sort=-field`). No new header pattern — the six
headers from Phase 0 (`X-Tenant-Id`/`X-User-Id`/`X-User-Email`/
`X-User-Name`/`X-User-Role`/`X-Request-Id`) already cover every route
below; `bff/src/app.ts`'s existing `requireAuth` + proxy mount at `/api/v1`
needs no changes, only new FastAPI routes behind it.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/contacts` | `409 CONFLICT` with the existing contact's id in `error.details` on an email/phone dedupe hit — not a silent merge, not a second record. Counselor decides whether to open the existing contact or (a later, explicit) force-create. |
| GET | `/api/v1/contacts` | `?search=&lead_source=&owner_id=&sort=` |
| GET/PATCH | `/api/v1/contacts/{id}` | |
| GET | `/api/v1/contacts/{id}/activities` | |
| GET | `/api/v1/pipeline-stages` | Triggers `ensure_default_stages` if empty. |
| PATCH | `/api/v1/pipeline-stages/{id}` | Rename/reorder only. |
| POST | `/api/v1/contacts/{id}/deals` | Create a deal (course + stage) for a contact. |
| GET | `/api/v1/deals` | `?stage_id=&owner_id=&contact_id=` — board view reads this. |
| GET/PATCH | `/api/v1/deals/{id}` | A `stage_id` change here writes the `activities` row. |
| POST | `/api/v1/tasks` | |
| GET | `/api/v1/tasks` | `?assignee_id=&status=&sort=due_at` |
| PATCH | `/api/v1/tasks/{id}` | Complete/reassign/reschedule. |
| POST | `/api/v1/contacts/{id}/documents/upload-url` | Returns a presigned PUT URL scoped to the computed `s3_key` — client uploads directly to S3/MinIO, not through the backend. |
| POST | `/api/v1/contacts/{id}/documents` | Confirms the upload, creates the `documents` row (called after the client's direct PUT succeeds). |
| GET | `/api/v1/contacts/{id}/documents` | |
| GET | `/api/v1/documents/{id}/download-url` | Presigned GET, short-lived. |

## 6. Multi-tenancy check

- Every table above: `tenant_id` + RLS + leading composite index, no
  exceptions (`CLAUDE.md` rules 1–2).
- Every FK is composite `(x_id, tenant_id) → target(id, tenant_id)`, per §4
  — the one new rule this phase adds on top of the Phase 0 pattern.
- **S3 key scoping**: the backend computes `s3_key` from the validated
  `tenant_id` + `contact_id` server-side; the client never supplies or
  influences the key. A presigned URL is scoped to exactly that key, so
  even a leaked URL's blast radius is one document, and a guessed/forged
  key outside the caller's tenant prefix is rejected before a presigned URL
  is ever issued (the `contact_id` ownership check runs through the normal
  RLS-scoped session first).
- Dedupe queries, activity writes, and every list/filter above run through
  the existing `get_tenant_context` dependency (`app/deps/tenant.py`) — no
  new tenant-resolution code path, so Phase 0's defense-in-depth (BFF header
  strip + FastAPI dependency + RLS) covers all of it unchanged.
- No cross-tenant reference is possible through `deal.contact_id` /
  `deal.course_id` / `deal.stage_id` etc. — composite FKs make a
  cross-tenant link a constraint violation at write time, not just an RLS
  block at read time.

## 7. Task breakdown

Ordered, each sized as a reviewable commit — mirrors Phase 0's
one-slice-per-commit discipline (`DEVELOPMENT_PLAN.md` §6).

| # | Commit | Notes |
|---|---|---|
| 1 | Migration: `courses` + `pipeline_stages` | Include `ensure_default_stages` as a backend service function in the same slice as the stages endpoint (step 3), not this migration. |
| 2 | Migration: `contacts` | Partial unique indexes for dedupe in the same migration. |
| 3 | Backend: contacts CRUD + dedupe (409) + search/filter | Unit tests for dedupe logic. |
| 4 | Backend: `pipeline_stages` list/patch + `ensure_default_stages` | |
| 5 | BFF: proxy routes for contacts + pipeline-stages | Thin — no new auth logic, per §3. |
| 6 | Migration: `deals` | |
| 7 | Backend: deals CRUD + stage-transition endpoint | |
| 8 | Migration: `activities` (hash-partitioned) | Exact DDL from `DATABASE_SCHEMA.md` §3, per Phase 0 precedent. |
| 9 | Backend: activity logging on deal stage change | |
| 10 | BFF: proxy routes for deals | |
| 11 | Migration: `tasks` | |
| 12 | Backend + BFF: tasks CRUD | |
| 13 | Migration: `documents` | |
| 14 | Backend: S3/MinIO presigned upload/download flow + documents CRUD | Test the tenant-prefix scoping explicitly (§6). |
| 15 | BFF: proxy routes for documents | |
| 16 | `ux-designer` input: pipeline board interaction, contact form, task list/board | Before frontend build, per `feature-builder` process step 4 — this is the first phase with real counselor-facing UI. |
| 17 | `ui-designer` input: contacts list/detail, pipeline board, task views | Same reasoning. |
| 18 | Frontend: contacts list + detail | |
| 19 | Frontend: pipeline board (drag-drop stage change) | |
| 20 | Frontend: task list/board | |
| 21 | Frontend: document upload | |
| 22 | Tests: cross-tenant rejection for every new resource | Extends the `tests/test_tenant_isolation.py` pattern — direct-ID-guess attempts against contacts/deals/tasks/documents from the wrong tenant. |
| 23 | Docs: correct `DATABASE_SCHEMA.md` §1's `contacts` row (drop `stage`, it's on `deals` now); confirm `API_CONVENTIONS.md` needs no changes. | Per §2's note — fix docs to match what was actually built, same discipline as `DEVELOPMENT_PLAN.md` §15. |

Steps 16–17 (design input) can run in parallel with 6–15 (deals/tasks/
documents backend work) — nothing in the design pass depends on those
endpoints existing yet.

## 8. Acceptance criteria

1. Creating a contact with an email already used by another contact in the
   **same** tenant returns `409 CONFLICT`, with the existing contact's id
   in `error.details`.
2. The same email is **not** rejected when creating a contact in a
   **different** tenant — dedupe is tenant-scoped, not global.
3. A counselor can create a deal for a contact (course + initial stage);
   it appears on the pipeline board grouped under that stage.
4. Changing a deal's `stage_id` writes exactly one `activities` row
   (`deal_stage_changed`, old stage, new stage, actor, timestamp) and
   updates `stage_changed_at`.
5. A counselor in tenant A gets `401`/`404` (never a real record) when
   directly requesting a contact/deal/task/document id that belongs to
   tenant B — including by ID guess, not just via the list endpoints.
6. Assigning a task to a user in a different tenant is rejected (FK
   violation surfaces as `400`/`404`, not a silent cross-tenant link).
7. A counselor can create a task, mark it done, and it drops out of their
   open-tasks list (`?status=open`).
8. A counselor can request an upload URL, upload a file, and confirm it;
   the resulting `documents.s3_key` is prefixed with their own
   `tenant_id`; a counselor in tenant B requesting a download URL for that
   document id gets `404`, never a valid presigned URL.
9. `GET /api/v1/pipeline-stages` for a brand-new tenant with no stages
   returns the seeded defaults (`Inquiry` → … → `Enrolled`, `Dropped`)
   without any manual setup step.
10. Every new endpoint's success and error responses match
    `API_CONVENTIONS.md` §3–§4's envelope shape exactly.
11. Together, 3–8 reproduce `FEATURES_AND_PLAN.md`'s Phase 1 exit
    criterion end to end: a counselor creates a lead, moves it through
    stages, attaches a document, and completes a task.

## 9. Handoff

Start `feature-builder` at §7 step 1. Steps 16–17 (design input) should run
before step 18, not before the backend work — nothing in the backend/BFF
slices needs a mockup. If an implementation detail contradicts this plan —
particularly the composite-FK rule in §4/§6 or the dedupe conflict shape in
§5 — stop and amend the plan rather than diverging silently.
