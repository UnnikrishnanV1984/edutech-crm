# CLAUDE.md

Instructions for Claude Code working in this repository. Read
`ARCHITECTURE.md`, `FEATURES_AND_PLAN.md`, `DATABASE_SCHEMA.md`, and
`API_CONVENTIONS.md` before making structural changes.

## Project

Multi-tenant EdTech CRM. React frontend, Node/Express BFF, Python/FastAPI
backend, PostgreSQL, Redis. Ships as pooled SaaS by default, single-tenant
deployable to a client VPC using the same Docker images.

## Repo structure (target)

```
/frontend         React + TypeScript (Vite)
  /Dockerfile
/bff              Node.js + Express + TypeScript
  /Dockerfile
/backend          Python + FastAPI
  /Dockerfile
  /app
    /api          route modules
    /models       SQLAlchemy models
    /schemas      Pydantic schemas
    /services     business logic
    /workers      Celery tasks
/db               SQL migrations (Alembic), seed scripts
/keycloak         realm-export.json (auto-imported on container start)
/deploy/helm       Helm charts — one per deployable module (web, bff, backend, keycloak)
/docker-compose.yml
```

Each of `frontend`, `bff`, `backend`, and `keycloak` is a standalone module
with its own Dockerfile. `docker compose up` runs all of them locally
alongside `db` (Postgres) and `redis`. These are the same images pushed to
Amazon ECR and deployed to EKS via the Helm charts in `/deploy/helm` — see
`ARCHITECTURE.md` Sections 5-6 for the local-to-AWS mapping. `db` and `redis`
are dev-only containers; production uses RDS and ElastiCache, so application
code must reach them only via environment variables, never a hardcoded local
hostname.

## Non-negotiable rules

1. **Every new database table includes `tenant_id UUID NOT NULL` and an RLS
   policy.** No table is exempt unless it is explicitly global/platform-level
   (e.g., a `tenants` table itself). See `DATABASE_SCHEMA.md` for the exact
   pattern to copy.
2. **Every index on a tenant-scoped table leads with `tenant_id`.** Do not
   create an index that omits it.
3. **Every FastAPI endpoint validates `X-Tenant-Id`** and sets the Postgres
   session var (`app.tenant_id`) before running any query. Never trust a
   tenant ID from the request body — only from the validated header/JWT.
4. **The BFF is the only layer that talks to the browser's auth session.**
   FastAPI never reads cookies directly; it only trusts the BFF's forwarded
   headers.
5. **No tenant ID, user-identifying data, or secrets in logs** beyond
   `tenant_id` and `user_id` themselves (needed for debugging) — never log
   emails, phone numbers, or document contents.
6. **Background jobs must carry tenant context explicitly** (as a job
   parameter), since Celery/BullMQ workers don't have a request-scoped
   session to resolve it from.
7. **`tenant_id` is only ever trusted from a validated Keycloak token**
   (resolved by the BFF via JWKS validation), never from a request body,
   query param, or client-supplied header. FastAPI trusts the BFF's
   forwarded `X-Tenant-Id`, and the BFF trusts only Keycloak.
8. **Stateful local containers (`db`, `redis`, `keycloak`'s embedded DB if
   used) are not production infrastructure.** Never write code that assumes
   they're reachable at a fixed local hostname — always go through env vars,
   so the same code works against RDS/ElastiCache/managed Keycloak in AWS.

## Commands

Fill these in as the scaffolding is created; keep this section current.

```
# Local dev (all services: web, bff, backend, db, redis, keycloak)
docker compose up

# Rebuild a single module after a Dockerfile change
docker compose up --build bff

# Keycloak realm/client config is auto-imported from /keycloak/realm-export.json
# on container start — edit that file and restart the keycloak service to
# change realm/client settings rather than using the admin console by hand.

# Frontend
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run test

# BFF
cd bff && npm run dev
cd bff && npm run lint
cd bff && npm run test

# Backend
cd backend && uvicorn app.main:app --reload
cd backend && pytest
cd backend && ruff check .
cd backend && alembic upgrade head
```

## Conventions

- TypeScript strict mode on for both frontend and BFF.
- Python: type hints required, Pydantic for all request/response schemas,
  `ruff` for linting.
- Commits: small, scoped to one feature slice from `FEATURES_AND_PLAN.md`.
- New API endpoints: follow `API_CONVENTIONS.md` for envelope shape, error
  format, and pagination — do not invent a new response shape per endpoint.
- Before implementing a feature, check `FEATURES_AND_PLAN.md` for which phase
  it belongs to and whether prerequisite phases are complete.

## What to ask about before proceeding

- Any change that removes or weakens an RLS policy.
- Any new external integration (new API keys/secrets needed).
- Any schema change to a table already in production use.
