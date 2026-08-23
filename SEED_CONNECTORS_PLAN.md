# Seed-data connectors — implementation plan

## 1. Where this fits

Not a phase in `FEATURES_AND_PLAN.md` — it's dev-only tooling that
pre-builds the connector interface Phase 2 ("Lead capture integrations")
will implement for real. Treated as ad-hoc infrastructure work, already
scoped with the user via the `architect` skill (see that design note for
the full reasoning, including why `owner_id`/`actor_id` stay `NOT NULL`
rather than becoming nullable). Phase 1's exit criteria are met, so this
doesn't block on anything.

## 2. Affected layers

| Layer | Touched? | What changes |
|---|---|---|
| Frontend | No | Every seeded contact/deal gets a real owner via round-robin — no new UI state |
| BFF | No | No new endpoints |
| Backend | Yes | New `app/connectors/` package, one new `activity_service` function, `app/db/seed.py` extended, new `app/core/redis.py` helper |
| Database | No | No new tables, no migration — explicitly ruled out in the architect note |
| Background jobs | No | Runs once at container boot via `docker-entrypoint.sh`, not a recurring job |
| Infra | Yes | `docker-compose.yml` — one new read-only volume mount on `backend` |
| Keycloak | Yes | `realm-export.json` — pin explicit `id` for the two dev users |

## 3. Database changes

None. Confirmed in the architect design note: `owner_id`/`actor_id` stay
`NOT NULL`; seeded leads get a real owner via round-robin over
pre-provisioned dev users instead.

## 4. API contract

None — no new or changed endpoints.

## 5. Multi-tenancy check

- Connectors iterate `SELECT id FROM tenants` — never a hardcoded tenant
  UUID.
- Every write happens inside a session that runs
  `SELECT set_config('app.tenant_id', :id, true)` first, exactly like
  `get_tenant_context` does for a real request — RLS applies identically,
  nothing bypasses it.
- Idempotency keys are tenant-scoped (`seed:ingested:{tenant_id}:{source}:{external_id}`)
  so one tenant's re-seed can never be short-circuited by another
  tenant's already-ingested lead.
- Round-robin owner assignment only ever picks from `users` rows already
  scoped to that same tenant (queried with `tenant_id` in the `WHERE`).

## 6. Task breakdown

1. **Keycloak**: pin explicit `id` for `counselor.a`
   (`ca111111-1111-1111-1111-111111111111`) and `counselor.b`
   (`cb222222-2222-2222-2222-222222222222`) in `keycloak/realm-export.json`,
   following the existing `a1111.../b2222...` tenant-ID convention. Update
   `keycloak/README.md`'s seed-identity table with the pinned IDs, and fix
   its stale `db/seed.sql` reference to `backend/app/db/seed.py` in the
   same commit (one-line doc fix, not a separate task).
2. **`docker-compose.yml`**: mount `./keycloak/realm-export.json` read-only
   into the `backend` service (e.g. `/app/dev-realm.json`).
3. **`backend/app/db/seed.py`**: extend to parse the mounted realm file's
   `users` array and call the existing `upsert_user` service for each
   entry (`id` → `keycloak_sub` is wrong — see note below), inside a
   per-tenant `set_config` session. Add a test proving a second run
   doesn't duplicate (upsert is already idempotent on
   `(tenant_id, keycloak_sub)`, so this is mostly a "does it run cleanly
   twice" check).
   - **Note to resolve during implementation**: `upsert_user`'s
     `keycloak_sub` param must hold the *token's* `sub` claim, which is
     the Keycloak-issued `id` we're pinning — pass the realm file's `id`
     field as `keycloak_sub`, not a separate synthetic value, so JIT
     provisioning matches on real login.
4. **`backend/app/core/redis.py`**: lazy `get_redis_client()` singleton
   (mirrors `app/core/s3.py`'s pattern), for the idempotency check.
5. **`backend/app/connectors/base.py`**: `RawLead` dataclass
   (`external_id`, `full_name`, `email`, `phone`, `course_code`,
   `occurred_at`, `raw` payload) + `LeadConnector` ABC (`source`,
   `fetch_raw_leads() -> list[RawLead]`) + `SeedFileConnector` base that
   reads its own JSON file and calls a subclass-provided `normalize(raw)`.
6. **`backend/app/connectors/seed_data/`**: `courses.json` +
   `meta.json`/`google.json`/`web.json`/`whatsapp.json`, each shaped like
   that platform's actual payload (e.g. Meta's `field_data` array) so
   `normalize()` does real work, not a pass-through.
