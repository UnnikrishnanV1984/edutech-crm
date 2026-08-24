# Phase 4b plan — outbound Meta/Google conversion signals

Completes Phase 4's remaining exit-criteria clause ("ad platforms are
receiving conversion signals"). The design decision is already made and
approved — `ARCHITECTURE.md` §7d (commit `986abe1`) — this plan only turns
that decision into implementation steps. It does not re-derive or revisit
any of §7d's choices.

## 1. Prerequisites check

Per `CLAUDE.md`'s phase-sequencing rule and this skill's own process step
2: the architect design required for any new external integration is
done (§7d), so implementation can be planned. The rest of Phase 4
(reporting/forecasting/dashboards, `PHASE_4_PLAN.md`) already shipped in
a prior session. This plan is the last piece needed to consider Phase 4
complete — see `FEATURES_AND_PLAN.md`'s updated Phase 4 entry for current
status of each exit-criteria clause.

**Reconfirmed still out of scope** (§7d, unchanged here): "fee paid"
conversion events (no `payments` table exists), and cost-per-enrollment
in real dollars (needs a separate, unresolved product decision on how ad
spend data enters the system).

## 2. Affected layers

- **Database**: new `conversion_events` table; new nullable
  `lead_source_connections.conversion_target_id` column.
- **Backend (FastAPI)**: `PATCH /api/v1/lead-source-connections/{id}`
  gains `conversion_target_id`; deal stage-change route enqueues a new
  Celery task; no new read endpoint for v1 (see §4 below for why).
- **Background jobs**: new `app/workers/conversions.py` — one
  `send_conversion_event` task, following `app/workers/rules.py`'s
  existing per-item transaction + local retry pattern exactly.
- **mock-integrations**: two new local-only routes (`meta.py`,
  `google.py`) simulating the real Conversions API / offline-conversions
  API. No new service, no new Dockerfile (§7d).
- **BFF**: no changes — this is a backend-only outbound side effect
  triggered by an existing write path; the one touched field
  (`conversion_target_id`) rides through the BFF's existing
  `lead-source-connections` proxy route unchanged.
- **Frontend**: `IntegrationsPage.tsx`'s connection management gets a
  `conversion_target_id` field, editable for `meta`/`google` connections
  only.

## 3. Database changes

### 3.1 `conversion_events` (new table)

Standard tenant-scoped pattern (`DATABASE_SCHEMA.md` §2). One row per
(deal, platform) — a deal whose contact came in through a Meta-sourced
lead but whose tenant also has a Google connection configured could in
principle need both.

```sql
CREATE TABLE conversion_events (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    deal_id         UUID NOT NULL,
    platform        TEXT NOT NULL CHECK (platform IN ('meta', 'google')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed')),
    attempts        INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id),
    FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id)
);

CREATE UNIQUE INDEX uq_conversion_events_deal_platform
    ON conversion_events (tenant_id, deal_id, platform);
CREATE INDEX idx_conversion_events_tenant_status
    ON conversion_events (tenant_id, status);

ALTER TABLE conversion_events ENABLE ROW LEVEL SECURITY;
-- policy: standard app.tenant_id = tenant_id, matching every other
-- tenant-scoped table (DATABASE_SCHEMA.md §2) — no exemption needed,
-- this table is only ever written by a worker that already knows
-- tenant_id from the enqueue call, unlike lead_source_connections.
```

The unique `(tenant_id, deal_id, platform)` index is also the retry
task's idempotency guard: `_already_sent` (mirroring `rules.py`'s
`_already_ran`) checks for an existing `status = 'sent'` row before
calling out, so a redelivered/duplicate enqueue can't double-send.

### 3.2 `lead_source_connections.conversion_target_id`

```sql
ALTER TABLE lead_source_connections
    ADD COLUMN conversion_target_id TEXT;
```

Nullable — a connection created before this feature, or a `whatsapp`/
`web` connection that will never send conversions, simply has `NULL`
here. Not encrypted (it's an identifier, not a credential — the Pixel/
Dataset ID or Google conversion-action resource name is not secret in
the way the access token is).

Both changes ship in one migration, `0016_conversion_events.py`.

## 4. API contract

**`PATCH /api/v1/lead-source-connections/{id}`** — extend
`LeadSourceConnectionUpdate` with an optional `conversion_target_id:
str | None`, and add the field to `LeadSourceConnectionOut`. Existing
envelope/error shape unchanged (`API_CONVENTIONS.md` §3-4); no new error
codes needed (empty string / whitespace-only is rejected as
`VALIDATION_ERROR`, matching the model's existing `_check_status`-style
validator pattern).

