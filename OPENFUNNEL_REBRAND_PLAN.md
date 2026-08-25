# OpenFunnel rebrand + design system — phased plan

Companion to the architect gap analysis (this session, 2026-08-25) comparing
`design_handoff_crm_wireframes/` against the current app. Not resolving any
new design questions here — this is the phase breakdown per
`feature-planner`'s own process, sized at the **phase** level. Each phase
below gets its own commit-level task breakdown from a separate
`feature-planner` pass when that phase is actually started, same rhythm as
`PIPELINE_AND_REVENUE_PLAN.md` was for Phase 6.

## 1. Located

Not yet in `FEATURES_AND_PLAN.md`. Proposed as **Phase 7**, sub-phased 7a–7i
below. Recommend appending a short pointer to `FEATURES_AND_PLAN.md`'s phase
list once this plan is approved (done in the same change as this doc).

## 2. Prerequisites check

None of the sub-phases below touch tables Phase 5 (infra hardening) or
Phase 6 (invoicing) are mid-flight on, except where noted per-phase. Same
"disjoint tables and layers" reasoning Phase 6 already used against Phase 5
applies here — this can run independently of both.

## 3. Cross-cutting notes (apply to every phase below)

- **Multi-tenancy**: identical behavior pooled vs. single-tenant throughout,
  except Phase 7h (Branding), which is explicitly *per-tenant by design* —
  that's the entire point of white-labeling. No phase here introduces a new
  way of trusting `tenant_id` — every new/changed route still goes through
  `get_tenant_context` + the BFF's validated-header chain, same as every
  existing route.
