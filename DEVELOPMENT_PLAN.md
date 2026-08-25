# Development plan — OpenFunnel

Produced by the `feature-planner` skill. **No application code is written by
this document.** Hand to `feature-builder` (or a human reviewer) before
implementation begins.

Repo state at time of writing: documentation only (`ARCHITECTURE.md`,
`FEATURES_AND_PLAN.md`, `DATABASE_SCHEMA.md`, `API_CONVENTIONS.md`,
`CLAUDE.md`, `LICENSE`, `.claude/skills/`). No services, no Dockerfiles, no
migrations, no CI.

---

## 0. Locating the work

The request ("develop the application") spans the entire feature set, not one
feature. Mapping it onto `FEATURES_AND_PLAN.md` §2:

| Phase | Status | Can it be planned now? |
|---|---|---|
| Phase 0 — Foundations | Not started | **Yes** — no prerequisites |
| Phase 1 — Core CRM | Blocked | No — needs Phase 0 exit criteria |
| Phase 2 — Lead capture | Blocked | No |
| Phase 3 — Comms & automation | Blocked | No |
| Phase 4 — Reporting & conversions | Blocked | No |
| Phase 5 — Hardening & single-tenant | Blocked | No |

Per `FEATURES_AND_PLAN.md` §3 and `CLAUDE.md`, Phase N+1 is not planned until
Phase N's exit criteria are met and tested. **Sections 1–8 below are the Phase
0 plan.** Section 9 is a roadmap sketch for Phases 1–5 — deliberately not a
plan, and not to be handed to `feature-builder`.

Nothing in this request falls outside `FEATURES_AND_PLAN.md`, so there is no
ad-hoc work to flag.

---

## 1. Phase 0 scope and exit criteria

Verbatim from `FEATURES_AND_PLAN.md`:

> - **Exit criteria**: a logged-in user in tenant A cannot see tenant B's data,
>   proven with an automated test; `docker compose up` brings up the full stack
>   from a clean checkout with no manual steps.

Everything below exists to serve those two sentences. Phase 0 ships **no CRM
features** — no contacts, no pipeline, no tasks. It ships the tenant-isolation
harness that every later feature inherits, plus the local-to-AWS module
mapping so it isn't retrofitted.

**In scope**
- Six-service Docker Compose stack (`web`, `bff`, `backend`, `db`, `redis`,
  `keycloak`; `minio` behind an optional profile)
- One Dockerfile per shippable module (`frontend`, `bff`, `backend`)
- `tenants` + `users` tables, with the RLS pattern proven end to end
- Keycloak realm auto-import: realm, client, `tenant_id` claim mapper, roles,
  two seed tenants with seed users
- Auth chain: React → Keycloak (Auth Code + PKCE) → BFF (JWKS validation) →
  FastAPI (`X-Tenant-Id`) → Postgres (`app.tenant_id`)
- GitHub Actions CI: lint + test for all three services, plus the isolation test
- Skeleton Helm charts in `/deploy/helm`

**Explicitly out of scope for Phase 0**
- Any `contacts`/`pipeline_stages`/`tasks`/`documents` table or endpoint
- Celery workers (directory `/backend/app/workers` is created; no tasks yet)
- Real rate limiting (middleware seam only — Phase 5 tunes it)
- PgBouncer (not run locally; the `SET LOCAL` convention below keeps it safe
  to add later without a code change)
- Any UI beyond a login-gated shell that renders the current user and tenant

---

## 2. Affected layers