**No new endpoint to list/inspect `conversion_events` in this pass.**
Considered and deferred, not silently dropped: a manager/admin-visible
"did this enrollment's conversion send?" view would be genuinely useful,
but it's a second reporting surface with its own RowScope/UI design
question, and nothing in Phase 4's exit criteria requires it — the exit
criteria is "ad platforms are receiving conversion signals," which is
satisfied by the send happening, not by an in-app view of it. If this
becomes wanted, it's a small follow-up (a `GET
/api/v1/deals/{id}/conversion-events` nested route, `API_CONVENTIONS.md`
§2's nested-resource shape) — not planned further here.

**No new webhook.** Unlike Phase 2's *inbound* integrations, this is an
outbound call the backend initiates — nothing external calls back into
this app for it.

## 5. Trigger point and background task

### 5.1 Enqueue (deal stage-change route)

`backend/app/api/deals.py`'s `patch_deal` already enqueues
`evaluate_event_rules.delay(...)` right after a stage change, inside the
`if old_stage_id is not None:` block (same documented pre-commit-enqueue
race already accepted there — this plan does not change that trade-off,
only adds a second `.delay()` call at the same site, consistent with the
existing one rather than inventing a different timing).

That block needs the **new** stage's `is_won` flag, which isn't loaded
today (`update_deal` returns `old_stage_id`, not the new stage's `is_won`
— see `deal_service.py:78-96`). Add one small lookup:

```python
if old_stage_id is not None:
    await log_deal_stage_changed(...)   # unchanged
    evaluate_event_rules.delay(...)      # unchanged

    new_stage = await get_stage(context.db, context.tenant.id, deal.stage_id)
    if new_stage is not None and new_stage.is_won:
        for platform in ("meta", "google"):
            send_conversion_event.delay(str(context.tenant.id), str(deal.id), platform)
```

`get_stage` already exists (`pipeline_stage_service.py:83`) — reuse
directly, no new lookup needed.

Enqueuing both platforms unconditionally and letting the task itself
no-op when that tenant has no matching `lead_source_connections` row
(§5.2) is simpler than checking connection existence at the route —
keeps the route from needing to know integration details, matches how
`evaluate_event_rules` similarly doesn't pre-filter by whether rules
exist.

### 5.2 `app/workers/conversions.py` (new)

Mirrors `app/workers/rules.py`'s `_run_one_rule` structure exactly —
same `_MAX_ATTEMPTS = 3`, same per-attempt fresh
session/transaction, same "record failure in a fresh transaction after
retries are exhausted" tail:

```python
@celery_app.task(name="app.workers.conversions.send_conversion_event")
def send_conversion_event(tenant_id: str, deal_id: str, platform: str) -> None:
    asyncio.run(_send_conversion_event(uuid.UUID(tenant_id), uuid.UUID(deal_id), platform))

async def _send_conversion_event(tenant_id, deal_id, platform) -> None:
    sessionmaker = get_sessionmaker()
    last_error = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with sessionmaker() as db, db.begin():
                await _set_tenant(db, tenant_id)
                if await _already_sent(db, tenant_id, deal_id, platform):
                    return
                connection = await get_active_connection(db, tenant_id, platform)
                if connection is None or not connection.conversion_target_id:
                    # No connection configured for this platform on this
                    # tenant — not an error, just nothing to send.
                    # Recorded as 'failed' with a descriptive last_error
                    # so it's visible in the table, not silently dropped.
                    await _record_event(db, tenant_id, deal_id, platform,
                                         "failed", attempt,
                                         "no active connection configured")
                    return
                deal = await _load_deal(db, tenant_id, deal_id)
                token = await decrypt_token(db, connection.access_token_encrypted)
                await _call_platform_api(platform, connection.conversion_target_id,
                                          token, connection.external_account_id, deal)
                await _record_event(db, tenant_id, deal_id, platform, "sent", attempt)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            logger.warning("conversion_send_attempt_failed", tenant_id=str(tenant_id),
                            deal_id=str(deal_id), platform=platform, attempt=attempt,
                            error=last_error)
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        await _record_event(db, tenant_id, deal_id, platform, "failed",
                             _MAX_ATTEMPTS, last_error)
