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
| `backend` | Deployment + Service in EKS, behind ALB Ingress (internal, only reachable from `bff`) |
| `db` | Amazon RDS for PostgreSQL (Multi-AZ) — not run in-cluster |
| `redis` | Amazon ElastiCache for Redis — not run in-cluster |
| `keycloak` | Deployment + Service in EKS (or AWS-managed alternative, e.g. Cognito, if the team later chooses to swap it — realm-based design keeps this optional) |
| `minio` | Amazon S3 — not run in-cluster in production |

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