| Layer | Touched | Changes |
|---|---|---|
| **Frontend** (`/frontend`) | Yes | New Vite + React + TS (strict) app. `keycloak-js` Auth Code + PKCE. Auth context, protected-route wrapper, silent token refresh, `Authorization: Bearer` on every BFF call. One shell page rendering `/api/v1/me`. Dockerfile (dev server + multi-stage static build). |
| **BFF** (`/bff`) | Yes | New Express + TS (strict) service. Middleware chain: request-id → JWKS token validation → tenant/user resolution → rate-limit seam → proxy. Forwards `X-Tenant-Id`, `X-User-Id`, `X-Request-Id`. Maps upstream errors to the `API_CONVENTIONS.md` envelope. Redis client for JWKS/decision cache. Dockerfile. |
| **Backend** (`/backend`) | Yes | New FastAPI + SQLAlchemy 2.x app. Tenant-context dependency (rejects missing/invalid `X-Tenant-Id` with `401` before any query), per-transaction `SET LOCAL app.tenant_id`, structured logging, envelope + error handlers, `/health`, `/ready`, `/api/v1/me`. Dockerfile. |
| **Database** (`/db`) | Yes | Alembic initialised. One migration: `tenants` (global) + `users` (tenant-scoped, RLS + composite index). Roles `crm_migrate` / `crm_app`. Idempotent seed script for the two test tenants. |
| **Background jobs** | Structurally only | `/backend/app/workers` package + Celery app configured against `REDIS_URL`; no tasks, no worker container in Phase 0. Deferred to Phase 3. |
| **Keycloak** (`/keycloak`) | Yes | `realm-export.json` auto-imported on start: realm, public web client (PKCE S256), `tenant_id` user-attribute → claim mapper, realm roles `admin`/`manager`/`counselor`, seed users for tenant A and tenant B. |
| **Deploy** (`/deploy/helm`) | Yes | Skeleton charts for `web`, `bff`, `backend`, `keycloak`. Deployment/Service/Ingress/ConfigMap/Secret-ref templates, image repo+tag values, no cluster deploy in Phase 0. |
| **CI** (`/.github/workflows`) | Yes | Per-service lint + test jobs, image build jobs, one compose-based tenant-isolation job. |

---

## 3. Database changes

Both tables follow `DATABASE_SCHEMA.md` §2. `tenants` is the one documented
exemption from the `tenant_id` rule (`DATABASE_SCHEMA.md` §1 — global table).

### 3.1 `tenants` — global, no RLS

```sql
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,   -- subdomain / Keycloak attribute value
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'suspended')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Deliberately exempt from RLS per `CLAUDE.md` rule 1 (platform-level table).
Reachable only by the tenant-resolution path and admin tooling — never by a
tenant-scoped request handler.

### 3.2 `users` — tenant-scoped, standard pattern

```sql
CREATE TABLE users (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    keycloak_sub  TEXT NOT NULL,
    email         TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL
                  CHECK (role IN ('admin', 'manager', 'counselor')),
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'disabled')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
);

CREATE INDEX idx_users_tenant_role
    ON users (tenant_id, role, created_at DESC);

CREATE UNIQUE INDEX uq_users_tenant_keycloak_sub
    ON users (tenant_id, keycloak_sub);

CREATE UNIQUE INDEX uq_users_tenant_email
    ON users (tenant_id, lower(email));

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_users ON users
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

All three indexes lead with `tenant_id` (`CLAUDE.md` rule 2). Uniqueness is
per-tenant, not global — the same person may exist in two tenants.

### 3.3 Session context

Per `DATABASE_SCHEMA.md` §4, use the **`SET LOCAL` / transaction-scoped** form
from day one, even though PgBouncer isn't in the local stack:

```sql
SET LOCAL app.tenant_id = :tenant_id;
```

Wrap every request in an explicit transaction; set the variable as the first
statement. Adding PgBouncer in transaction-pooling mode later then becomes a
config change, not a code change.

Note the policy uses the strict two-arg-free `current_setting(...)`, which
**raises** when the variable is unset rather than returning NULL. That is the
desired fail-loud behaviour: a query that escapes the tenant-context dependency
errors instead of silently returning zero rows. `feature-builder` must not
"fix" this by switching to `current_setting('app.tenant_id', true)`.

### 3.4 Database roles — the FORCE RLS gotcha

`FORCE ROW LEVEL SECURITY` applies policies to the **table owner too**. Two
roles, and the seed script must account for this:

- `crm_migrate` — owns the tables, runs Alembic. DDL is unaffected by RLS, but
  any `INSERT`/`UPDATE` it does (seeds) **is** subject to the policy.
- `crm_app` — the runtime role used by FastAPI. `SELECT/INSERT/UPDATE/DELETE`
  grants only. Must **not** have `BYPASSRLS` and must not be superuser —
  CI asserts this.