- **Token/class naming mismatch, found while reading the wireframe files
  directly** (worth stating once, not per-phase): `tokens.css` (the palette)
  and `styles.css` (the component classes) use **two different variable
  naming schemes** — `tokens.css` defines `--p`/`--ink`/`--ac`/`--ln`/etc.,
  but `styles.css`'s own classes (`.btn`, `.card`, `.tag`, `.table`, ...)
  reference a *different* set (`--color-bg`/`--color-text`/`--color-accent`/
  `--font-heading`/`--space-1`/...) with its own standalone `:root` block
  (meant for opening the wireframe file standalone, not for merging as-is).
  Neither file's variable names should be adopted literally. Per the
  wireframe README's own instruction ("mapped onto the app's existing `--*`
  variables"), Phase 7a's job is: keep this app's *existing* token names
  (`--accent`, `--surface`, `--text-muted`, `--radius`, `--space-*`, ...
  already used consistently across every page), and remap only their
  *values* to match `tokens.css`'s palette + `styles.css`'s spacing/radius/
  shadow scale. `styles.css`'s component classes (`.btn-primary`, `.tag-
  accent`, `.card`, ...) are a *reference for restyling* this app's existing
  `Button`/`Badge`/`Card`/`EmptyState` React components' internal styles —
  not a new global CSS class system to introduce alongside them. Introducing
  a second styling methodology (global classes) next to the existing
  component+inline-`var(--token)` convention would fragment the codebase for
  no benefit.
- **Fonts**: `styles.css` loads Cormorant Garamond + Lora via a Google Fonts
  `@import`. Confirm at Phase 7a implementation time whether this app's CSP/
  offline-dev requirements allow a Google Fonts fetch or need the font files
  vendored locally — not decided here, flag it in that phase's own task
  breakdown.
- **List states**: the wireframe README requires four states per list —
  loading (skeleton), empty (distinct copy for never-any vs. filtered-none),
  populated, error (inline retry). Confirm each restyled/rebuilt list in
  every phase below actually has distinct empty-vs-filtered-empty copy;
  several current pages collapse these into one `EmptyState` today — closing
  that gap is part of the restyle work, not a separate phase.

## 4. Phase breakdown

### Phase 7a — Rebrand + design token foundation
**Blocks every other visual phase below — must land first.**

- **Affected layers**: frontend only (`frontend/src/index.css`, the shared
  component set — `Button`, `Card`, `Badge`, `EmptyState`, `Avatar`,
  `ThemeToggle` — plus `Sidebar.tsx`, `index.html`'s `<title>`), docs
  (`README.md` top matter, doc headers referencing "EdTech CRM").
- **Database / API**: none.
- **Multi-tenancy check**: N/A — no data path touched.
- **Task breakdown** (phase-level):
  1. Remap `index.css`'s existing token *values* to `tokens.css`'s light+dark
     palette (`--p`→paper/ground role already served by `--surface`/`--bg`
     equivalents, `--ac`→`--accent`, etc. — exact existing-name mapping table
     is this phase's own first task, not pre-decided here).
  2. Add Cormorant Garamond (headings) + Lora (body) per the font-loading
     decision above; adjust the radius scale (pills 999px, cards 10px, outer
     frames 14px, controls 8px) and spacing scale to match.
  3. Restyle `Button`/`Card`/`Badge`/`EmptyState`/`Avatar` against
     `styles.css`'s `.btn`/`.card`/`.tag` definitions (values only, per the
     naming-mismatch note above) — accent as stroke/outline, never a filled
     block; primary buttons accent-outlined per the README.
  4. Rebrand: `Sidebar.tsx`'s hardcoded "EdTech CRM" string →
     "OpenFunnel"; `index.html` `<title>`; `README.md` top heading; doc
     headers that display the product name in prose. **Explicitly excluded**:
     the `edutech-crm` repo folder name, Docker image names, the
     `edutech_crm` Postgres database name, the `edutech-crm` Keycloak realm
     slug, and tenant slugs like `tenant-a` — all internal identifiers,
     unchanged. If a full internal rename is ever wanted, that's a separate,
     later, infra-only decision — not bundled here.
  5. Verify dark mode still holds — `tokens.css` ships a full dark ramp,
     confirm every remapped token has both light and dark values (this app
     already supports a theme toggle; don't regress it).
- **Acceptance criteria**:
  - Every existing page renders with the new palette/type in both light and
    dark with no hardcoded color/font left over from the old palette.
  - Sidebar, browser tab, and `README.md` all say "OpenFunnel"; no
    internal identifier (folder, image, DB name, realm slug) changed.
  - A visual pass confirms accent is never used as a solid fill on a
    primary button (stroke/outline only, per the design system's own rule).

### Phase 7b — Configurations shell + Users & roles — shell done, role/status editing deferred (2026-08-25)
Depends on 7a (visual). Backend work (Users & roles) has no visual
dependency and could be built in parallel with 7a if useful, but the tab
shell needs 7a's component restyle to look right.

**Built**: the tabbed `ConfigurationsPage.tsx` shell (SLA/Integrations/
Pipelines/Branding/Users & roles, tab state in the `?tab=` query param),
`Sidebar.tsx`'s Admin group collapsed to one "Configurations" link, and
the three old routes now redirect (`/sla-policies` → `?tab=sla`, etc.).
`SlaPoliciesPage`/`IntegrationsPage`/`PipelineConfigPage` moved in with
only their outer `<h1>`/wrapper stripped (the shell owns that once) —
no other functional change. Users & roles ships **read-only** (name,
email, role, manager, territory, status) — product decision, explicitly
deferring the section below rather than silently skipping it.

**Deferred, not built**: role/status editing, and the `backend-admin`
Keycloak confidential client + secrets it requires. Confirmed with the
user before starting (2026-08-25): provisioning new credentials is a
big enough decision to not fold into a shell-consolidation pass. The
design below is still the plan for when that's picked up — nothing here
was invalidated, just not started.

- **Affected layers**: frontend (new tabbed `ConfigurationsPage.tsx`
  replacing the four separate `/sla-policies`, `/integrations`,
  `/pipeline-config` routes + a new Users&roles tab; `Sidebar.tsx`'s Admin
  group collapses to one "Configurations" link), backend (`PATCH
  /api/v1/users/{id}` gains `role`/`status`), Keycloak (new confidential
  client per `ARCHITECTURE.md` §4a), Docker Compose + Helm (new
  `KEYCLOAK_ADMIN_CLIENT_ID`/`KEYCLOAK_ADMIN_CLIENT_SECRET` secrets).
- **Database**: none new — `users.status` already exists, unused by any
  route today; this phase is the first consumer.
- **API contract**: `PATCH /api/v1/users/{id}` — extend the existing
  `UserUpdate` schema with optional `role: str` and `status: "active" |
  "disabled"`, admin-only. Response shape unchanged
  (`{"data": UserOut, "meta": {...}}`). Full request-flow design already
  written in `ARCHITECTURE.md` §4a — build directly against it (Keycloak
  Admin API call first, local `users` row only updated on that call's
  success, never speculatively).
- **Multi-tenancy check**: §4a's own note already covers this — the
  service-account technically has cross-tenant Admin API reach within one
  shared Keycloak realm, so the *application-layer* re-confirmation that
  `user_id` belongs to `context.tenant.id` (already how the existing route
  works via `get_user(db, tenant_id, user_id)`) is the actual boundary, not
  Keycloak's realm scoping. No new tenant-trust mechanism introduced.
- **Task breakdown** (phase-level):
  1. Keycloak: add the `backend-admin` confidential service-account client
     to `realm-export.json`, grant `manage-users`; wire the two new secrets
     into `.env`/Compose/Helm values.
  2. Backend: extend `PATCH /api/v1/users/{id}` per §4a; tests for
     Keycloak-call-fails-so-local-row-untouched, cross-tenant user id
     rejected, non-admin 403.
  3. Frontend: new Users&roles tab (list users, role dropdown, activate/
     deactivate toggle) — no user-creation UI, per §4a's explicit scope cut.
  4. Frontend: consolidate `SlaPoliciesPage`/`IntegrationsPage`/
     `PipelineConfigPage` content into one tabbed shell component, routing
     `/configurations` (or similar) with tab state in the URL; update
     `Sidebar.tsx`'s Admin group to one link. `PipelineConfigPage`'s
     recently-built Save/Reset/Reset-to-Default UI (this session) moves in
     as-is — no functional change, just relocated under the Pipelines tab.
- **Acceptance criteria (role/status editing — still pending, not started)**:
  - An admin can change another user's role and see it reflected
    immediately, without waiting for that user's next login.
  - If the Keycloak Admin API call fails, the local `users.role`/`status`
    column is confirmed unchanged (not written speculatively).
  - A disabled user drops out of `RowScope`/team-lookup results immediately.
  - A tenant-A admin cannot change a tenant-B user's role/status by id
    (404, not 403 — consistent with this codebase's established
    out-of-scope-looks-like-missing convention).
- **Acceptance criteria (shell — met)**:
  - All five Configurations tabs (SLA, Integrations, Pipelines, Branding,
    Users & roles) are reachable from one nav entry; the three old
    standalone routes redirect rather than 404.

### Phase 7c — Pipeline: Table view + filters
Depends on 7a.

- **Affected layers**: frontend only (`PipelinePage.tsx` gains a Board/Table
  toggle and Lead-source/Course/SLA-state filter controls alongside the
  existing owner filter); backend — `GET /api/v1/deals` likely already
  supports enough filter params for this (confirm at implementation time;
  add any missing query param rather than a new endpoint).
- **Database**: none expected.
- **Multi-tenancy check**: reuses the existing `RowScope`-scoped deals list
  endpoint — no new trust path.
- **Task breakdown**:
  1. Confirm `GET /api/v1/deals`'s existing filter params cover lead-source/
     course/SLA-state; add whichever are missing (deal already carries
     `course_id`; SLA state comes from the existing `sla_states` join
     `report_service.py` already knows how to do for `my-queue`).
  2. Table view: same filtered deal set, tabular layout (Name/Course/Stage/
     Owner/SLA/days-in-stage), reusing `Contacts`' eventual table
     conventions from 7d where they overlap.
  3. Filter strip UI (Mine/Everyone toggle already exists via `OwnerFilter`;
     add lead-source, course, SLA-state, Board/Table).
- **Acceptance criteria**:
  - Switching Board↔Table preserves the active filter set.
  - An SLA-state filter of "breached" shows only deals whose current
    `sla_states` row is breached — cross-checked against the Board view's
    own SLA pill for the same deals.

### Phase 7d — Contacts: bulk actions
Depends on 7a. Independent of 7c.

- **Affected layers**: frontend (`ContactsListPage.tsx` gains row selection
  + a toolbar that swaps in place for bulk mode), backend (bulk-assign-owner
  and bulk-flag-follow-up need either a new batch endpoint per contact-id
  list, or N sequential calls to existing single-contact endpoints —
  decide at implementation time; given this session's Pipeline Config batch
  endpoint precedent, an all-or-nothing batch endpoint is the safer default
  if partial-failure semantics matter here).
- **Database**: none new.
- **API contract**: candidate — `POST /api/v1/contacts/bulk-assign-owner`,
  `POST /api/v1/contacts/bulk-flag-follow-up`, both `{contact_ids:
  uuid[], ...}` → confirm per-contact scope (`RowScope`) before acting on
  each id, same as every other mutating route.
- **Multi-tenancy check**: every `contact_id` in a bulk payload must be
  re-verified against `context.tenant.id` (and `RowScope` for non-admins)
  before acting — a bulk endpoint is a wider attack surface for exactly the
  cross-tenant-id-smuggling class of bug this session's Pipeline Config
  batch endpoint was built to guard against; reuse that pattern.
- **Task breakdown**:
  1. Backend: bulk-assign-owner endpoint + tests (cross-tenant id rejected,
     out-of-scope id for a non-admin rejected).
  2. Backend: bulk-flag-follow-up endpoint (creates one `follow_up_flags`
     row per contact) + tests.
  3. "Add task" bulk action: confirm whether this needs a new endpoint or
     can reuse the existing per-contact task-create endpoint N times from
     the frontend — bulk task creation has weaker atomicity requirements
     than owner reassignment, a sequential loop may be acceptable.
  4. Frontend: selection state, toolbar swap, per-action confirmation.
- **Acceptance criteria**:
  - Selecting contacts across a paginated list and bulk-assigning owner
    updates exactly the selected set, no others.
  - A bulk payload containing a contact id outside the caller's `RowScope`
    is rejected for that id without silently skipping it unnoticed — the
    response names which ids failed and why.

### Phase 7e — Escalations: resolve drawer, counters, snooze
Depends on 7a. This is a **schema change to a production table**
(`escalations`) — architect pass done (2026-08-25), design below is
approved, not a sketch.

- **Affected layers**: frontend (`EscalationsPage.tsx` gains counters,
  status filter pills, and a right-anchored resolve drawer with radio
  outcomes — same `SlideOverPanel` pattern as create-contact/create-task),
  backend (`escalation_service.py` gains snooze + a direct `open→resolved`
  transition; `reassign_to`/`resolution_note` already exist and mostly just
  need a frontend UI), a new small Celery module
  (`app/workers/escalations.py`).
- **Database** (migration `0028`): `escalations` gains
  `snoozed_until TIMESTAMPTZ NULL` and `was_reopened BOOLEAN NOT NULL
  DEFAULT false`; `escalations_status_check` gains `'snoozed'`; a partial
  index `idx_escalations_snoozed_until ON escalations (tenant_id,
  snoozed_until) WHERE status = 'snoozed'` serves the expiry scan (leads
  with `tenant_id` per the standard rule, and the scan is per-tenant same
  as `dispatch_sla_computation`). `was_reopened` exists because
  `reassign_to`'s handler already clears `acknowledged_at` back to `NULL`
  on reassignment, so there's no way to reconstruct "was this ever
  reopened" from current columns alone — same shape as `invoices
  .was_reworked` (migration `0026`).
- **Transition logic**: `_ALLOWED_TRANSITIONS` gains a direct
  `"open": {..., "resolved"}` edge (REQUIREMENTS.md §4.2: "Manager
  acknowledgement should be fast... a single action" — the drawer's
  "Contacted — close" outcome shouldn't force two round trips) and
  `{"open", "acknowledged"}: {"snoozed"}`. If a `resolved` transition fires
  while `acknowledged_at` is still `NULL`, set it to the same timestamp as
  `resolved_at` so a resolved row is never missing that field. `snoozed →
  open` is not exposed as a manual transition at all — only
  `app/workers/escalations.py`'s expiry scan sets it, using
  `WHERE snoozed_until <= now()` evaluated by Postgres, not Python's clock
  (the clock-skew bug class `report_service.resolve_period` already hit
  twice). Also fixes a real bug found while designing this: `resolution_note`
  was only applied inside the `if status is not None` branch, so a
  reassign-only PATCH silently dropped its note — moved outside that branch.
- **API contract**: `EscalationUpdate` gains `snoozed_until: datetime |
  None`, required exactly when `status == "snoozed"` (mirrors
  `EscalationCreate`'s existing exactly-one-of validator style);
  `status` now also accepts `"snoozed"`. `EscalationOut` gains
  `snoozed_until`, `was_reopened`. `GET /api/v1/escalations` gains an
  optional `status` filter query param. New `GET /api/v1/reports/escalations`
  (cache-aside, same pattern as every other `report_service.py` function)
  returns `{open, breaching_within_1h, avg_resolve_minutes, reopened}`.
- **Scope subtlety (why this needed an architect pass, not just a
  migration)**: the counters endpoint needs *two different* scope axes,
  not one. `open`/`avg_resolve_minutes`/`reopened` are escalations-table
  metrics scoped the same way `GET /escalations` already scopes —
  `assigned_to` equal to the caller (a manager only ever sees escalations
  assigned directly to them; this is deliberately narrower than
  `RowScope`'s team-expansion, since `assigned_to` is never a counselor
  id, so broadening it the `RowScope` way would be a no-op that looks
  like it does something). `breaching_within_1h` is a leading indicator
  over `sla_states`/`deals` — a fundamentally different axis, owner-scoped
  the way `get_sla_compliance` already scopes (`RowScope`: self + direct
  reports), because it's about the manager's *team's* deals, not about
  who an escalation happens to be assigned to. The endpoint takes both
  scope inputs and applies each to its own sub-query.
- **Task breakdown**:
  1. ~~`architect` pass on the snooze schema sketch~~ — done, see above.
  2. Migration `0028` + `escalation_service.py` changes (snooze,
     direct-resolve transition, `was_reopened`, `resolution_note` fix).
  3. `app/workers/escalations.py` (expiry scan) + beat schedule entry.
  4. `report_service.get_escalation_summary` for the counters.
  5. Frontend: counters row, status filter pills, resolve drawer (radio:
     Contacted-close / Reassign owner / Snooze until…, note field,
     Cancel/Resolve — button label reflects the chosen outcome).
- **Acceptance criteria**:
  - A snoozed escalation automatically reopens (status → `open`,
    `snoozed_until` cleared) once `snoozed_until` passes, without any user
    action, verified via the background job's own test.
  - The "Breaching within 1h" counter matches a direct query against
    `sla_states` for the same tenant/team — no drift between the displayed
    count and the underlying data.
  - A manager cannot see another manager's assigned escalations by any
    combination of status filter or the new counters endpoint (tenant
    isolation + scope test).
  - Reassigning an escalation still records its note (regression test for
    the `resolution_note` fix above).

### Phase 7f — Follow-ups: kanban queue
Depends on 7a. Independent of 7e (confirmed **not** sharing a backend
mechanism with Escalations' snooze — see below).

- **Affected layers**: frontend only. `follow_up_flags` already has
  `remind_on DATE` — "snoozing" a follow-up flag is just a `PATCH` moving
  `remind_on` later, reusing the field that already exists. **No schema
  change**, unlike Phase 7e — despite the wireframe using "Snooze" as a
  label on both screens, the two features are backed differently: follow-
  ups already had a reschedulable date, escalations didn't.
- **Database / API**: none new — `PATCH /api/v1/follow-up-flags/{id}`
  already accepts field updates (confirm `remind_on` is one of them; add it
  if not, a one-line schema change, not architect-gated since it's widening
  an existing mutable field, not a structural change).
- **Multi-tenancy check**: N/A, no new route.
- **Task breakdown**:
  1. Confirm/extend `FollowUpFlagUpdate` to accept `remind_on`.
  2. Frontend: four-column board (Overdue/Due today/This week/Snoozed) —
     bucketing is a pure function of `remind_on` vs. today, computed
     client-side from the existing list response, same as Tasks' existing
     Overdue/Today/Upcoming grouping.
  3. Inline card actions: Reason (display only, already a field), Snooze
     (opens a small date picker, PATCHes `remind_on`), Done (existing
     resolve action).
- **Acceptance criteria**:
  - Snoozing a flag moves it to the correct column based on the new
    `remind_on` value with no page reload.
  - The underlying flag table (below the board, per the wireframe) reflects
    the same data with no drift.

### Phase 7g — Workflow rule builder — done (2026-08-25)
Depends on 7a. Fully independent of every other phase.

- **Confirmed at implementation time**: `workflow_rules.conditions`/
  `actions` JSONB already covered everything the builder needs (field/op/
  value condition rows, typed per-action config) — no schema change. The
  live engine's condition-matching helpers (`_matches_conditions`/
  `_load_condition_fields` in `app/workers/rules.py`) were promoted to
  public functions on `workflow_rule_service.py`
  (`matches_conditions`/`load_condition_fields`/`load_deal`/`load_contact`)
  so the new read-only test-run path reuses the *exact* logic the live
  engine runs, rather than a second implementation that could drift; the
  worker module now imports them back.
- **API contract (built)**:
  - `POST /api/v1/workflow-rules/test-run` — takes a draft rule body
    (`trigger_type`/`trigger_config`/`conditions`, no `id`, works before
    saving) and returns `{candidates_checked, matched: [{type, id,
    label}]}` against a sample of the tenant's own recent/currently-
    eligible records (last 20 per trigger type), executing zero actions.
  - `GET /api/v1/workflow-rules/runs` — paginated run history,
    `?rule_id=` optional, joined to the rule's name so the UI never N+1s;
    visibility mirrors `GET /api/v1/workflow-rules` exactly (non-Admin
    only sees runs for rules they created or that are active). Added
    beyond the original sketch — needed for the "Run history" button
    (not explicitly scoped here originally, but required to make it
    "usable" rather than decorative).
  - `PATCH /api/v1/workflow-rules/{id}` unchanged (admin-only edit) — the
    builder's Save routes there for edits, `POST /workflow-rules` for new
    rules (defaults an Admin's save straight to `active`, closing a
    pre-existing gap where an Admin-created rule had no UI path off
    `draft` — `decide_rule` already supported that transition, it was
    just never exposed).
- **Frontend (built)**: `WorkflowRuleBuilder.tsx` (condition rows scoped
  to the selected trigger's real fields — `lead_source` for
  contact-sourced triggers, `stage_id`/`course_id` for deal-sourced ones,
  none for `task_overdue` since the engine has no matchable fields for it
  either — same limitation, not test-run-only), ordered numbered action
  cards, a client-side plain-English preview, and a Test run button.
  `WorkflowRunHistoryPanel.tsx` for the history view. `send_message`
  stays visibly disabled in the action picker — no backing execution path
  existed before this phase and still doesn't, unchanged from
  `CreateWorkflowRulePanel.tsx` (now deleted, fully superseded).
- **Acceptance criteria**: met — Test run against an unsaved draft rule
  shows real matching contacts/deals from the caller's own tenant and
  writes zero `workflow_runs` rows (regression-tested explicitly); the
  plain-English preview updates live with no save required.

### Phase 7h — Branding / white-label — logo + header shipped, rest planned (2026-08-26)
Depends on 7a (the branding admin screen itself needs the restyled
component set). The remainder of this phase (draft/publish, versioning,
palette/typeface, favicon, contrast check, live preview, custom domain,
and honest preview-only handling of the Login/Email/PDF surfaces this app
doesn't have yet) is planned in full in `BRANDING_FULL_SYSTEM_PLAN.md` —
not built yet, and gated on an `architect` pass per that doc's own
CLAUDE.md-required flag (schema change to a table already in production
use, plus a new table).

**Scope cut, confirmed with the user before starting the first pass**: it built
the part actually asked for — logo + header image upload, applied
immediately — and explicitly skipped the wireframe's fuller system
(color/typeface pickers, contrast check, custom domain, App/Login/Email
live-preview tabs, "where branding appears" checklist, draft/publish
workflow, version history). None of those were requested, and the
login-screen backdrop specifically still has nowhere real to plug into
(this app has no in-app login screen — confirmed, PKCE redirect flow,
`frontend/src/auth/` has no login page component — so a Keycloak
login-theme customization stays a separate, later, architect-approved
follow-up if ever picked up). No draft/publish step exists — an upload
takes effect the moment it's confirmed.

- **Affected layers**: frontend (`BrandingTab.tsx` — two upload wells;
  `Sidebar.tsx` renders the result: header lockup if set, else logo +
  tenant name, else the plain "OpenFunnel" wordmark), backend (new
  table + asset storage + fetch/upload/confirm endpoints), no BFF
  change (the existing generic `/api/v1/*` proxy already covers it).
- **Database** (migration `0029`): `tenant_branding` — same
  one-row-per-tenant pattern as `tenant_sla_settings` (composite
  `(id, tenant_id)` PK + unique index on `tenant_id`, not a different PK
  shape), storing only `logo_s3_key`/`header_image_s3_key`. Asset bytes
  reuse the same S3/MinIO bucket `documents` already uses, not a second
  storage mechanism.
- **API contract (built)**: `GET /api/v1/branding` (any authenticated
  role, not admin-only — the sidebar needs it for everyone), `POST
  /api/v1/branding/upload-url` + `POST /api/v1/branding/confirm`
  (admin-only, same presigned-PUT-then-confirm shape `documents.py`
  already established, including the tenant/asset-type s3_key-prefix
  tamper check). `GET /branding`'s image URLs use a 1-hour presigned
  GET, not `documents`' 60-second one — a branding image is embedded as
  a persistent `<img>` across every page load, not downloaded once.
- **Multi-tenancy check**: standard RLS on the new table; upload/confirm
  reuse `documents`' existing tenant-scoped s3_key validation.
- **Acceptance criteria (met)**:
  - A tenant with no branding configured renders identically to the
    current app (no regression for the common case) — verified: the
    Sidebar's fallback chain always resolves to the plain wordmark when
    both URLs are null, including during the initial fetch.
  - Tenant A's branding is never visible to Tenant B under any code
    path, including the asset upload/serving path (tenant-isolation
    test).
  - An uploaded logo/header shows up in the sidebar without a page
    reload once the upload confirms.

### Phase 7i — Responsive / phone layouts
Depends on **every** other phase above — a mobile layout for a screen that
hasn't been rebuilt in the new design system yet isn't meaningful work.
Last in sequence for that reason, not because it's unimportant.

- **Affected layers**: frontend only.
- **Database / API**: none.
- **Multi-tenancy check**: N/A.
- **Task breakdown**:
  1. Bottom tab bar (Home/Pipe/Contact/Tasks/More) for <900px, replacing the
     sidebar.
  2. Dashboard: counters + queue cards, no chart.
  3. Pipeline: one-stage-at-a-time with a swipeable stage bar and an
     explicit "Move ▾" control replacing drag (drag doesn't work well on
     touch — this is a deliberate interaction change, not a missed detail).
  4. Contact detail: header actions (Call/WhatsApp/Note), tabbed Deals/
     Tasks/Activity/Docs, sticky Advance-stage bar.
- **Acceptance criteria**:
  - Every primary nav destination is reachable from the bottom tab bar at
    <900px.
  - Pipeline stage advancement works via the explicit "Move ▾" control with
    no drag-and-drop dependency below the 900px breakpoint.

## 5. `FEATURES_AND_PLAN.md` update

Append to the phase list:

> ### Phase 7 — OpenFunnel rebrand + design system
> New design system + white-label branding + several UX gaps closed
> (bulk contact actions, pipeline table view, escalation/follow-up
> snooze, workflow rule builder). Sub-phased 7a–7i in
> `OPENFUNNEL_REBRAND_PLAN.md` — 7a (token/rebrand foundation) gates
> every other visual sub-phase. Independent of Phase 5/6's remaining
> scope (disjoint tables/layers, same reasoning Phase 6 used against
> Phase 5).
> **Exit criteria**: every screen in `design_handoff_crm_wireframes/`
> has a shipped equivalent; "OpenFunnel" is the only product name a
> user ever sees; a tenant can publish custom branding that appears in
> the app shell, outbound email, and generated PDFs with zero effect on
> tenants who haven't configured any.

## 6. Sequencing summary

7a → (7b, 7c, 7d, 7e→7f, 7g, 7h can run in roughly any order relative to
each other once 7a lands, each independently shippable) → 7i last. 7e
gates 7f only because 7f's UI conventions are worth matching once 7e's
resolve-drawer pattern exists, not because of a hard dependency — reorder
if useful. 7h is flagged largest/riskiest/most-novel and intentionally not
first, per the architect note's own trade-off reasoning.
