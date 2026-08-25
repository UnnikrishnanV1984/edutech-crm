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

### Phase 7b — Configurations shell + Users & roles
Depends on 7a (visual). Backend work (Users & roles) has no visual
dependency and could be built in parallel with 7a if useful, but the tab
shell needs 7a's component restyle to look right.

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
- **Acceptance criteria**:
  - An admin can change another user's role and see it reflected
    immediately, without waiting for that user's next login.
  - If the Keycloak Admin API call fails, the local `users.role`/`status`
    column is confirmed unchanged (not written speculatively).
  - A disabled user drops out of `RowScope`/team-lookup results immediately.
  - A tenant-A admin cannot change a tenant-B user's role/status by id
    (404, not 403 — consistent with this codebase's established
    out-of-scope-looks-like-missing convention).
  - All five Configurations tabs (SLA, Integrations, Pipelines, Branding
    placeholder until 7h, Users & roles) are reachable from one nav entry;
    the four old standalone routes redirect or are removed.

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
(`escalations`) — per `CLAUDE.md`, run the snooze design through `architect`
before writing that migration, don't treat this plan's sketch below as
pre-approved.

- **Affected layers**: frontend (`EscalationsPage.tsx` gains counters,
  status filter pills, and a resolve drawer with radio outcomes), backend
  (`escalation_service.py` gains snooze; `reassign_to`/`resolution_note`
  already exist and just need a frontend UI, no backend change there).
- **Database (sketch, architect-gate before building)**: `escalations`
  gains `snoozed_until TIMESTAMPTZ NULL`; `status` CHECK constraint gains
  `'snoozed'`; a background job (same `worker`/`beat` pattern already used
  for SLA clocks) flips `snoozed` rows back to `open` once `snoozed_until`
  passes.
- **API contract**: `EscalationUpdate` gains `snoozed_until: datetime |
  None` as a third status-adjacent field alongside the existing
  `status`/`reassign_to`/`resolution_note`; the counters (Open, Breaching
  within 1h, Avg time to resolve, Reopened) likely want a new
  `GET /api/v1/reports/escalations` aggregate, following the existing
  `report_service.py` cache-aside pattern rather than computing client-side.
- **Multi-tenancy check**: standard — no new trust path, the counters
  endpoint scopes by `RowScope` exactly like every other report.
- **Task breakdown**:
  1. `architect` pass on the snooze schema sketch above.
  2. Migration + service + API for snooze, once approved.
  3. `report_service.get_escalation_summary` (or similar) for the counters.
  4. Frontend: counters row, status filter pills, resolve drawer (radio:
     Contacted-close / Reassign / Snooze, note field, Cancel/Resolve).
- **Acceptance criteria**:
  - A snoozed escalation automatically reopens (status → `open`) once
    `snoozed_until` passes, without any user action, verified via the
    background job's own test.
  - The "Breaching within 1h" counter matches a direct query against
    `sla_states`/`escalations` for the same tenant — no drift between the
    displayed count and the underlying data.

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

### Phase 7g — Workflow rule builder
Depends on 7a. Fully independent of every other phase.

- **Affected layers**: frontend only (`CreateWorkflowRulePanel.tsx` gains
  condition rows, ordered action cards, a plain-English preview, and a
  Test-run button); backend — confirm whether `workflow_rules.conditions`/
  `actions` JSONB already supports everything the builder needs to express
  (this session's earlier work on workflow rules suggests it likely does —
  verify field-by-field at implementation time rather than assuming), and
  whether a dry-run/"Test run" evaluation path exists in
  `workflow rule engine` already or needs a new read-only evaluation mode.
- **Database**: none expected — `workflow_rules` already stores conditions/
  actions as JSONB.
- **API contract**: candidate new endpoint — `POST
  /api/v1/workflow-rules/{id}/test-run` (or a pre-save variant taking the
  draft rule body directly, since Test run likely needs to work before the
  rule is saved) returning which contacts/deals the current condition set
  would currently match, without executing any actions.
- **Multi-tenancy check**: test-run evaluates against the caller's own
  tenant's data only — same scoping the real rule engine already uses.
- **Task breakdown**:
  1. Confirm current `conditions`/`actions` JSONB shape covers the
     wireframe's field/operator/value/AND condition-row model; extend if
     there's a gap.
  2. Backend: read-only test-run evaluation path (reuses the existing rule-
     matching logic, short-circuited before the action-dispatch step).
  3. Frontend: condition-row builder, ordered action cards, plain-English
     preview (pure client-side string generation from the current draft
     state), Test run button wired to the new endpoint.
