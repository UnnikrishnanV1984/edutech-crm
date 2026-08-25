# Pipeline Config: Save / Reset / Reset to Default

Ad-hoc admin-UX request (not yet in `FEATURES_AND_PLAN.md` — closest sibling
is `ADMIN_UX_IMPROVEMENTS_PLAN.md`, which this plan follows the same
conventions as). Not gated on any phase's exit criteria; touches only the
existing `pipeline_stages` admin screen and one new supporting table.

Design decisions below were confirmed directly with the requester
(2026-08-25) rather than assumed, since several had real data-loss
consequences:

- **Reset** = discard-unsaved-draft, not a replay/undo of already-persisted
  mutations. This requires changing Pipeline Config from "every click hits
  the API immediately" to a draft-then-Save model with an explicit **Save**
  button (new, not originally in the ask, but required to make "Reset"
  meaningful).
- **Save** is all-or-nothing — one new transactional batch endpoint, not a
  client-side replay of the existing per-stage CRUD calls.
- **Reset to Default** restores a snapshot captured once, at the moment a
  tenant's default 8 stages were first seeded — not the same hardcoded list
  for every tenant. Blocked (409) if any stage that would be removed is
  currently in use by a deal or SLA policy, mirroring the existing
  single-stage delete guard.

## 1. Located

Not listed in `FEATURES_AND_PLAN.md`. Flagging per this skill's step 1 —
treating it as ad-hoc admin-UX work, same bucket as
`ADMIN_UX_IMPROVEMENTS_PLAN.md`. Recommend folding a line into
`FEATURES_AND_PLAN.md` once built, but not blocking on that here.

## 2. Prerequisites check

None. Touches only `pipeline_stages` (Phase 1) and adds one new table —
independent of any in-progress phase.

## 3. Affected layers

- **Database**: one new table, `pipeline_stage_default_snapshots`
  (immutable, per-tenant). No changes to `pipeline_stages` itself.
- **Backend**: two new endpoints (`POST /api/v1/pipeline-stages/batch`,
  `POST /api/v1/pipeline-stages/reset-to-default`); `ensure_default_stages`
  extended to also write the snapshot, once, the first time it seeds a
  tenant's defaults.
- **BFF**: none — generic `/api/v1/*` proxy already covers new routes.
- **Frontend**: `PipelineConfigPage.tsx` restructured around a local draft
  vs. last-saved-snapshot model; two new confirmation modals.
- **Background jobs**: none.

## 4. Database changes

### 4.1 `pipeline_stage_default_snapshots` (new)

Row-per-stage, same shape as `pipeline_stages` minus the mutable/timestamp
columns — deliberately typed columns, not a JSONB blob, so it stays
queryable and consistent with every other table in this schema.

