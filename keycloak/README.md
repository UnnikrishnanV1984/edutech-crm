# Keycloak realm

`realm-export.json` is auto-imported by the `keycloak` container on start
(`--import-realm`, see `docker-compose.yml`) — do not configure this by hand
in the admin console; edit this file and restart the service instead.

## Local dev seed identities

Two tenants, one counselor user each. The `tenant_id` custom user attribute
below **must exactly match** the `tenants.id` row the Postgres seed script
(`backend/app/db/seed.py`) inserts for the same tenant — Keycloak and
Postgres don't share a database, so these UUIDs are fixed/hardcoded on both
sides rather than generated, purely so local dev has a stable pairing.

Each user's `id` is also pinned (rather than left for Keycloak to generate
on import) for the same reason, one level deeper: it's what Keycloak issues
as the `sub` claim (see the `sub-explicit` mapper below), and
`backend/app/db/seed.py` pre-provisions a matching `users` row keyed on
that exact value before anyone has ever logged in — so seed data (see
`backend/app/connectors/`) has a real owner to assign to from the first
`docker compose up`, and the row that person later gets on real login is
the *same* row, not a duplicate.

| Tenant | `tenants.id` / Keycloak `tenant_id` attribute | Username | Password | Keycloak/user `id` (→ `sub`) |
|---|---|---|---|---|
| Tenant A Academy | `a1111111-1111-1111-1111-111111111111` | `counselor.a` | `password` | `ca111111-1111-1111-1111-111111111111` |
| Tenant B Academy | `b2222222-2222-2222-2222-222222222222` | `counselor.b` | `password` | `cb222222-2222-2222-2222-222222222222` |

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