Seeding cross-tenant rows therefore sets `app.tenant_id` per tenant before
inserting that tenant's users, rather than inserting all rows in one shot.
This is a real trap and the most likely source of a confusing early failure.

### 3.5 Migration policy

Single Alembic revision creating both tables *with* their RLS policy and
indexes in the same migration (`DATABASE_SCHEMA.md` §5). Roles/grants live in
a separate bootstrap migration that runs first, so the same DDL works against
RDS where role creation may be handled out of band.

---

## 4. API contract

Response envelope, error codes, and pagination per `API_CONVENTIONS.md` §3–§5.
Phase 0 adds no collection endpoints, so pagination is implemented in the
shared helper but not yet exercised by a route.

### 4.1 FastAPI

| Method | Path | Tenant required | Purpose |
|---|---|---|---|
| GET | `/health` | **No** | Liveness — process is up. No DB touch. |
| GET | `/ready` | **No** | Readiness — DB and Redis reachable. |
| GET | `/api/v1/me` | Yes | Current user + tenant. |

`/health` and `/ready` are the **only** exemptions from `CLAUDE.md` rule 3.
They are unauthenticated, do no tenant-scoped query, and return no tenant data.
They must be declared as an explicit allowlist in the tenant-context middleware,
not by forgetting to add the dependency — so a new route is tenant-guarded by
default and a future exemption is a visible diff.

**`GET /api/v1/me` → 200**

```json
{
  "data": {
    "user": {
      "id": "b1c9...",
      "email": "counselor.a@example.test",
      "full_name": "Asha Rao",
      "role": "counselor",
      "status": "active"
    },
    "tenant": {
      "id": "9f2e...",
      "slug": "tenant-a",
      "name": "Future Digital Inc"
    }
  },
  "meta": { "request_id": "01J..." }
}
```

**Errors** (`API_CONVENTIONS.md` §4): missing/unparseable `X-Tenant-Id` →
`401 UNAUTHORIZED`; `X-Tenant-Id` not a known active tenant → `401
UNAUTHORIZED` (not `404` — do not let a caller probe which tenant UUIDs exist);
tenant valid but the user row can't be resolved → `403 FORBIDDEN`.

### 4.2 BFF

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness for k8s probes. |
| GET | `/api/v1/me` | Validate token, resolve tenant, proxy to FastAPI. |

Middleware order is load-bearing:

1. **Request ID** — generate `X-Request-Id` (accept an inbound one only from a
   trusted ingress, never from the browser).
2. **Token validation** — verify the Keycloak access token against JWKS
   (cached, with `kid` rotation), checking signature, `iss`, `aud`, `exp`.
3. **Tenant/user resolution** — read `tenant_id` and `sub` **from the validated
   token claims only**. Reject if `tenant_id` is absent. Never read a tenant
   hint from body, query, or an inbound header (`CLAUDE.md` rule 7).
4. **Rate-limit seam** — Redis-keyed by `tenant_id`, permissive default in
   Phase 0, tuned in Phase 5.
5. **Proxy** — forward with `X-Tenant-Id`, `X-User-Id`, `X-Request-Id`, and
   **strip any client-supplied copies of those three headers before setting
   them**. This is the single most important line of code in Phase 0.

### 4.3 `X-User-Id` semantics — decision

`ARCHITECTURE.md` §4 says "acting user UUID" without saying whose UUID.
**Decision: `X-User-Id` carries the Keycloak `sub`** (a UUID), and FastAPI
resolves the `users` row via `(tenant_id, keycloak_sub)`. The alternative —
BFF looking up our internal `users.id` — would force the BFF to query Postgres,
which contradicts "FastAPI owns business logic and data access." Recorded here
so it isn't re-litigated during implementation.

### 4.4 User provisioning — decision

Keycloak is the source of truth for identity; `users` is the source of truth
for CRM-side attribution (ownership, assignment). **Decision: JIT upsert** —
on `/api/v1/me`, upsert `users` on `(tenant_id, keycloak_sub)` from the
forwarded context, taking `role` from the token's role claim. No admin invite
flow in Phase 0; the tenant admin console is Phase 1+ work. `tenant_id` for
the upsert comes only from the validated header, never from a payload.

