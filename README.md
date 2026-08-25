# OpenFunnel

Multi-tenant CRM for EdTech admissions teams. See `ARCHITECTURE.md`,
`FEATURES_AND_PLAN.md`, `DATABASE_SCHEMA.md`, and `API_CONVENTIONS.md` for
the full design; `DEVELOPMENT_PLAN.md` for the current phase plan.

## Quickstart (local dev)

Requires Docker and Docker Compose.

```bash
cp .env.example .env
docker compose up
```

This brings up `web`, `bff`, `backend`, `db`, `redis`, and `keycloak`. The
Keycloak realm (client, roles, `tenant_id` claim mapper, two seed tenants) is
auto-imported from `keycloak/realm-export.json` — no manual console setup.
Database migrations and the tenant seed data run automatically on `backend`
container start; each seed user's `users` row is created on their first
login (JIT-provisioned from the token, not pre-seeded).

Once healthy:

- Frontend: http://localhost:5173
- BFF: http://localhost:4000
- Backend (internal, direct access for debugging only): http://localhost:8000
- Keycloak admin console: http://localhost:8080 (`admin` / see `.env`)

Seed users (password `password` for both, see `keycloak/realm-export.json`):

| Tenant | Username | Role |
|---|---|---|
| Future Digital Inc | `counselor.a` | counselor |
| Tenant B Academy | `counselor.b` | counselor |

Log in as `counselor.a`, then `counselor.b`, to see the tenant-isolation
boundary in the shell page.

To reset to a clean state:

```bash
docker compose down -v
docker compose up
```

## Rebuilding a single service

```bash
docker compose up --build bff
```

## Per-service commands (without Docker)

See `CLAUDE.md` → Commands.

## Optional: local object storage (MinIO)

Not started by default. Bring it up with:

```bash
docker compose --profile storage up
```