7. **`backend/app/connectors/{meta,google,web,whatsapp}.py`**: thin
   subclasses — `source` + filename + `normalize()`.
8. **`backend/app/services/activity_service.py`**: add
   `log_lead_captured(db, tenant_id, contact_id, deal_id, actor_id, source, payload)`.
9. **`backend/app/connectors/ingestion_service.py`**: per tenant — seed
   courses (idempotent via the existing `uq_courses_tenant_code`, same
   proactive-check-then-catch pattern as contact dedupe), then per
   connector: fetch raw leads, and for each one not already marked in
   Redis — round-robin pick a `role='counselor'` user from that tenant,
   `contact_service.create_contact`, `deal_service.create_deal`,
   `activity_service.log_lead_captured`, then mark the Redis key. A
   contact-dedupe `409` from a partial prior run is treated as
   already-ingested (mark the Redis key, move on), not an error. If a
   tenant has zero counselor users, skip lead ingestion for that tenant
   with a log line — never violate `owner_id`/`actor_id` `NOT NULL`.
10. **`backend/app/connectors/seed_runner.py`**: `python -m
    app.connectors.seed_runner` entrypoint — builds its own session/redis
    client, iterates tenants, calls `ingestion_service`.
11. **`backend/docker-entrypoint.sh`**: inside the existing
    `ENVIRONMENT=development` block, after `python -m app.db.seed`, add
    the seed-runner call.
12. **Tests** (`backend/tests/`): real-Postgres+Redis-gated, matching
    existing conventions — ingestion creates the expected
    contacts/deals/activities; round-robin distributes across both dev
    users; re-running is a no-op (row counts unchanged, Redis
    short-circuits before any DB write); a tenant with no users is
    skipped without raising.
13. **Live verification**: `docker compose down -v && docker compose up`
    from a clean checkout, confirm seeded data via the API for both
    tenants; `docker compose restart backend` and confirm no duplicates;
    log in as `counselor.a` for real and confirm `/api/v1/me` resolves to
    the same `users.id` that owns her seeded contacts.
14. **`ARCHITECTURE.md`**: short new subsection noting the connector
    pattern and that Phase 2 replaces each connector's `fetch_raw_leads`
    with a real API call — same downstream ingestion path.

## 7. Acceptance criteria

1. Fresh `docker compose down -v && docker compose up`: each dev tenant
   has one seeded contact per sample lead across all four source files,
   each contact's `lead_source` matching its origin connector.
2. Every seeded contact's `owner_id` is a real row in `users` belonging to
   that tenant (`counselor.a`'s user id for Tenant A, `counselor.b`'s for
   Tenant B), distributed round-robin — not all landing on one user.
3. Every seeded contact has exactly one deal, in that tenant's default
   (first non-won/lost) pipeline stage, referencing a seeded course.
4. Every seeded deal has exactly one `lead_captured` activity with a
   non-null `actor_id`.
5. `docker compose restart backend` (no volume wipe) does not change
   contact/deal/activity row counts — verified before/after.
6. Logging in as `counselor.a` through the real Keycloak PKCE flow
   resolves (`/api/v1/me`) to the same `users.id` that already owns her
   tenant's seeded contacts — not a second, duplicate user row.
7. No literal lead/contact field values (name, email, phone, course name)
   appear in any `.py` file under `backend/app/connectors/` — only in
   `seed_data/*.json`.
8. Setting `ENVIRONMENT` to anything other than `development` skips this
   entirely, verified by the same gate `docker-entrypoint.sh` already uses
   for tenant seeding.
9. A direct-SQL check (same pattern as `test_tenant_isolation_db.py`)
   confirms Tenant A's seeded contacts are invisible with
   `app.tenant_id` set to Tenant B.