---

## 5. Multi-tenancy check

Against `ARCHITECTURE.md` §4 and `CLAUDE.md` rules 1–8:

| Rule | Phase 0 compliance |
|---|---|
| 1 — `tenant_id` + RLS on every table | `users` complies. `tenants` is the documented global exemption. |
| 2 — indexes lead with `tenant_id` | All three `users` indexes do. |
| 3 — every endpoint validates `X-Tenant-Id` | Enforced by a default-on dependency; `/health` and `/ready` are an explicit, reviewed allowlist. |
| 4 — BFF is the only layer touching the browser session | FastAPI reads no cookies; it has no cookie parser wired at all. |
| 5 — no PII/secrets in logs | Structured logger emits `tenant_id`, `user_id`, `request_id`, route, status, duration. A CI grep asserts no `email`/`token`/`authorization` key reaches a log call. |
| 6 — jobs carry tenant context explicitly | No jobs in Phase 0; the Celery base-task signature reserves a required `tenant_id` first parameter so Phase 3 can't forget. |
| 7 — `tenant_id` only from a validated Keycloak token | BFF derives it from validated claims and strips inbound copies of the three forwarded headers. |
| 8 — stateful containers are dev-only | `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`, `KEYCLOAK_ISSUER_URL` all read from env. CI greps for hardcoded `localhost`/`db`/`redis` hostnames in app code. |

**Defence in depth.** Three independent layers must each fail before a
cross-tenant read is possible: the BFF would have to forward the wrong
`X-Tenant-Id`, *and* the FastAPI dependency would have to set the wrong
`app.tenant_id`, *and* the RLS policy would have to not match. Phase 0's job is
to make all three real and test the innermost one directly at the DB level, not
only through HTTP.

**Single-tenant deployments.** Identical code and identical DDL
(`ARCHITECTURE.md` §7 tier 3). `tenant_id`/RLS stay in place though isolation
is physical. Nothing in Phase 0 branches on deployment mode.

---

## 6. Task breakdown

Ordered; each is one reviewable commit. Steps 2–4 follow `feature-builder`'s
database-first process.

| # | Commit | Notes |
|---|---|---|
| 1 | Repo scaffolding | `.gitignore`, `.editorconfig`, `.env.example` (every var from §7), top-level `README` quickstart. No service code. |
| 2 | Backend skeleton + Dockerfile | FastAPI app factory, settings from env (pydantic-settings), `ruff` + `pytest` configured, `/health`. |
| 3 | DB bootstrap migration | `crm_migrate`/`crm_app` roles, grants, `pgcrypto`. Assert `crm_app` lacks `BYPASSRLS`. |
| 4 | `tenants` + `users` migration | Tables, indexes, RLS enable + force + policy, per §3. Plus a pytest that hits the DB directly, no HTTP. |
| 5 | Tenant-context dependency + envelope | `SET LOCAL app.tenant_id` per transaction, `401` on missing header, envelope/error handlers, structured logging, `/ready`. |
| 6 | `GET /api/v1/me` + JIT upsert | Per §4.4. Unit tests for the service layer. |
| 7 | Keycloak realm export + compose service | Realm, PKCE client, `tenant_id` mapper, roles, seed users for tenants A and B. Auto-import verified from a clean volume. |
| 8 | BFF skeleton + Dockerfile | Express + TS strict, request-id, `/healthz`, error envelope. |
| 9 | BFF auth middleware | JWKS validation w/ cache + rotation, claim extraction, **inbound header stripping**, proxy `/api/v1/me`. Tests: expired token, wrong `aud`, absent `tenant_id` claim, forged `X-Tenant-Id` header. |
| 10 | Frontend skeleton + Dockerfile | Vite + React + TS strict, `keycloak-js` PKCE, auth context, protected route, shell rendering `/api/v1/me`. |
| 11 | `docker-compose.yml` + seed | All services wired, healthchecks and `depends_on: condition: service_healthy`, `minio` behind a profile. Idempotent seed for tenants A/B (respecting §3.4). |
| 12 | Tenant-isolation integration test | The exit-criteria test — see §7. |
| 13 | CI workflows | Per-service lint/test, image builds, compose-based isolation job, the rule-5 and rule-8 grep checks. |
| 14 | Helm chart skeletons | `/deploy/helm/{web,bff,backend,keycloak}`, `helm lint` + `helm template` in CI. No cluster deploy. |
| 15 | Docs update | Fill in `CLAUDE.md` "Commands" with the real, verified commands. Confirm `DATABASE_SCHEMA.md` §1 still accurate. |

