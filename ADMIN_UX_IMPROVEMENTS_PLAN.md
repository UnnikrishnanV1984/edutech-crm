# Admin UX improvements — task/deal owner filter, pipeline Config menu

Covers two of the three items requested: the Mine/Everyone filter
confusion (Tasks and, for consistency, Pipeline — both share the
identical bug) and a new admin-only Config menu for pipeline-stage
management (create/delete/reorder). The third item (a Users menu with
role assignment and user add/remove) is **not** covered here — it
conflicts with this codebase's existing Keycloak-JIT-provisioning
design (role is overwritten from the token claim on every request,
documented in `UserUpdate`'s docstring) and there's no in-app user-
creation path (`registrationAllowed: false`, no invite flow). Routed to
`architect` separately per `CLAUDE.md`'s "new external integration"
gate — not planned here.

Neither of these is in `FEATURES_AND_PLAN.md` under a specific phase;
"Tenant admin console (users, roles, pipeline config)" is listed in §1's
feature set but was never assigned to a phase in §2. Treating this as
an explicit ad-hoc request per this skill's own step 1, since it was
directly asked for — not silently added to a phase that hasn't reached
it.

## 1. Prerequisites check

Phase 4's exit criteria are met (see `FEATURES_AND_PLAN.md`). Neither
piece here depends on Phase 5 — this is a gap-fill in already-shipped
Phase 1/3 surfaces (pipeline stages, task/deal filtering), not new
phase work, so no sequencing blocker applies.

## 2. Affected layers

- **Frontend**: `TasksPage.tsx`, `PipelinePage.tsx` (filter fix);
  `Sidebar.tsx` (new nav item); new `PipelineConfigPage.tsx` (Config
  menu).
- **Backend**: `app/api/pipeline_stages.py` (new POST/DELETE routes,
  new reorder route, admin-gate the mutating routes), `app/services/
  pipeline_stage_service.py` (create/delete/reorder logic),
  `app/schemas/pipeline_stage.py` (new create schema).
- **Database**: none. No new table or column — see §4.
- **Background jobs**: none touched.
- **BFF**: none — generic proxy, no route-specific changes needed
  (confirmed same as Phase 4b's conversion_target_id field).

## 3. Database changes

**None required.** Reordering is handled as an application-transaction
two-phase update against the existing `sort_order` column (§6.3) rather
than a constraint change, and deletion is blocked (409) rather than
soft-disabled, so no new `status` column is needed either. This avoids
`CLAUDE.md`'s "schema change to a table already in production use" gate
entirely — worth stating explicitly since `pipeline_stages` already
holds live tenant data.

## 4. API contract

All new/changed routes are under `/api/v1/pipeline-stages`, following
`API_CONVENTIONS.md`'s existing envelope/error shapes.

### 4.1 Existing routes — tightened, not reshaped

`GET /api/v1/pipeline-stages` and `PATCH /api/v1/pipeline-stages/{id}`
currently have **no role gate at all** — any authenticated tenant user
(including a counselor) can rename a stage or change
`win_probability_pct` today. This is a real, separate gap the
investigation surfaced, not something introduced by this plan. Fix:

- `GET` stays open to all authenticated tenant roles (the Pipeline
  board needs stage names for every role).
- `PATCH` becomes `Depends(require_admin)` — a genuine behavior change
  (a manager/counselor who could previously edit a stage's name will
  get 403 after this ships). Called out explicitly as a deliberate
  fix, not a side effect — flagged in acceptance criteria (§8).

### 4.2 `POST /api/v1/pipeline-stages` (new)

`require_admin`. Request:

```json
{ "name": "Trial Class", "is_won": false, "is_lost": false }
```

- `sort_order` is **not** client-settable on create — always appended
  at `max(sort_order) + 1` for the tenant, matching
  `DEFAULT_STAGES`' seeding convention. Reordering afterward uses §4.4.
- `is_won`/`is_lost` are settable **only at create time**, matching the
  existing `PipelineStageUpdate` schema's deliberate exclusion of them
  from PATCH (`pipeline_stage.py:7-16`) — that exclusion exists because
  later phases (forecast, conversion-signal sends, escalation win/loss
  logic) read `is_won`/`is_lost` as a stable signal; this plan doesn't
  reopen that decision, just extends it to say "stable after creation,"
  not "stable forever, including creation."
- Response: `PipelineStageOut` (existing shape), `200`.
- `409 CONFLICT` if `name` collides with an existing stage for the
  tenant (existing unique index `uq_pipeline_stages_tenant_name`
  already enforces this — just needs the existing `IntegrityError` →
  409 translation `pipeline_stages.py:37-41` already has, reused for
  POST).

### 4.3 `DELETE /api/v1/pipeline-stages/{id}` (new)

`require_admin`. No request body.

- `404 NOT_FOUND` if the stage doesn't exist for this tenant.
- `409 CONFLICT` ("Stage is in use") if any `deals.stage_id` or
  `sla_policies.stage_id` references it — checked explicitly before
  delete, not left to a raw FK violation (matches this codebase's
  existing IntegrityError→409 translation convention rather than
  leaking a DB error).
- `409 CONFLICT` ("Cannot delete the only won/lost stage") if this is
  the tenant's **last** `is_won = true` stage (or last `is_lost = true`
  stage) — deleting it would silently break Phase 4's forecast
  (`Σ deals × win_probability_pct`) and Phase 4b's conversion-signal
  trigger (`ARCHITECTURE.md` §7d fires on `is_won` transitions), which
  both assume at least one such stage exists. Not caught by any DB
  constraint — an explicit application-level check.
- **Known, documented gap, not solved here**: `workflow_rules.actions`/
  `conditions`/`trigger_config` are tenant-scoped JSONB and can
  reference a `stage_id` (e.g. a `change_stage` action's
  `to_stage_id`, or an `eq`/`in` condition on `stage_id`) with no FK to
  catch a dangling reference after delete. A rule referencing a deleted
  stage will fail or silently no-op the next time it evaluates
  (`_execute_action`'s `change_stage` branch would raise `ValueError`
  on `uuid.UUID(config["to_stage_id"])` resolving to nothing, which
  `_run_one_rule`'s existing retry-then-fail path already handles
  safely — it won't corrupt data, just fail that rule's run). Flagged,
  not fixed — a full fix means scanning `workflow_rules` JSONB for
  stage references before allowing delete, which is a larger scope
  than "add a delete button."
- Response on success: `200`, empty `data: {}`.

### 4.4 `PATCH /api/v1/pipeline-stages/reorder` (new)

`require_admin`. Request — the full ordered list of stage ids for the
tenant:

```json
{ "stage_ids": ["uuid-1", "uuid-2", "uuid-3"] }
```

- `400 VALIDATION_ERROR` if the list doesn't contain exactly the set of
  stage ids currently belonging to the tenant (no partial reorders — a
  partial list would leave `sort_order` gaps/collisions undefined).
- On success: rewrites `sort_order` for every listed stage to its index
  in the list (0-based or 1-based, either is fine — service-layer
  detail). See §6.3 for how this avoids the `(tenant_id, sort_order)`
  unique-index collision without a constraint change.
- Response: `PipelineStageOut[]` in the new order, `200`.
- Registered **before** `/{stage_id}` in the router (or with a distinct
  path segment as shown) so FastAPI doesn't try to parse `"reorder"` as
  a UUID path param — a real routing-order pitfall worth calling out
  for `feature-builder`.

## 5. Task/deal owner filter fix

No backend change needed — confirmed during investigation that
`GET /api/v1/tasks`'s `assignee_id` param already composes correctly
with `RowScope` for every role (an admin's explicit `assignee_id=X`
already isn't further restricted, since `RowScope.owner_ids=None` for
admin means no additional filter is applied). This is a frontend-only
fix, plus the identical fix mirrored onto `PipelinePage.tsx`'s deal
owner filter, which has the same control and the same underlying
`RowScope` mechanism.

**Root cause of the confusion** (both pages): a single Mine/Everyone
toggle button renders identically for all three roles, but:
- For **counselor**, `RowScope.owner_ids = [self.id]` always applies
  server-side regardless of what the frontend sends — so "Everyone" is
  currently a no-op that still only shows their own items. Confusing:
  the button implies a choice that doesn't exist.
- For **manager**, `RowScope.owner_ids = [self, ...direct_reports]` —
  "Everyone" actually means "my team," not literally everyone in the
  tenant. Confusing: the label overpromises.
- For **admin**, "Everyone" is accurate (no RowScope restriction).

**Fix, per role:**
- **Counselor**: remove the toggle entirely. Their task/deal list is
  always "mine" — nothing to choose, so nothing to show. Matches the
  explicit ask ("the user should be able to see only their tasks").
- **Manager**: keep a two-state toggle, relabeled `Mine` / `My team`
  (not "Everyone") — accurately describes what `RowScope` actually
  returns for a manager. No backend change; purely a label fix plus
  keeping the existing `assignee_id`-omitted-means-team-scoped
  behavior.
- **Admin**: replace the toggle with **`Mine` button + a dropdown**
  (`Everyone` | each tenant user by name, sourced from the existing
  `useUsers()`/`listUsers()` hook already used elsewhere in the app as
  a picker). Selecting a specific user sets `assignee_id=<their id>`;
  `Everyone` omits `assignee_id` entirely (unchanged request shape).
  `Mine` is a shortcut that's equivalent to selecting the admin's own
  name in the dropdown — implemented as one control state, not two
  independent ones, so they can't disagree.

Both `TasksPage.tsx` and `PipelinePage.tsx` get the same three-way
role-conditional rendering; behavior is otherwise identical to how each
page already wires `assignee_id`/`owner_id` into its list call today.

## 6. Multi-tenancy check

- Every new route depends on `get_tenant_context` (existing pattern) —
  `tenant_id` only ever comes from the BFF's forwarded, Keycloak-
  validated header, never a request body/param (`CLAUDE.md` rule 7).
  Confirmed unchanged by this plan.
- `POST`/`DELETE`/`reorder` all filter/insert scoped to
  `context.tenant.id` — a create can't target another tenant, a delete
  can't remove another tenant's stage (404 if the id doesn't belong to
  the caller's tenant, matching the existing `get_stage` lookup
  pattern), and reorder's "list must match the tenant's exact stage
  id set" check (§4.4) is itself a tenant-isolation guard — an admin
  can't slip another tenant's stage id into their own reorder request
  and have it silently accepted (it'd fail the set-membership check,
  not attempt a cross-tenant write).
- The admin-tightening of `PATCH` (§4.1) doesn't touch RLS — it's an
  application-layer role gate, same category as every other
  `require_admin` route in this codebase (`REQUIREMENTS.md` §1.3 — RBAC
  is enforced at the application layer, not via additional RLS
  policies). Not an RLS change, so `CLAUDE.md`'s RLS-weakening gate
  doesn't apply (and this is a *tightening*, not a weakening, of
  authorization, if anything the opposite direction that gate cares
  about).
