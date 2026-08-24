# EdTech CRM — Architecture

## 1. Overview

A cloud-native, multi-tenant CRM for EdTech admissions teams: lead capture from
Meta/Google/web/WhatsApp, pipeline management, workflow automation, reporting
and forecasting. Ships as a pooled SaaS product by default, with the same
Docker images deployable as a single-tenant instance in a client's own VPC.

## 2. Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React (Vite or Next.js) + TypeScript | Counselor dashboard, admin console |
| BFF | Node.js + Express (TypeScript) | Auth session handling, request shaping, tenant resolution |
| Backend API | Python + FastAPI | Core business logic, integrations, workflow engine |
| Database | PostgreSQL 16+ | Multi-tenant, RLS + partitioning (see DATABASE_SCHEMA.md) |
| Cache / queue | Redis | Session cache, rate limiting, BullMQ/RQ job queues |
| Object storage | S3-compatible (AWS S3 or MinIO for self-host) | Documents, attachments |
| Background jobs | Celery (Python) or BullMQ (Node), backed by Redis | Workflow triggers, email/WhatsApp sends, conversion sync |
| Search | Postgres full-text to start; Elasticsearch/OpenSearch if scale demands | Lead/contact search |
| Identity & auth | Keycloak (OIDC) | Login, token issuance, tenant claim mapping — see Section 4 |
| Containerization | Docker + Docker Compose (local), Kubernetes/Helm (prod) | Same images for SaaS and single-tenant |

## 3. Why a BFF between React and FastAPI

- Keeps browser-facing auth (cookies, CSRF, session refresh) in Node/Express,
  separate from the Python service that owns business logic.
- Lets the frontend talk one consistent API shape even if FastAPI endpoints
  change or get versioned underneath.
- Central point to resolve **tenant context** (from subdomain, JWT claim, or
  custom domain mapping) once, then forward it to FastAPI on every request as
  a header (`X-Tenant-Id`) — FastAPI never has to guess tenant identity from
  the frontend.
- Good place for response aggregation if a dashboard view needs data from
  multiple FastAPI endpoints in one round trip.

If the team later decides the BFF is unnecessary overhead, React can call
FastAPI directly — but keep tenant-resolution and auth-token logic isolated in
one module so that change stays contained.

## 4. Auth flow and request flow

Keycloak is the identity provider. React authenticates against Keycloak
directly (Authorization Code flow + PKCE, via `keycloak-js` or an
OIDC client library) rather than the BFF owning username/password handling.

- Keycloak issues the access token (JWT) and refresh token.
- The access token carries `sub` (user id), `realm`/custom attribute for
  `tenant_id`, and role claims.
- React sends the Keycloak access token to the BFF on every call; the BFF
  validates it against Keycloak (JWKS endpoint), extracts `tenant_id` and
  `user_id`, and forwards them to FastAPI as headers — FastAPI itself never
  talks to Keycloak directly, it trusts the BFF's forwarded, already-validated
  context.

**Tenant identity in Keycloak** — mirrors the same tiering used for the
database:
- **Pooled SaaS tenants**: a single Keycloak realm, with `tenant_id` stored
  as a custom user attribute (or a client role/group per tenant). Simpler to
  operate, matches the shared-Postgres-with-RLS model.
- **Isolated / single-tenant deployments**: a dedicated Keycloak realm (or a
  dedicated Keycloak instance entirely) per client, consistent with their
  dedicated database.

```
Browser (React)
   -> Keycloak                 login, issues access + refresh token (OIDC)
   -> BFF (Express)             validates token against Keycloak JWKS,
                                  resolves tenant_id + user_id
      -> FastAPI                receives X-Tenant-Id + X-User-Id + X-Request-Id
         -> sets Postgres session var app.tenant_id (RLS scopes all queries)
         -> reads/writes Postgres, reads/writes Redis
         -> enqueues background jobs (workflow triggers, sends)
      <- JSON response
   <- shaped response
<- rendered UI
```

## 5. Local development environment

Everything runs in Docker Compose as separate modules/services:

| Service | Image / base | Role |
|---|---|---|
| `web` | Node (React build/dev server) | Frontend, hot-reloaded in dev |
| `bff` | Node (Express) | Auth token validation, tenant resolution, request shaping |
| `backend` | Python (FastAPI) | Core business logic, integrations, workflow engine |
| `db` | `postgres:16` | Primary datastore |
| `redis` | `redis:7` | Cache, queues, idempotency keys |
| `keycloak` | `quay.io/keycloak/keycloak` | Identity provider, OIDC |
| `minio` (optional) | `minio/minio` | Local S3-compatible object storage for documents |
| `mock-integrations` | Python (FastAPI) | Dev/test-only stand-in for the Meta Graph API, WhatsApp Cloud API, and Google Ads API — never deployed in production, same annotation as `minio` above. Part of the default stack (unlike `minio`'s opt-in `storage` profile): Phase 2's lead-capture pipelines can't be exercised locally at all without it. See §7a |
| `worker` | Python (Celery) | Executes queued/scheduled tasks — SLA state computation, workflow rule evaluation. Same `backend` image, `celery worker` as the container command instead of `uvicorn`; `docker-entrypoint.sh` is bypassed (no reason to re-run migrations/seed a second time). See §7c |
| `beat` | Python (Celery) | Fires the periodic dispatchers on a schedule (`celery beat`) — same image as `worker`, different command. Nothing here executes tasks itself, it only enqueues them for `worker` to pick up |

Each service is its own Dockerfile/module so it can be built, tested, and
shipped independently — the same images used in `docker compose up` locally
are what get pushed to a registry and deployed to Kubernetes, not
dev-only containers rebuilt for production.

Keycloak realm/client configuration (realm export JSON) should be checked
into the repo (e.g., `/keycloak/realm-export.json`) and auto-imported on
container start, so a fresh `docker compose up` gives a fully working login
without manual Keycloak console setup.

## 6. Path to production (AWS EKS)

The local module boundaries map directly to Kubernetes workloads — this is
the reason each piece is a separate service locally rather than a combined
container:

| Local (Docker Compose) | AWS production |
|---|---|
| `web` | Static build served via S3 + CloudFront, or a Deployment behind the ingress if SSR is needed |
| `bff` | Deployment + Service in EKS, behind ALB Ingress |
| `backend` | Deployment + Service in EKS, behind ALB Ingress. `/api/v1/*` stays internal-only (reachable only from `bff`); `/webhooks/*` additionally needs a **public** ingress path — the same Docker image, just a second, differently-exposed route on the same ALB — since Meta/WhatsApp/Google call it directly and never go through the BFF (§7a, `PHASE_2_PLAN.md` §4.2) |
| `db` | Amazon RDS for PostgreSQL (Multi-AZ) — not run in-cluster |
| `redis` | Amazon ElastiCache for Redis — not run in-cluster |
| `keycloak` | Deployment + Service in EKS (or AWS-managed alternative, e.g. Cognito, if the team later chooses to swap it — realm-based design keeps this optional) |
| `minio` | Amazon S3 — not run in-cluster in production |
| `mock-integrations` | **Not deployed** — production `backend` talks to the real Meta Graph API, WhatsApp Cloud API, and Google Ads API directly (`META_GRAPH_API_BASE_URL`/`WHATSAPP_API_BASE_URL`/`GOOGLE_ADS_API_BASE_URL` point at the real platforms, not at this service — same config-swap principle as `S3_ENDPOINT`/MinIO) |
| `worker` / `beat` | Deployment (`worker`, horizontally scalable) + a single-replica Deployment (`beat` — running it more than once would fire every scheduled task multiple times) in EKS. Same `backend` image and ECR repo as the API Deployment, just a different container command per Deployment spec |

Practical implications for how the repo should be structured:

- **Each module gets its own Dockerfile** (`/frontend/Dockerfile`,
  `/bff/Dockerfile`, `/backend/Dockerfile`) — these are the exact images
  built in CI and pushed to Amazon ECR, referenced by the Helm charts.
- **Stateful services (`db`, `redis`, `minio`) are dev-only containers.**
  Application code must only ever talk to them via connection strings/env
  vars — never assume they're reachable at a fixed local hostname, so
  swapping to RDS/ElastiCache/S3 in production is a config change, not a
  code change.
- **Helm charts live in `/deploy/helm`**, one chart (or subchart) per
  deployable module (`web`, `bff`, `backend`, `keycloak`), parameterized so
  the same chart deploys either the pooled SaaS cluster or a single-tenant
  cluster in a client's AWS account — only `values.yaml` changes.
- **Secrets** (DB credentials, Keycloak admin, S3 keys) are environment
  variables locally (`.env`, gitignored) and Kubernetes Secrets / AWS Secrets
  Manager in production — never hardcoded, never committed.

## 7. Multi-tenancy strategy

Three tiers, same application code throughout:

1. **Pooled SaaS tenants (default)** — shared Postgres tables, `tenant_id` on
   every row, Row-Level Security enforced at the database level, composite
   indexes leading with `tenant_id`.
2. **Higher-volume pooled tenants** — same shared schema, but high-write
   tables (activities, communication logs) are hash-partitioned by
   `tenant_id` to bound table size and keep autovacuum/index maintenance
   predictable.
3. **Isolated / single-tenant (client VPC)** — same Docker images and same
   table DDL, deployed against a dedicated database. `tenant_id` columns and
   RLS policies are irrelevant here (isolation is physical) but are left in
   place so the schema stays identical across both deployment modes —
   simplifies migrations and avoids code branching.

See `DATABASE_SCHEMA.md` for the concrete DDL pattern.

## 7a. Lead-capture connectors and dev-data seeding

The Phase 2 integrations in Section 1 (Meta/Google/web/WhatsApp lead
capture) share one interface, defined now so sample data can exercise it
before the real integrations exist: `LeadConnector`
(`backend/app/connectors/base.py`) — a `source` plus
`fetch_raw_leads() -> list[RawLead]` — with a `normalize()` step that maps
a platform-shaped payload into a `RawLead`.

Today, every connector is a `SeedFileConnector`: `fetch_raw_leads` reads a
checked-in JSON file (`backend/app/connectors/seed_data/`) shaped like
that platform's actual payload (Meta's `field_data` array, Google's
`userColumnData`, WhatsApp's `wa_id`/no-email shape) instead of calling a
live API. `backend/app/connectors/ingestion_service.py` writes each lead
through the same service-layer functions (`contact_service`,
`deal_service`, dedupe included) a real HTTP request uses — connectors
never get a shortcut write path. Idempotency is a Redis key per
`(tenant_id, source, external_id)`, the same mechanism `API_CONVENTIONS.md`
§7 specifies for real webhook redelivery.

Swapping a source to the real Phase 2 integration means overriding that
connector's `fetch_raw_leads` (a Graph API call, a Google Ads pull, a
WhatsApp webhook handler) — `normalize()`'s contract and everything
downstream stay the same.