Steps 8–9 (BFF) and 10 (frontend) can run in parallel with 5–6 once the
FastAPI contract from §4 is fixed.

---

## 7. Acceptance criteria

Phase 0 is done when all of these pass in CI on a clean checkout.

**Tenant isolation — the exit criterion**

1. Seeded with tenant A (user `counselor.a`) and tenant B (user `counselor.b`),
   each with one `users` row: a `GET /api/v1/me` with A's Keycloak token returns
   A's user and A's tenant, and never any field belonging to B.
2. With `app.tenant_id` set to tenant A, `SELECT count(*) FROM users` executed
   as `crm_app` returns exactly A's user count — asserted **directly against
   Postgres**, bypassing HTTP.
3. With `app.tenant_id` set to tenant A, `UPDATE users SET full_name = 'x'`
   affects **0** rows belonging to tenant B.
4. With `app.tenant_id` set to tenant A, inserting a `users` row with tenant B's
   `tenant_id` is **rejected** by the `WITH CHECK` clause.
5. A query run as `crm_app` with **no** `app.tenant_id` set **raises** rather
   than returning rows.
6. A request carrying A's valid token plus a hand-forged `X-Tenant-Id: <B>`
   header returns **A's** data — the BFF stripped and replaced the header.
7. A request to `/api/v1/me` with no token → `401` with body
   `{"error": {"code": "UNAUTHORIZED", ...}}`, and no DB connection is opened.
8. A request with a well-formed token signed by the wrong key → `401`.
9. A token whose claims omit `tenant_id` → `401`, not a 500 and not a fallback
   to a default tenant.
10. `crm_app` has neither superuser nor `BYPASSRLS` — asserted by a query
    against `pg_roles`.

**Clean-checkout startup**

11. From `git clone` with only `cp .env.example .env`, `docker compose up`
    reaches all-healthy with **zero** manual steps — no Keycloak console
    clicks, no manual migration command, no manually created realm or user.
12. Browsing to the web app redirects to Keycloak, login as `counselor.a`
    succeeds, and the shell renders "Asha Rao — Future Digital Inc" sourced from
    `/api/v1/me`.
13. `docker compose down -v && docker compose up` reproduces 11–12 identically
    from empty volumes.

**Conventions and CI**

14. Every response — success and error — matches the `API_CONVENTIONS.md`
    envelope, and `meta.request_id` on the HTTP response equals the
    `request_id` on the corresponding BFF and FastAPI log lines for that call.
15. `npm run lint`/`npm run test` (frontend, bff) and `ruff check .`/`pytest`
    (backend) all pass in CI.
16. No email address, phone number, token, or `Authorization` value appears in
    any log line, asserted by a test that captures log output during an
    authenticated request.
17. No application source file contains a hardcoded `localhost`, `db`, or
    `redis` hostname (grep check) — all connections come from env vars.
18. `helm lint` and `helm template` succeed for all four charts.
19. All three images build from a clean context in CI.