- **Acceptance criteria**:
  - Test run against a draft (unsaved) rule shows real matching contacts/
    deals from the caller's own tenant and triggers zero actions.
  - The plain-English preview updates live as conditions/actions change,
    with no save required to see it.

### Phase 7h — Branding / white-label
Depends on 7a (the branding admin screen itself needs the restyled
component set). Largest, riskiest, most novel phase — sequenced near the
end deliberately, not first, despite being the wireframe's flagship screen.
**New RLS-scoped table + new external-facing rendering paths** — run the
schema and the login-branding scope decision below through `architect`
before building, per `CLAUDE.md`.

- **Affected layers**: frontend (new Branding tab: two upload wells, color/
  typeface pickers, live preview with App/Login/Email tabs, "where branding
  appears" checklist, version history), backend (new table + asset storage
  + draft/publish/version endpoints), BFF (branding config needs to reach
  the app shell early — probably fetched alongside `/api/v1/me` or a
  dedicated `GET /api/v1/branding` the shell calls before first paint),
  possibly outbound-email templates and PDF/invoice generation (both need
  to read published branding, not draft).
- **Database (sketch, architect-gate before building)**: a new
  `tenant_branding` table (or `tenant_branding_versions` if versioning is
  modeled as one-row-per-version rather than a `published`/`draft` pair
  of JSONB blobs) — standard `tenant_id NOT NULL` + RLS pattern; asset
  files (logo/header-lockup/favicon/login-backdrop) stored via the
  existing `documents` upload path, not a second storage mechanism.
- **Scope decision needed before this phase starts** (flagged, not
  resolved here): the wireframe's login-backdrop branding requires a
  **Keycloak login-theme customization** — this app has no in-app login
  screen (confirmed: PKCE redirect flow, `frontend/src/auth/` has no login
  page component). Recommend scoping Phase 7h's actual build to **app
  shell + outbound email + PDF/invoice** branding only, and treating the
  Keycloak login backdrop as an explicitly separate, later, architect-
  approved follow-up (different mechanism entirely — a Keycloak theme, not
  a React change) — don't let it block shipping the rest of this phase.
- **API contract (sketch)**: `GET /api/v1/branding` (published, cached
  alongside `/me` for the app shell), `GET /api/v1/branding/draft` +
  `PUT /api/v1/branding/draft` (admin-only, edits the working draft),
  `POST /api/v1/branding/publish` (draft → published, snapshots a version),
  `GET /api/v1/branding/versions` + `POST /api/v1/branding/versions/{id}/
  restore` (copies an old version back into draft, doesn't publish it
  automatically — matches the wireframe's "Restore" vs. "Publish" being
  distinct actions).
- **Multi-tenancy check**: standard RLS on the new table; the contrast-check
  and live-preview logic run entirely client-side against the draft, no
  new trust path. Asset uploads reuse `documents`' existing tenant-scoped
  upload validation.
- **Task breakdown**:
  1. `architect` pass: table shape (JSONB draft/published pair vs.
     versioned rows), and the login-branding scope decision above.
  2. Migration + schema/service/API for draft/publish/versions.
  3. Asset upload wiring (logo, header lockup, favicon) via the existing
     document-upload path.
  4. Frontend: upload wells, color/typeface pickers, contrast check,
     App/Login/Email preview tabs (Login tab shows what *would* render if
     the Keycloak theme were built — a mockup, not live, given the scope
     decision above), "where branding appears" checklist, version history.
  5. App shell: fetch published branding on load, apply logo/accent/
     typeface; confirm this doesn't regress unbranded (default) tenants —
     no branding configured must render exactly like today, not a broken
     partial theme.
  6. Outbound email + PDF/invoice: read published branding at render time.
- **Acceptance criteria**:
  - A tenant with no branding configured renders identically to the
    current app (no regression for the common case).
  - Publishing a draft is the *only* thing that changes what the app shell/
    emails/PDFs render — editing the draft alone never affects a live
    session.
  - Restore populates the draft from a prior version without publishing it
    automatically — a second, explicit Publish is required.
  - The contrast check correctly flags an accent-on-header combination
    under 3:1 before Publish is allowed (or at least surfaces a clear
    warning — decide "warns" vs. "blocks" at implementation time).
  - Tenant A's branding is never visible to Tenant B under any code path,
    including the asset upload/serving path.

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