```sql
CREATE TABLE pipeline_stage_default_snapshots (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    name                TEXT NOT NULL,
    sort_order          INTEGER NOT NULL,
    is_won              BOOLEAN NOT NULL DEFAULT false,
    is_lost             BOOLEAN NOT NULL DEFAULT false,
    is_invoice_stage    BOOLEAN NOT NULL DEFAULT false,
    is_rework_stage     BOOLEAN NOT NULL DEFAULT false,
    win_probability_pct INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
);
CREATE INDEX idx_pipeline_stage_default_snapshots_tenant
    ON pipeline_stage_default_snapshots (tenant_id);

ALTER TABLE pipeline_stage_default_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_stage_default_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_pipeline_stage_default_snapshots
    ON pipeline_stage_default_snapshots
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Standard tenant-scoped pattern per `DATABASE_SCHEMA.md` §2 — no exception
needed here (unlike `pipeline_stage_templates`, this genuinely is per-tenant
data: each tenant's own provisioning-time baseline, not shared content).
**Write-once**: rows are only ever inserted, never updated — a snapshot is
a point-in-time capture, not a live-editable config.

### 4.2 Backfill for existing tenants

Same migration, data-only step: every tenant with zero rows in the new
table gets one snapshot inserted from `pipeline_stage_service.DEFAULT_STAGES`
(the same 8-stage list `ensure_default_stages` already seeds a *brand-new*
tenant from) — **not** from that tenant's current, possibly-already-edited
`pipeline_stages`. Reasoning, stated explicitly since it's a judgment call
made without a fourth round of clarification: "system-defined default"
reads as the platform's known-good baseline, not an accidental freeze of
whatever a given tenant happened to have drifted their pipeline into by the
time this feature ships. Flag this assumption to the requester before
shipping — reversible by re-running the backfill differently if wrong,
since these rows have no other reader yet at that point.

### 4.3 `ensure_default_stages` (existing function, extended)

`pipeline_stage_service.py`'s `ensure_default_stages` already guards on
"only seed if this tenant has zero `pipeline_stages` rows" — same
transaction, same guard, also insert the 8
`pipeline_stage_default_snapshots` rows the first time (and only the first
time) it seeds a new tenant. This is the actual "snapshot taken once, at
provisioning" the requester asked for — the backfill in §4.2 exists only to
backstop tenants provisioned *before* this change ships.

## 5. API contract

All routes below sit under the existing `pipeline_stages` router, admin-
gated (`require_admin`, same as every other mutating route on this
resource), following `API_CONVENTIONS.md`'s envelope/error shape.

### 5.1 `POST /api/v1/pipeline-stages/batch` — Save

Full-replacement contract, not a diff — deliberately mirrors the existing
`PATCH /pipeline-stages/reorder`'s "always send the complete list"
precedent rather than inventing a separate diff format, since diffing
client-side against a state that might have shifted underneath it is
exactly the kind of thing a full-replacement contract avoids. Array order
*is* the new `sort_order`.

```
POST /api/v1/pipeline-stages/batch
{
  "stages": [
    { "id": "<uuid>", "name": "Contacted" },                 // existing, kept/renamed
    { "name": "Proposal Sent", "is_won": false, "is_lost": false,
      "is_invoice_stage": false, "is_rework_stage": false }, // new — no id
    ...
  ]
}
-> { "data": PipelineStageOut[], "meta": { request_id } }   // final list, in order
```

- Any existing tenant stage **not** present in `stages` by `id` is treated
  as a delete.
- `is_won`/`is_lost`/`is_invoice_stage`/`is_rework_stage` are only read for
  entries with no `id` (new stages) — creation-only, same rule as the
  single-stage `POST`; present-and-ignored (not rejected) on an existing
  entry, matching `PipelineStageUpdate`'s existing exclusion pattern.
- Validated as one unit before anything is written: resulting set must
  still have exactly the existing won/lost-stage invariants
  `delete_stage` already enforces today (at least one `is_won`, one
  `is_lost`, one open stage) — evaluated against the *proposed final list*,
  not stage-by-stage.
- For every id being removed: run `delete_stage`'s existing two checks
  (in use by a deal, in use by an SLA policy). **Any single blocker aborts
  the entire batch** — 409, `VALIDATION_ERROR`-style body listing every
  blocked stage and why, and nothing in the batch is applied (not even the
  unrelated renames/creates) — this is what "all-or-nothing" means for a
  batch this heterogeneous.
- All-or-nothing means one DB transaction: deletes, inserts (fresh UUIDs),
  renames, and `sort_order` reassignment for the survivors, using the same
  two-phase negative-placeholder trick `reorder_stages` already uses to
  avoid the `(tenant_id, sort_order)` unique index colliding mid-update.
- A stage `id` in the payload that doesn't resolve to *this* tenant's row
  is rejected the same way `reorder_stages` already rejects an unknown id
  today (400) — never silently ignored, never actioned against another
  tenant's row.

### 5.2 `POST /api/v1/pipeline-stages/reset-to-default`

```
POST /api/v1/pipeline-stages/reset-to-default
{ "confirm": "RESET TO DEFAULT" }
-> 200 { "data": PipelineStageOut[], "meta": { request_id } }   // fresh default list
-> 409 { "error": { "code": "CONFLICT", "message": "...", "details": [...] } }
```

- The literal `confirm` string is checked server-side too, not just
  disabling a client button — a scripted/replayed call without the exact
  phrase is rejected (400, `VALIDATION_ERROR`) the same way a malformed
  body would be anywhere else in this API. The frontend enforces the
  no-paste typing requirement; the backend enforces that the phrase itself
  is actually present, so this isn't purely a client-side speed bump.
- Loads this tenant's `pipeline_stage_default_snapshots` (§4). If empty
  (shouldn't happen after the §4.2 backfill, but don't trust that
  silently) — 409, distinct message, rather than deleting every stage and
  leaving the tenant with zero.
- Same in-use check as §5.1: every *current* stage not matching the
  snapshot by name is a candidate delete, checked against deals/SLA
  policies. Any blocker aborts the whole reset — current configuration is
  left **completely untouched**, matching `delete_stage`'s existing
  all-or-nothing guard, just evaluated for the whole set up front instead
  of one stage at a time.
- On success, one transaction: delete every current stage, insert fresh
  rows (new UUIDs) copying the snapshot's name/order/flags exactly.

## 6. Multi-tenancy check

- `pipeline_stage_default_snapshots`: standard `tenant_id NOT NULL` +
  `ENABLE`/`FORCE ROW LEVEL SECURITY` + tenant-scoped policy + composite
  `(id, tenant_id)` PK + tenant-leading index — no deviation, no exception
  (unlike `pipeline_stage_templates`, this is real per-tenant data).
- Both new endpoints run through the existing `get_tenant_context` +
  `require_admin` chain — `app.tenant_id` is set from the BFF's validated
  header before either query runs, same as every other mutating route on
  this resource.
- §5.1's per-id validation (reject an id that doesn't resolve to the
  caller's own tenant) is the same defense-in-depth pattern
  `reorder_stages` already established — RLS makes cross-tenant rows
  invisible to the query in the first place, but the explicit check gives
  a clean 400 instead of a silent "not found in this result set" ambiguity.
- Backfill migration (§4.2) runs per-tenant, scoped by `tenant_id` in its
  own `INSERT` — never a cross-tenant bulk operation.

## 7. Task breakdown

1. **Migration**: `pipeline_stage_default_snapshots` table (RLS, index) +
   backfill insert for tenants with zero snapshot rows, from
   `DEFAULT_STAGES`.
2. **Backend**: extend `ensure_default_stages` to also write the snapshot
   the first time it seeds a brand-new tenant's 8 stages; new
   `get_default_snapshot(db, tenant_id)` service read.
3. **Backend**: `batch_update_stages` service fn + schema + `POST
   /api/v1/pipeline-stages/batch` route + tests — happy path; delete
   blocked by deal-in-use; delete blocked by SLA-policy-in-use (whole
   batch rejected, unrelated create/rename in the same batch confirmed
   *not* applied); won/lost-invariant violation rejected; cross-tenant id
   in payload rejected.
4. **Backend**: `reset_to_default` service fn + `POST
   /api/v1/pipeline-stages/reset-to-default` route + tests — happy path
   (recreates snapshot exactly: names, flags, order); blocked by
   deal-in-use; blocked by SLA-policy-in-use (current config confirmed
   unchanged after a blocked attempt); wrong/missing `confirm` phrase
   rejected server-side; tenant-B admin cannot trigger or read tenant-A's
   snapshot/reset.
5. **Frontend**: restructure `PipelineConfigPage.tsx` around
   `draftStages` (locally mutated) vs. `savedStages` (last server truth);
   every existing action (create/rename/delete/reorder) now mutates the
   draft only; `dirty` derived from the two.
6. **Frontend**: **Save** button (enabled only when dirty) → builds the
   §5.1 payload from `draftStages`, POSTs, replaces `savedStages` with the
   response on success, surfaces the 409 blocker list inline on failure
   without touching the draft.
7. **Frontend**: **Reset** button (enabled only when dirty) + a plain
   confirm modal (reusing `PipelinePage.tsx`'s existing custom
   confirm-bar convention, not `window.confirm`, for visual consistency)
   → on confirm, `draftStages = deepCopy(savedStages)`, no API call.
8. **Frontend**: **Reset to Default** button (always enabled) + a
   type-to-confirm modal — text input requiring the exact phrase `RESET TO
   DEFAULT`, `onPaste` calls `preventDefault()` so the field can only be
   filled by typing, Confirm disabled until the typed value matches
   exactly → POSTs §5.2, replaces **both** `draftStages` and `savedStages`
   on success (explicit warning text in the modal that this discards
   unsaved edits too, not just live config), surfaces the 409 blocker list
   without touching either on failure.
9. **Docs**: `DATABASE_SCHEMA.md` gains the new table's row.

## 8. Acceptance criteria

- Loading Pipeline Config with no edits: **Save** and **Reset** are both
  disabled; **Reset to Default** is enabled.
- Creating, renaming, deleting, or reordering a stage in the draft (without
  clicking Save) enables both **Save** and **Reset**; no API call has been
  made for that action yet besides the initial page-load `GET`.
- **Reset**, confirmed: draft reverts to exactly the last-saved state;
  **Save**/**Reset** become disabled again; zero write API calls were made
  by this action.
- **Save** with a batch containing a delete that's blocked (deal or SLA
  policy in use): the whole batch is rejected (409); an unrelated
  create/rename in that same batch is confirmed **not** applied server-side
  (`GET /pipeline-stages` afterward matches pre-Save state exactly); the
  draft in the UI is left exactly as the admin had it, not reset or
  partially cleared.
- **Save** with a valid mixed batch (one create, one rename, one delete,
  full reorder): all four land atomically; the returned list's order
  matches the submitted array order exactly.
- A stage `id` belonging to tenant B included in tenant A's Save payload is
  rejected (400) — never silently dropped, never actioned.
- **Reset to Default**'s Confirm button stays disabled until the typed
  input exactly matches `RESET TO DEFAULT`; the input's content cannot be
  set via paste (keyboard shortcut or right-click menu) — only by typing.
- **Reset to Default**, blocked (a non-default stage is in use by a deal or
  SLA policy): 409; current `pipeline_stages` confirmed completely
  unchanged afterward.
- **Reset to Default**, succeeds: resulting `pipeline_stages` matches the
  tenant's `pipeline_stage_default_snapshots` exactly in name, order, and
  every flag — for a tenant provisioned before this feature shipped,
  matches the `DEFAULT_STAGES`-backfilled snapshot; for one provisioned
  after, matches whatever their actual first-seed snapshot captured.
- Calling `POST /api/v1/pipeline-stages/reset-to-default` with a missing or
  wrong `confirm` value is rejected server-side (400) even with a
  hand-crafted request that never went through the UI.
- A counselor (non-admin) gets 403 from both new endpoints, matching every
  existing mutating route on this resource.
- Tenant B's admin cannot read or trigger a reset against tenant A's
  `pipeline_stage_default_snapshots` rows — enforced by RLS, not just
  omitted from a UI.
