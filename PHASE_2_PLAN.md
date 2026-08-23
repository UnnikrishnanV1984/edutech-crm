# Phase 2 plan — Lead capture integrations

Per `FEATURES_AND_PLAN.md` (re-read fresh after the `802dd6b` merge —
Phase 2's own scope is unchanged by that merge). Phase 1's exit criteria
are met and verified. Builds directly on two architect design notes
already produced this session (webhook/tenant-resolution structure, and
the mock-backed build approach) — referenced inline, not re-derived.

## 1. Prerequisites check

Phase 1 exit criteria met (contacts/deals/tasks/documents CRUD, RLS
verified, activity logging working). No blockers to starting Phase 2.

## 2. Affected layers

| Layer | Touched? | What changes |
|---|---|---|
| Frontend | Minimal | An admin-only "Integrations" settings screen (connect/disconnect, status) — scoped small, see §7 step ordering for why it's last, not skipped |
| BFF | No changes | Webhooks bypass it entirely (architect note 1); the admin connection-management endpoints are ordinary `/api/v1` routes, already covered by the existing generic proxy mount — no new BFF code needed, same as every resource added in Phase 1 |
| Backend | Yes, substantial | New `lead_source_connections` table/service/routes, three ingestion pipelines, new public `/webhooks/*` routes, a new `mock_integrations` app |
| Database | Yes | One new table, deliberately without RLS (architect note 1) |
| Background jobs | Partial | No Celery/BullMQ infrastructure exists yet in this repo — flagged explicitly in §4 rather than silently building a scheduler |
| Infra | Yes | New `mock-integrations` Docker Compose service (default stack, not opt-in) |

## 3. Database changes

```sql
CREATE TABLE lead_source_connections (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    source                  TEXT NOT NULL
                            CHECK (source IN ('meta', 'google', 'whatsapp', 'web')),
    external_account_id     TEXT NOT NULL,
    access_token_encrypted  BYTEA,
    refresh_token_encrypted BYTEA,
    token_expires_at        TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'disabled')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
);

-- Global, not tenant-scoped — this is the lookup a webhook uses to
-- *discover* tenant_id in the first place (architect note 1).
CREATE UNIQUE INDEX uq_lead_source_connections_external
    ON lead_source_connections (source, external_account_id);
CREATE INDEX idx_lead_source_connections_tenant
    ON lead_source_connections (tenant_id, source);

-- Deliberately NO RLS — see the note directly below.
GRANT SELECT, INSERT, UPDATE ON lead_source_connections TO crm_app;
```

**This is the one genuinely non-obvious consequence of "no RLS" worth
stating plainly**: unlike every other table in this app, the database
itself will not stop a query against `lead_source_connections` from
returning another tenant's row. Every application-layer query — the
admin list/connect/disconnect endpoints *and* the webhook-resolution
path — must include an explicit `tenant_id = :tenant_id` filter by
hand. §6 and §8 call this out as its own required test, not folded into
the general RLS test pattern, because there's no RLS here to test.

`access_token_encrypted`/`refresh_token_encrypted` use `pgcrypto`'s
`pgp_sym_encrypt`, keyed by a new required env var
`INTEGRATION_CREDENTIALS_KEY` (architect note 1). `web` connections
never populate these — the "credential" is the public, non-secret
`external_account_id` itself (a generated embed key).

`DATABASE_SCHEMA.md` §1 gets a new row for `lead_source_connections`,
with a note next to the standard-pattern reference explaining the RLS
exemption (mirroring how the `tenants` row already documents its own
exemption).

## 4. API contract

### 4.1 Admin connection management (`/api/v1`, existing BFF proxy, no BFF changes)

New: a `require_admin` FastAPI dependency (`app/deps/roles.py`) —
`403 FORBIDDEN` if `context.user_role != "admin"`. **First role-gated
endpoint in this codebase** — every Phase 0/1 endpoint checks tenant
only, not role. Flagging this rather than treating it as routine: it's
a one-line guard using the role the token already carries, not a
preview of Phase 3's full RBAC/row-level-scoping system, and it should
stay that way — resist the temptation to build more than "is this
caller an admin" here.

```
GET    /api/v1/lead-source-connections
POST   /api/v1/lead-source-connections
PATCH  /api/v1/lead-source-connections/{id}
```

`GET` — list this tenant's connections. Response never includes
decrypted tokens, only `{id, source, external_account_id, status,
token_expires_at, created_at}`.

`POST` — body `{source, external_account_id, access_token?,
refresh_token?}`. For `source=web`, `external_account_id`/tokens are
ignored — the server generates the embed key. For `meta`/`whatsapp`/
`google`, tokens are required and get encrypted before storage.
`409 CONFLICT` if `(source, external_account_id)` already exists for
*any* tenant (the global unique index) — error detail should say "this
account is already connected" without revealing which tenant, so one
tenant can't probe whether another has connected a given account.

`PATCH` — body `{status}` only (`active`/`disabled`) — disconnect is a
status flip, not a delete, matching `contacts`/`courses`' existing
soft-disable convention. Token rotation (re-`POST`ing new tokens for an
existing connection) is a reasonable follow-up, not required for this
phase's exit criteria.

`POST /api/v1/lead-source-connections/{id}/sync` — admin-only,
on-demand trigger for a Google pull (§4.3 explains why this exists
instead of a scheduler).

### 4.2 Public webhook routes (`backend`, bypass BFF entirely, new public ingress path — architect note 1)

```
GET  /webhooks/meta       (Meta's subscription verification handshake — echoes hub.challenge)
POST /webhooks/meta
GET  /webhooks/whatsapp   (same handshake pattern, WhatsApp Cloud API is a Meta product)
POST /webhooks/whatsapp
```

Both `POST` handlers, in order: verify `X-Hub-Signature-256` against
the raw body using the platform's app secret (reject `401` before
anything else) → extract `external_account_id` from the payload →
look up `lead_source_connections` (no tenant context yet — this *is*
the tenant-resolution step) → `404`/ignore if no active connection
found for that account (don't leak whether an account ID is known) →
check the Redis idempotency key → if unseen, fetch full lead detail via
the platform's Graph/Cloud API (through the mock in dev, per §4.4) →
resolve course, create contact/deal/activity → mark the Redis key.
Always returns `200` quickly (webhook senders retry on non-2xx) even
when a lead is skipped for a benign reason (duplicate, unknown course)
— only signature failure gets a non-2xx.

### 4.3 Google (pull, not push)

No inbound webhook. `backend` calls the Google Ads API (through the
mock) using that connection's stored OAuth token to list new leads
since the last successful sync, on demand via §4.1's `/sync` endpoint.
**This repo has no Celery/BullMQ worker infrastructure yet** —
`ARCHITECTURE.md` lists it as a future background-jobs layer, not
something built in Phase 0/1. Rather than stand up a scheduler now
(real scope creep beyond this phase), Google sync is admin-triggered
for this phase; automatic periodic polling is a follow-up once
background-job infrastructure actually exists. Flagging this as an
explicit boundary, not a silent gap.

### 4.4 `mock-integrations` (new service, dev/test only — never in `ARCHITECTURE.md` §6's production mapping, same annotation `minio` already carries in §5)

```
GET  /meta/v18.0/{leadgen_id}          -> field_data (shaped like backend/app/connectors/seed_data/meta.json)
POST /meta/_trigger                     -> signs + POSTs a simulated webhook to backend's own /webhooks/meta
GET  /whatsapp/v18.0/{message_id}      -> same shape
POST /whatsapp/_trigger
POST /google/oauth/token                -> mock token exchange
GET  /google/customers/{id}/leads       -> mock leads list
```

`_trigger` endpoints exist so integration tests (and manual local
testing) can simulate an inbound webhook without a real Meta/WhatsApp
server — they sign the payload with the same `META_APP_SECRET`/
`WHATSAPP_APP_SECRET` value `backend` verifies against, so the real
verification code runs, not a bypassed stub.

## 5. Multi-tenancy check

- `lead_source_connections` has no RLS by design (§3) — every query
  against it needs an explicit `tenant_id` filter in application code,
  checked by its own dedicated test (§8), not assumed covered by the
  general RLS suite.
- `tenant_id` is never read from a webhook payload or request body at
  any point — only ever resolved by looking up the platform-supplied
  `external_account_id` in `lead_source_connections`, and that mapping
  is only ever written by an authenticated admin action through the
  normal Keycloak+BFF+`require_admin` path. This satisfies
  `CLAUDE.md` rule 7's spirit even though the webhook request itself
  carries no Keycloak token.
- Once a tenant is resolved, every subsequent write (contact/deal/
  activity creation) goes through the exact same `set_config('app.tenant_id',
  ...)` + existing Phase 1 service-layer functions the seed-connectors
  work already established — full RLS applies from that point on.
- `mock-integrations` never touches Postgres directly — it only calls
  back into `backend`'s own public webhook routes, which enforce
  everything above normally.

## 6. Task breakdown

1. Migration: `lead_source_connections` (§3), including the `pgcrypto`
   extension if not already enabled.
2. Backend: `app/core/crypto.py` — thin `encrypt_token`/`decrypt_token`
   wrapping `pgp_sym_encrypt`/`pgp_sym_decrypt` with
   `INTEGRATION_CREDENTIALS_KEY`; add the env var to `.env.example`/
   `config.py`.
3. Backend: `lead_source_connection_service.py` — create/list/update,
   every query with an explicit `tenant_id` filter (§5). Unit tests
   including the no-RLS cross-tenant filter check specifically.
4. Backend: `app/deps/roles.py` — `require_admin`. Test: a
   manager/counselor token gets `403` on an admin route.
5. Backend: `/api/v1/lead-source-connections` routes (§4.1) + schemas.
   Tests including the global-uniqueness `409` and its non-leaking
   error message.
6. `mock-integrations`: new service scaffold (FastAPI, own Dockerfile,
   own `pyproject.toml`), wired into `docker-compose.yml`'s default
   stack. `/meta` and `/whatsapp` field-data + `_trigger` routes,
   reusing the existing `seed_data/*.json` fixture shapes.
7. Backend: `app/webhooks/meta.py` — signature verification, tenant
   resolution, Redis idempotency check, Graph API fetch (via
   `META_GRAPH_API_BASE_URL`), course resolution, contact/deal/activity
   creation reusing `contact_service`/`deal_service`/
   `activity_service.log_lead_captured` (already exists from the
   seed-connectors work) with the owner round-robin from
   `user_service.list_counselor_ids` (same precedent). If course can't
   be resolved, still create the contact, skip the deal, log a warning
   — don't drop the lead entirely.
8. Backend: `GET /webhooks/meta` verification handshake.
9. Tests for step 7-8: real signed payloads (self-signed with a test
   secret, matching this repo's existing rigor — no logic-bypassing
   mocks), duplicate delivery is a no-op, unsigned/badly-signed request
   is rejected before any DB touch, unknown `external_account_id` is
   ignored without leaking anything.
10. `mock-integrations`: `/whatsapp` routes (mirrors step 6).
11. Backend: `app/webhooks/whatsapp.py` + handshake route — mirrors
    steps 7-9, reusing the shared HMAC-verification helper rather than
    duplicating it.
12. `mock-integrations`: `/google/oauth/token` + `/google/customers/{id}/leads`.
13. Backend: Google OAuth token exchange/refresh against the mock,
    stored via the same encrypted-column mechanism as Meta/WhatsApp.
14. Backend: `POST /api/v1/lead-source-connections/{id}/sync` (§4.3) —
    pulls new leads via the mock, same dedupe/course-resolution/
    ingestion pipeline as the webhook path, reused not reimplemented.
15. Backend: `source=web` connection creation (embed-key generation, no
    tokens) + `POST /webhooks/web` (or a public `/api/v1`-adjacent
    route — decide at implementation time whether this is public-form
    submission like the others or deserves its own path) with basic
    rate limiting, since it's the one fully public, unauthenticated,
    embeddable endpoint (§4's rate-limiting gap called out by
    architect note 1).
16. `ARCHITECTURE.md`: update §5's local dev table (`mock-integrations`
    row, "never deployed" annotation) and §6's production mapping
    (`backend` gets a public `/webhooks/*` ingress path alongside its
    existing internal-only `/api/v1` path).