- Reorder's two-phase update (§6.3 below) stays within one DB
  transaction, scoped to `tenant_id` throughout — no window where a
  concurrent request from a different tenant could observe or affect
  the intermediate negative-placeholder state (transaction isolation,
  and the negative values are on rows already filtered to this
  tenant's ids).

### 6.3 Reorder implementation detail (why no migration is needed)

`(tenant_id, sort_order)` has a live unique index
(`uq_pipeline_stages_tenant_sort_order`, migration `0003`). A naive
single-row `sort_order` PATCH can collide with whatever stage currently
holds the target value (confirmed during investigation — this is why
`pipeline_stages.py`'s existing `IntegrityError` → 409 handler exists
at all today). Two ways to make a full-list reorder atomic without
transient collisions:

1. Make the unique index `DEFERRABLE INITIALLY DEFERRED` — a schema
   change to a table already in production use, `CLAUDE.md`-gated,
   needs `architect`. Rejected for that reason alone, even though it's
   otherwise the simpler fix.
2. **Two-phase update within the existing (non-deferred) constraint,
   in one transaction** (chosen): first pass sets every listed stage's
   `sort_order` to a unique negative placeholder (`-1, -2, -3, ...`) —
   safe, since no stage's real `sort_order` is ever negative, so no
   collision with untouched rows or with each other as they're written
   one at a time in list order. Second pass then sets each stage's
   final positive `sort_order` in any order — safe, because after
   phase one, zero rows for this tenant hold a positive value, so no
   write in phase two can collide with a not-yet-updated sibling.
   Needs no constraint change, no migration — purely a service-layer
   `update_stage`-style function doing two loops of `UPDATE` in one
   `db.begin()` block.

## 7. Task breakdown

1. `app/schemas/pipeline_stage.py` — add `PipelineStageCreate`
   (`name`, `is_won=False`, `is_lost=False`) and `PipelineStageReorder`
   (`stage_ids: list[uuid.UUID]`).
2. `app/services/pipeline_stage_service.py` — `create_stage()`
   (append at `max(sort_order)+1`), `delete_stage()` (the two 409
   checks from §4.3), `reorder_stages()` (the two-phase update from
   §6.3).
3. `app/api/pipeline_stages.py` — wire the three new routes, add
   `require_admin` to the existing `PATCH`. Tests: admin-only gate on
   PATCH (a counselor/manager token now gets 403), create dedupes name
   (409), delete blocks when referenced by a deal (409) and when it's
   the last `is_won` stage (409), delete succeeds for an unused
   non-`is_won`/`is_lost` stage, reorder rejects a partial/foreign id
   list (400) and correctly rewrites `sort_order` for a full valid
   list, reorder is tenant-isolated (tenant B's stage id in tenant A's
   reorder request is rejected, not silently written).
4. Frontend: `frontend/src/api/pipelineStages.ts` — add
   `createPipelineStage`, `deletePipelineStage`, `reorderPipelineStages`
   calls; extend the `PipelineStage` type with nothing new (response
   shape unchanged from existing `PipelineStageOut`).
5. Frontend: new `frontend/src/pages/PipelineConfigPage.tsx` — list
   current stages (drag-to-reorder, matching this app's existing
   Kanban drag interaction in `PipelinePage.tsx` for a consistent
   pattern rather than inventing a new one), inline create form,
   delete button per row (disabled/tooltipped when the DELETE call
   would 409 — read the error response rather than guessing ahead of
   time which stages are deletable).
6. `Sidebar.tsx` — add a `CONFIG` group (or a single `/pipeline-config`
   item under the existing `ADMIN` array — simpler, matches how SLA
   policies/Integrations already sit as flat items there rather than a
   further sub-group) gated by the existing `showAdmin` check.
7. `TasksPage.tsx` / `PipelinePage.tsx` — role-conditional filter
   control per §5 (no toggle for counselor, relabeled Mine/My-team
   toggle for manager, Mine-button-plus-user-dropdown for admin).
   Frontend test: each role sees the expected control (or none).

## 8. Acceptance criteria

- A counselor sees no Mine/Everyone control on Tasks or Pipeline at
  all — their list is always their own items.
- A manager sees `Mine`/`My team` (not "Everyone") and "My team" shows
  exactly themself + direct reports, never the whole tenant.
- An admin sees `Mine` plus a dropdown of every tenant user;
  selecting a specific user shows only that user's items; `Everyone`
  shows the whole tenant's items.
- A manager or counselor token calling `PATCH /api/v1/pipeline-stages/
  {id}` now gets `403 FORBIDDEN` (a deliberate behavior change from
  today, per §4.1) — an admin token still succeeds.
- Creating a stage with a duplicate name for the same tenant returns
  `409`; a different tenant can reuse the same name (existing index is
  tenant-scoped, unchanged).
- Deleting a stage referenced by an existing deal returns `409` and the
  stage is not deleted; deleting the tenant's only `is_won` stage
  returns `409` even if no deal currently references it.
- Deleting an unused, non-`is_won`/`is_lost` stage succeeds and it no
  longer appears in `GET /api/v1/pipeline-stages`.
- Reordering a tenant's full stage list persists the new `sort_order`
  values with no `IntegrityError` at any point, verified by reordering
  twice in a row (exercises the collision the naive approach would hit
  on the second call).
- Submitting a reorder list containing another tenant's stage id (or
  missing one of the caller's own stages) returns `400` and changes
  nothing.