This only runs in local dev (`docker-entrypoint.sh`'s
`ENVIRONMENT=development` gate, after tenant seeding) — never in a real
deployment. See `keycloak/README.md` for why the dev seed users' Keycloak
`id` is pinned rather than left to generate: it lets
`backend/app/db/seed.py` pre-provision matching `users` rows (so seeded
leads have a real counselor to round-robin-assign to before anyone has
logged in) without creating a duplicate when that person logs in for
real.

## 7b. Phase 2 lead-capture pipelines (Meta, Google, WhatsApp, web)

`PHASE_2_PLAN.md` implements the real integrations §7a's connector
interface anticipated: Meta Lead Ads and WhatsApp Cloud API are inbound
webhooks (`POST /webhooks/meta`, `POST /webhooks/whatsapp`), Google Ads
is an admin-triggered pull (`POST /api/v1/lead-source-connections/{id}/sync`
— no background-job infra exists yet to poll it automatically, an
explicit boundary), and the web form is a public capture endpoint
(`POST /webhooks/web`). All four write through the exact same
`contact_service`/`deal_service`/`activity_service` functions §7a's
seed connectors already established.

The `/webhooks/*` routes bypass the BFF entirely — Meta/WhatsApp/Google
call `backend` directly, never through a browser session, so
`CLAUDE.md` rule 4 (BFF owns the browser's auth session) doesn't apply
to them. `tenant_id` for an inbound webhook is resolved via
`lead_source_connections`, a table admins populate ahead of time
through the normal Keycloak+BFF-authenticated `/api/v1` routes
(`require_admin`-gated, `REQUIREMENTS.md` §1.2) — never trusted from the
webhook payload itself (`CLAUDE.md` rule 7). This table is a second
documented global RLS exemption alongside `tenants` — see
`DATABASE_SCHEMA.md` §1.

Every platform base URL (`META_GRAPH_API_BASE_URL`,
`WHATSAPP_API_BASE_URL`, `GOOGLE_ADS_API_BASE_URL`) defaults to the
local `mock-integrations` service (§5) and is swapped to the real
platform via config only, the same principle as `S3_ENDPOINT`/MinIO —
this is what let Phase 2 be built and fully tested before any real
platform credentials existed. Per-tenant Meta/Google/WhatsApp tokens are
encrypted at rest (`pgcrypto` `pgp_sym_encrypt`, keyed by
`INTEGRATION_CREDENTIALS_KEY`).

## 7c. Celery: SLA computation and the workflow rule engine

`PHASE_3_PLAN.md` is the first real use of the `/backend/app/workers`
package `DEVELOPMENT_PLAN.md` §0/§8 reserved back in Phase 0 ("Celery,
not BullMQ" — already decided there, not re-opened). Redis (§8) doubles
as broker and result backend; no new stateful service.

Two Beat-scheduled dispatchers run every 5 minutes, each fanning out
**one task per active tenant** rather than looping over every tenant in
a single task — a slow or failing tenant's computation can't delay or
break another's:

- `compute_sla_states` — walks each tenant's active `sla_policies`
  against current deals/tasks, using a tenant-configured business-hours
  clock (`tenant_sla_settings`) rather than raw wall-clock time. A fresh
  transition into `breached` raises exactly one `sla_breach` escalation,
  assigned to the deal/task owner's manager (`users.manager_id`) — a
  breached item with no manager on file logs a warning and is skipped,
  not silently escalated to nobody.
- `scan_time_based_rules` — evaluates `elapsed_time`/`task_overdue`
  workflow rules against matching deals/tasks.

Event-triggered workflow rules (`stage_changed`, `lead_created`) are
enqueued directly from their write path — the deal stage-change route
and Phase 2's lead-ingestion paths (both the real webhook path and the
dev-seed path) — right after that transaction commits, not queued from
inside it.

Every rule executes in its own short transaction against its own
session, one rule at a time — never several rules sharing one
transaction for the same trigger event. Retries are a local loop within
one rule's handling (up to 3 attempts) rather than Celery's own
task-level retry, which would re-run every other rule in the same batch
alongside the one that actually failed. An action forced to raise on
every attempt ends in exactly one `workflow_failure` escalation, not
one per attempt.

`workflow_rules.actions`/`conditions`/`trigger_config` are tenant-scoped
JSONB, validated at write time but never used to build a raw SQL query
— action execution dispatches on a fixed Python type enum. A
`send_message` action is accepted by the schema (so the comms-provider
work, still `architect`-blocked per `CLAUDE.md`'s rule on new external
integrations, doesn't need a later migration) but always records
`workflow_runs.status = 'skipped_unavailable'` rather than silently
succeeding.

## 7d. Outbound conversion signals (Meta Conversions API, Google offline conversions)

Built (`PHASE_4B_CONVERSIONS_PLAN.md`), completing Phase 4's remaining
exit-criteria clause. Originally deferred out of Phase 4's initial build
as a new-external-integration per `CLAUDE.md`'s "what to ask about" list
(`PHASE_4_PLAN.md` line 15); this section records the design decision
made before implementation started.

**No new service, no new credential store.** This reuses §7b's pattern
end to end rather than inventing a second one: `mock-integrations` gains
two new local-only routes simulating the real Conversions/offline-
conversions APIs (same service, same "never deployed in production"
annotation as its existing Meta/Google/WhatsApp routes); the real base
URLs are the same `META_GRAPH_API_BASE_URL`/`GOOGLE_ADS_API_BASE_URL`
config-swap §7b already established — no new env var for the endpoint
itself. Auth reuses `lead_source_connections`' existing encrypted
Meta/Google tokens (same ad account that already authenticates the
inbound lead pull); that table gains one new nullable column,
`conversion_target_id` (the Meta Pixel/Dataset ID or Google conversion
action resource name), not a second credentials table — a second store
for the same underlying token would just create a place for the two
copies to drift or leak.

**Trigger**: a deal transitioning into a stage with `is_won = true` (see
`pipeline_stages` in `DATABASE_SCHEMA.md` §1) enqueues a
`send_conversion_event` Celery task right after that transaction commits
— the exact same dispatch point §7c's workflow-rule triggers already use
(event-triggered background work is enqueued post-commit, never from
inside the triggering transaction). Keying off `is_won`, not a hardcoded
stage name, matches every other place in this codebase that reads
pipeline-stage semantics (forecast, escalations) — a tenant renaming
"Enrolled" must not silently break outbound conversion sends.

**Only the enrollment signal ships.** A "fee paid" conversion event
(also named in `FEATURES_AND_PLAN.md`'s Phase 4 line item) is explicitly
NOT included: there is no `payments` table yet — `DATABASE_SCHEMA.md` §1
lists it as part of the aspirational initial schema sketch, but no
migration has ever created it, so there is no fee-paid signal to send.
That's a prerequisite gap, not a decision made here; revisit once
`payments` lands as its own feature.

**Delivery semantics**: each (deal, platform) pair gets its own
independent transaction and local retry loop when the task runs — not
Celery's built-in task-level retry — matching §7c's workflow-engine
reasoning exactly: a batch that fires conversions for several
newly-won deals must not let one platform's failure roll back or
duplicate a sibling deal's already-successful send. A new
`conversion_events` table (`tenant_id`, `deal_id` composite FK,
`platform`, `status`, `attempts`, `last_error`, `sent_at`) tracks
delivery per the standard tenant-scoped pattern (`DATABASE_SCHEMA.md`
§2) — one row per (deal, platform) since a deal can in principle need
both a Meta and a Google send.

**Real-time, not batched**: rejected a nightly Celery Beat sweep — ad
platforms' own attribution modeling degrades with delayed conversion
signals, which undercuts the entire reason to send them. Enqueue-on-
commit costs nothing extra infrastructure-wise (worker/beat already run)
and keeps latency low, consistent with Phase 3's "fires without manual
intervention" automation standard.

**No `conversion_events` read endpoint, and no top-level cross-service
E2E test** (unlike every other Phase 2/3/4 feature in `/tests`) — a
deliberate pairing, not an oversight. The `/tests` tier's own convention
(`test_tenant_isolation.py`, `test_lead_source_connections_e2e.py`) is
HTTP-only, black-box against the live BFF — it never queries Postgres
directly, unlike `backend/tests`. Since this send happens asynchronously
via a Celery task with no HTTP surface to observe the outcome through,
an E2E test here would have had to either add direct DB access to that
tier (breaking its established black-box boundary) or wait on the
deferred read endpoint (§4 of the implementation plan). Verified instead
by `backend/tests/test_conversion_events.py` (calls the worker function
directly against a real `mock-integrations`, backend/tests' own
established convention for this) plus a manual live-stack check through
the real BFF during implementation. Revisit if the deferred read
endpoint gets built.

**Still unresolved, not decided here**: sending conversion *events*
doesn't give this app spend data *back* from Meta/Google, so "marketing
team can see cost-per-enrollment by channel" — Phase 4's other unmet
exit-criteria clause — remains open. That needs a product decision on
how ad-spend data enters the system (manual per-campaign entry vs. a
platform spend-API pull, itself a further new integration) — flagged in
`PHASE_4_PLAN.md` already and not resolved by this note.

## 8. Redis usage

Redis is required, used for:

- **Session/token cache** in the BFF (refresh token lookups, rate limiting per tenant).
- **Job queues** for background work: workflow automation triggers, outbound
  email/SMS/WhatsApp sends, Meta/Google conversion event sync.
- **Application-level caching** for expensive read paths (e.g., pipeline
  summary counts, dashboard aggregates) with short TTLs, invalidated on
  write.
- **Idempotency keys** for webhook ingestion (Meta/Google can redeliver
  webhooks — dedupe using an event ID stored in Redis with a TTL).

See Section 5 for local dev topology and Section 6 for how each service maps
to its AWS production equivalent.

## 9. Non-functional notes

- All FastAPI endpoints must require and validate `X-Tenant-Id`; reject
  requests without a resolvable tenant.
- Structured logging with `tenant_id` and `request_id` on every log line —
  essential for debugging pooled-tenant issues.
- Rate limit per tenant at the BFF layer (Redis-backed) to prevent one
  tenant's traffic from degrading others.
