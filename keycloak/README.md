# Keycloak realm

`realm-export.json` is auto-imported by the `keycloak` container on start
(`--import-realm`, see `docker-compose.yml`) — do not configure this by hand
in the admin console; edit this file and restart the service instead.

## Local dev seed identities

Two tenants, one counselor and one admin user each — the admin identities
were added in Phase 2 so `POST/PATCH /api/v1/lead-source-connections*`
(admin-only, `PHASE_2_PLAN.md` §4.1) has a real dev login to exercise from
the frontend Integrations screen and from `tests/test_lead_source_connections_e2e.py`,
without which those routes would be unreachable outside a raw curl call
with hand-set headers. `manager.a` (tenant A only) was added later so
`ManagerDashboard.tsx`'s team-scoped widgets (Pipeline by stage / My queue
today / Team SLA) have a real dev login too — without it, RowScope's
manager branch (self + direct reports) was untestable outside a hand-set
header. The `tenant_id` custom user attribute below **must exactly match**
the `tenants.id` row the Postgres seed script (`backend/app/db/seed.py`)
inserts for the same tenant — Keycloak and Postgres don't share a
database, so these UUIDs are fixed/hardcoded on both sides rather than
generated, purely so local dev has a stable pairing.

Each user's `id` is also pinned (rather than left for Keycloak to generate
on import) for the same reason, one level deeper: it's what Keycloak issues
as the `sub` claim (see the `sub-explicit` mapper below), and
`backend/app/db/seed.py` pre-provisions a matching `users` row keyed on
that exact value before anyone has ever logged in — so seed data (see
`backend/app/connectors/`) has a real owner to assign to from the first
`docker compose up`, and the row that person later gets on real login is
the *same* row, not a duplicate.

`counselor.a` additionally carries a `reports_to: ["manager.a"]` attribute
— a dev-seed-only convention (not a Keycloak concept `upsert_user` itself
understands), read by `seed.py`'s own second pass to set `users.manager_id`
after both rows exist, so `manager.a`'s RowScope actually has a direct
report to see team data through, rather than an empty team.

`manager.a`'s `id` is a genuine Keycloak-assigned UUID, not a hand-picked
one like the others — it was added to an already-running realm via the
Admin API (`--import-realm` only imports into a *new* realm; it silently
no-ops against one that already exists, so editing this file and
restarting the container does nothing for identities added after a
realm's first boot), and the Admin API's user-create endpoint does not
honor a caller-supplied `id`. This file's `id` was updated to match what
Keycloak actually assigned so `seed.py`'s Postgres provisioning stays
keyed on the same value the live token's `sub` claim carries — a fresh
`docker compose down -v && up` imports this file from scratch and *will*
honor the pinned `id` at that point, since realm import (unlike the
Admin API) creates the whole realm in one shot.

| Tenant | `tenants.id` / Keycloak `tenant_id` attribute | Username | Password | Role | Keycloak/user `id` (→ `sub`) |
|---|---|---|---|---|---|
| Future Digital Inc | `a1111111-1111-1111-1111-111111111111` | `counselor.a` | `password` | counselor (reports to `manager.a`) | `ca111111-1111-1111-1111-111111111111` |
| Tenant B Academy | `b2222222-2222-2222-2222-222222222222` | `counselor.b` | `password` | counselor | `cb222222-2222-2222-2222-222222222222` |
| Future Digital Inc | `a1111111-1111-1111-1111-111111111111` | `manager.a` | `password` | manager | `8bfb1ef2-eb6a-4d85-93fe-c0e4b9b6ce29` |
| Future Digital Inc | `a1111111-1111-1111-1111-111111111111` | `admin.a` | `password` | admin | `da111111-1111-1111-1111-111111111111` |
| Tenant B Academy | `b2222222-2222-2222-2222-222222222222` | `admin.b` | `password` | admin | `db222222-2222-2222-2222-222222222222` |

## Token claims

The `web` client maps:
- `sub` — via an explicit property mapper (`sub-explicit`). **Do not remove
  this mapper.** On the Keycloak image pinned here (26.7.2), the access
  token omits `sub` by default — confirmed against both a from-scratch
  client and the built-in `admin-cli` client, so it's server behavior, not a
  config mistake in this realm. `sub` is only reliably present in the
  **ID token** without this mapper. Verified live: without it, `bff`'s proxy
  crashed the process outright (`ERR_HTTP_INVALID_HEADER_VALUE`, setting
  `X-User-Id` to `"undefined"`) — see auth.ts's checks, which now reject a
  token missing `sub` with 401 instead of letting that reach the proxy.
- `tenant_id` — from the user attribute of the same name (custom mapper)
- `realm_access.roles` — via the built-in `roles` client scope
- `email`, `name` — via the built-in `email`/`profile` client scopes
- `aud: ["web"]` — via an explicit audience mapper (Keycloak does not
  include the client's own `clientId` in `aud` by default)

The BFF (`bff/src/auth/*`) validates all four before forwarding
`X-Tenant-Id`/`X-User-Id`/`X-User-Email`/`X-User-Name`/`X-User-Role` to
FastAPI — see `API_CONVENTIONS.md` §1.

`directAccessGrantsEnabled: true` on the `web` client exists only so the
tenant-isolation CI job (`DEVELOPMENT_PLAN.md` §7) can fetch real tokens for
both seed users without driving a browser through the PKCE flow. Real user
login always goes through the Authorization Code + PKCE flow from React.