17. `DATABASE_SCHEMA.md`: add the `lead_source_connections` row to §1
    with its RLS-exemption note.
18. Cross-service E2E (`tests/`): using the mock's `_trigger` endpoints,
    prove a simulated Meta/WhatsApp lead lands correctly attributed
    within the running stack, and that a tenant-B admin token can't see
    tenant-A's connections via the API.
19. Frontend: a minimal admin-only "Integrations" screen — list
    connections + connect/disconnect. **Recommending this stays in
    Phase 2** rather than deferring: without it there's no way for a
    real admin to ever connect a real account once credentials exist,
    which is the entire point of building this now — the backend work
    is otherwise not actually usable by anyone. Keep it small: a table
    + a form, no new design-system components beyond what
    `DESIGN_SYSTEM_REFRESH.md` already provides.

## 7. Acceptance criteria

1. A simulated Meta lead, triggered via `mock-integrations`' `_trigger`
   endpoint, appears as a contact+deal+activity in the correct tenant's
   pipeline within seconds — matching `FEATURES_AND_PLAN.md`'s Phase 2
   exit criteria, achieved against the mock rather than blocked on real
   credentials.
2. Same for a simulated WhatsApp message.
3. Same for a Google pull triggered via the admin `/sync` endpoint.
4. An unsigned or badly-signed webhook POST is rejected `401` before
   any database query runs.
5. Redelivering the same event id is a no-op (no duplicate contact/deal/
   activity) — verified via the Redis key, and separately via the DB
   partial-unique-index backstop with Redis flushed.
6. A `lead_source_connections` query missing its `tenant_id` filter
   would leak cross-tenant data — proven by a dedicated test that
   deliberately checks the service layer always includes it (since RLS
   can't catch this one).
7. A manager or counselor token gets `403` on every
   `/api/v1/lead-source-connections*` route; an admin token succeeds.
8. Connecting the same `(source, external_account_id)` twice — even
   from a different tenant — returns `409` without revealing which
   tenant already holds it.
9. `mock-integrations` never appears reachable from outside the compose
   network in any production-facing config (Helm values contain no
   reference to it).
10. A lead with no resolvable course still creates a contact (not
    silently dropped), with no deal and a logged warning.