**Environment variables** to appear in `.env.example`, Compose, and Helm values:
`DATABASE_URL`, `REDIS_URL`, `KEYCLOAK_ISSUER_URL`, `KEYCLOAK_REALM`,
`KEYCLOAK_CLIENT_ID`, `KEYCLOAK_JWKS_URL`, `BACKEND_BASE_URL`, `BFF_BASE_URL`,
`S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `LOG_LEVEL`,
`ENVIRONMENT`. No secret is committed; `.env` is gitignored.

---

## 8. Decisions taken, and open questions

**Resolved from existing docs — implement as stated, do not re-open:**

- **Vite, not Next.js.** `ARCHITECTURE.md` §2 allows either; `CLAUDE.md`'s repo
  structure specifies "React + TypeScript (Vite)". Vite wins; no SSR need in
  Phase 0. Directory is `/frontend`, Compose service name is `web`
  (`ARCHITECTURE.md` §5) — the mismatch is intentional, keep both.
- **Celery, not BullMQ.** `ARCHITECTURE.md` §2 allows either; `CLAUDE.md`'s repo
  structure specifies `/backend/app/workers` for Celery tasks.
- **GitHub Actions** for CI — `origin` is GitHub.
- **Postgres FTS** for search when Phase 1 needs it; Elasticsearch only if
  scale demands (`ARCHITECTURE.md` §2).

**Open — worth a human answer, but none blocks starting Phase 0:**

- **`deals` table.** `DATABASE_SCHEMA.md` marks it optional ("if a contact can
  have multiple concurrent applications/courses"). A Phase 1 question; the
  answer materially changes the contacts/pipeline model, so decide before
  planning Phase 1, not during it.
- **Keycloak `tenant_id` as user attribute vs. group-per-tenant.**
  `ARCHITECTURE.md` §4 permits both for pooled tenants. Phase 0 uses the user
  attribute (simplest mapper). Revisit only if tenant-scoped role management
  gets awkward.
- **Tenant onboarding.** Nothing in Phase 0 creates a tenant outside the seed
  script. A real signup/provisioning flow (Keycloak user + `tenants` row
  together) is unplanned in `FEATURES_AND_PLAN.md` — flagging it as a gap in
  the phase plan itself, likely Phase 1 admin-console work.
- **Audit log.** Listed under Platform features with no phase assigned. If
  audit coverage must include Phase 1 writes, the table needs to exist before
  Phase 1 code, not after.

---

## 9. Roadmap for Phases 1–5 (sketch, not a plan)

Not for `feature-builder`. Each entry lists only its entry condition and the
architectural question to resolve when the phase is planned properly.

**Phase 1 — Core CRM.** *Entry: Phase 0 §7 all green.* Plan then:
`contacts`, `pipeline_stages`, `courses`, `tasks`, `documents`, and the
`deals` yes/no decision. Every table repeats §3.2's pattern. Real questions:
dedupe strategy on create (exact email/phone vs. fuzzy), whether stage
transitions write to `activities` from day one, and S3/MinIO presigned-upload
flow. `ux-designer` and `ui-designer` are needed here — this is the first
phase with a real counselor-facing surface.

**Phase 2 — Lead capture.** *Entry: Phase 1 exit criteria met.* Each external
integration is a `CLAUDE.md` "ask first" item (new API keys) and must go
through the `architect` skill before planning. Real questions: public
unauthenticated ingest endpoints need tenant resolution without a Keycloak
token — a signed per-tenant form key, resolved server-side, is the likely
shape and must be designed, not improvised. Redis idempotency keys per
`API_CONVENTIONS.md` §7.

**Phase 3 — Communication & automation.** *Entry: Phase 2 exit criteria met.*
First real Celery work; `CLAUDE.md` rule 6 (explicit tenant context per job)
becomes live and must be enforced at the base-task signature. `workflow_rules`
+ `workflow_runs` (the latter hash-partitioned per `DATABASE_SCHEMA.md` §3).
WhatsApp/email providers → `architect` first.

**Phase 4 — Reporting & conversion feedback.** *Entry: Phase 3 exit criteria
met.* Aggregate read paths with Redis caching and write invalidation
(`ARCHITECTURE.md` §8). Outbound conversion APIs → `architect` first. The
`dataviz` skill applies to every dashboard surface here.

**Phase 5 — Hardening & single-tenant packaging.** *Entry: Phase 4 exit
criteria met.* Convert `activities`/`workflow_runs` to hash partitions (cheap
because `tenant_id` is already in every PK), real per-tenant rate limits,
first EKS deploy from the Phase 0 Helm charts, skewed-tenant load test.

---

## 10. Handoff

Start `feature-builder` at §6 step 1 and proceed in order. Do not begin any
Phase 1 table or endpoint until every item in §7 passes in CI. If an
implementation detail contradicts this plan, stop and amend the plan rather
than diverging silently — particularly anything touching §3 (schema/RLS) or
§4.2 (header handling).