```

`_call_platform_api` is an `httpx.AsyncClient(base_url=settings
.meta_graph_api_base_url)` / `...google_ads_api_base_url` POST — same
config-swap base URLs `app/webhooks/meta.py` and
`google_sync_service.py` already use (§7b), so this task talks to
`mock-integrations` locally with zero new configuration, and to the real
platforms in production the same way.

No escalation on failure (unlike `rules.py`'s workflow-failure
escalation) — a failed marketing-attribution send is not an
operational incident for a counselor/manager's queue; it's recorded in
`conversion_events.status = 'failed'` for later inspection. If that
turns out to be wrong in practice, escalating is a small follow-up, not
re-architected.

### 5.3 mock-integrations new routes

`mock-integrations/app/routers/meta.py`: add
`POST /meta/v18.0/{pixel_id}/events` — accepts a body shaped like the
real Conversions API (`data: [{event_name, event_time, user_data,
...}]`), returns `{"events_received": 1}` on any well-formed request
(no real dedup/validation needed, this is a dev stand-in).

`mock-integrations/app/routers/google.py`: add
`POST /google/customers/{customer_id}/conversionUploads:uploadClick
Conversions` (or the mock's existing simplified path style if
`google.py`'s current routes already diverge from the real Google Ads
REST shape — match whatever convention `google.py` already uses rather
than the real API's exact path if there's a mismatch; check that file
before implementing). Returns a fixed success-shaped response.

Both routes: no signature verification needed (unlike `meta.py`'s
existing inbound-webhook `sign()` check) — these are the mock standing
in for the *target* of an outbound call, not verifying an inbound one.

## 6. Multi-tenancy check

- `send_conversion_event` takes `tenant_id` as an explicit required
  first argument (`CLAUDE.md` rule 6 — background jobs carry tenant
  context explicitly).
- `get_active_connection` filters by `tenant_id` explicitly in
  application code — `lead_source_connections` has no RLS
  (`DATABASE_SCHEMA.md` §1), so this lookup must not rely on
  `app.tenant_id` alone, matching every other query against that table.
- `conversion_events` **does** get standard RLS (§3.1) — unlike
  `lead_source_connections`, nothing needs to discover `tenant_id` from
  this table before `tenant_id` is known; the caller always already has
  it.
- `_call_platform_api` sends only `deal`-derived and
  `contact`-derived data belonging to the same tenant that owns the
  connection being used — no cross-tenant data can reach a payload since
  `deal_id`/`tenant_id` are the task's own arguments, not attacker- or
  cross-tenant-controlled input.
- Credentials never leave the backend process unencrypted except in the
  outbound HTTPS call itself — `decrypt_token` is called inside the same
  transaction that's about to use it, not cached or logged (`CLAUDE.md`
  rule 5 — no secrets in logs; `last_error`/log lines here must never
  include the decrypted token, only HTTP status/exception text).

## 7. Task breakdown

1. Migration `0016_conversion_events.py` — `conversion_events` table +
   `lead_source_connections.conversion_target_id` column, per §3.
2. Backend schema/route: `conversion_target_id` on
   `LeadSourceConnectionUpdate`/`Out`, `PATCH` route already exists — no
   new route, just field wiring. Unit test: patching a connection's
   `conversion_target_id` persists and round-trips.
3. `deals.py` route change (§5.1): look up new stage's `is_won` via the
   existing `pipeline_stage_service.get_stage`, enqueue
   `send_conversion_event` per platform. Test: a stage change into an
   `is_won` stage enqueues; a non-`is_won` stage change does not (assert
   on the Celery task mock, matching how `evaluate_event_rules`'s
   enqueue is presumably already tested).
4. `app/workers/conversions.py` — `send_conversion_event` task,
   `_already_sent`/`_record_event`/`get_active_connection` helpers, per
   §5.2. Unit tests: successful send records `status='sent'`; a
   platform-call exception retries up to 3 times then records `failed`
   with `last_error` set; a tenant with no matching connection records
   `failed` with the "no active connection" message on the first
   attempt (no retry needed for a static missing-config state); a
   duplicate enqueue for an already-`sent` (deal, platform) is a no-op.
5. `mock-integrations` new routes (§5.3) — one test per platform
   asserting a 200 with the expected mock shape.
6. Frontend: `conversion_target_id` field in `IntegrationsPage.tsx`'s
   connection form/edit flow (wherever `status` is currently
   toggled/edited — check `ConnectSourcePanel.tsx` and the inline
   edit affordance, if any, for the right spot), shown only for
   `meta`/`google` connections.
7. Cross-service E2E test (`tests/`, matching
   `test_phase1_tenant_isolation.py`'s live-stack pattern): a deal moved
   into an `is_won` stage for a tenant with a configured `meta`
   connection results in a `conversion_events` row with `status='sent'`
   after the worker processes it (poll with a short timeout, matching
   how other async-completion E2E assertions in this repo likely already
   wait — check `test_lead_source_connections_e2e.py` for the existing
   poll/wait convention before inventing a new one).

## 8. Acceptance criteria

- A deal in tenant A moved into its `is_won` stage, with tenant A's
  `meta` connection configured with a `conversion_target_id`, results in
  exactly one `conversion_events` row (`platform='meta'`,
  `status='sent'`) and one outbound call recorded by
  `mock-integrations`.
- The same deal, if tenant A has no `google` connection configured, gets
  a `platform='google'` row with `status='failed'` and a descriptive
  `last_error` — not a silent no-op, not an exception that crashes the
  task.
- A deal moved into a **non**-`is_won` stage never enqueues a
  conversion send at all.
- A tenant B deal's conversion send never uses tenant A's
  `lead_source_connections` credentials or `conversion_target_id`, even
  under a crafted/incorrect `tenant_id` argument to the task (defense in
  depth — the task's own DB query is tenant-filtered regardless of what
  called it).
- A conversion send that fails 3 times in a row leaves exactly one
  `conversion_events` row (`status='failed'`, `attempts=3`), not three
  duplicate rows — enforced by the `(tenant_id, deal_id, platform)`
  unique index plus `_record_event` using it the same way `rules.py`'s
  `_record_run` uses `workflow_runs`' partial unique index.
- Re-enqueuing `send_conversion_event` for an already-`sent` (deal,
  platform) pair is a no-op — no duplicate outbound call.
- No decrypted access token ever appears in a log line
  (`CLAUDE.md` rule 5).
