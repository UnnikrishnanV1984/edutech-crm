# Branding — full system plan (Phase 7h continuation)

Companion to `OPENFUNNEL_REBRAND_PLAN.md`'s Phase 7h, which shipped logo +
header upload (applied immediately, no draft/publish) on 2026-08-25. This
plan covers the rest of `design_handoff_crm_wireframes/` screen 1l: draft/
publish, version history, company display name, favicon, login backdrop,
palette (accent + header background), typeface, custom domain, contrast
check, live preview (App/Login/Email tabs), and the "where branding
appears" checklist.

Per `feature-planner`'s process — this is a plan, not code. Per `CLAUDE.md`,
this is a **schema change to a table already in production use**
(`tenant_branding`) plus a **new table** — both need an `architect` pass
before implementation starts. Treat everything below as a sketch to be
approved, not pre-approved.

## 1. Located

Phase 7h in `FEATURES_AND_PLAN.md` (Phase 7's sub-phases, tracked in
`OPENFUNNEL_REBRAND_PLAN.md`). Not a new phase — this is the remainder of
7h that the first pass explicitly deferred.

## 2. Prerequisites check

Phase 7a (token/rebrand foundation) — done, this phase depends on it
visually. No other phase blocks this one.

## 3. Scope decision, confirmed with the user before this plan was written

Three of the mockup's "where branding appears" surfaces don't exist in
this app yet, and a fourth (custom domain) is a different kind of project
entirely:

- **Login screen** — this app has no in-app login page (PKCE redirect to
  Keycloak's own hosted login — confirmed, `frontend/src/auth/` has only
  `AuthProvider.tsx`/`context.ts`). Applying real branding there needs a
  Keycloak custom theme (FreeMarker templates), a different technology,
  not a React change.
- **Outbound emails** — this app sends zero emails today (confirmed, no
  SMTP client/email service/template anywhere in `backend/app`).
- **Invoices & PDFs** — no PDF generation exists anywhere (confirmed, no
  PDF library dependency, `invoice_service.py` is pure CRUD/state-machine,
  no rendering). The wireframe itself shows this checkbox unchecked —
  even the mockup doesn't claim this one is live.
- **Custom domain** — a DNS/TLS/routing project (custom domain → tenant
  resolution *before* auth, per-domain certificate provisioning, Keycloak
  redirect-URI management), unrelated to branding CRUD.

Decision: build the admin-side UI for all of these as **real, working
controls that save real data** — but the three preview surfaces (Login,
Email) render a clearly-labeled **"Preview only — not yet live"** mockup
using the draft's branding, and the "where branding appears" checklist
reflects that honestly (App sidebar & header: live; Login screen /
Outbound emails: preview only; Invoices & PDFs: not available — matching
the wireframe's own unchecked state). Custom domain is a stored field
with a visible "not yet active" note, not wired to any routing. Nothing
here is a dead end — a future Keycloak-theme project or email/PDF feature
can read what's already captured.

## 4. Affected layers

- **Frontend**: `BrandingTab.tsx` substantially rebuilt (draft/publish
  buttons, expanded Company identity box, new Palette & type box,
  contrast check, Live preview panel with App/Login/Email tabs, "where
  branding appears" checklist, Version history panel). `Sidebar.tsx`
  gains real application of `accent_color`/`header_background` (CSS
  custom-property overrides) and a dynamic favicon `<link>`, on top of
  the logo/header image it already renders.
- **Backend**: `tenant_branding` (existing table) becomes the mutable
  **draft**; new `tenant_branding_versions` table holds immutable
  published snapshots. New service functions + API routes for draft
  read/write, publish, discard, version list, and restore.
- **BFF**: none — the existing generic `/api/v1/*` proxy already covers
  new routes under `/api/v1/branding/*`.
- **Database**: one migration, two things — extend `tenant_branding`
  with new columns, create `tenant_branding_versions`.
- **Background jobs**: none.

## 5. Database (sketch — architect-gate before building)

`tenant_branding` (existing, migration `0029`) gains:

| Column | Type | Notes |
|---|---|---|
| `company_display_name` | `TEXT NULL` | shown in sidebar/preview in place of the tenant's Keycloak-registered name when set |
| `favicon_s3_key` | `TEXT NULL` | same bucket/upload path as logo/header |
| `login_backdrop_s3_key` | `TEXT NULL` | stored for real; only ever rendered in the Login preview tab, never a real Keycloak page |
| `accent_color` | `TEXT NULL` | hex string, validated server-side (`^#[0-9a-fA-F]{6}$`) |
| `header_background` | `TEXT NOT NULL DEFAULT 'light'` | `CHECK (header_background IN ('light','dark','accent'))` |
| `typeface` | `TEXT NOT NULL DEFAULT 'system'` | `CHECK` against a small closed set — see §6 on why this can't be an open picker |
| `custom_domain` | `TEXT NULL` | stored only, no routing behavior — UI must label it "not yet active" |

New `tenant_branding_versions` — write-once, INSERT-only, never UPDATEd,
same shape/spirit as `pipeline_stage_default_snapshots` (`DATABASE_SCHEMA.md`
row for that table: "write-once, only ever INSERTed... a snapshot is a
point-in-time capture, not a live-editable config"):

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK part 1 |
| `tenant_id` | `UUID NOT NULL REFERENCES tenants(id)` | PK part 2, standard pattern |
| `version_number` | `INT NOT NULL` | per-tenant incrementing (1, 2, 3…); `UNIQUE (tenant_id, version_number)` |
| every draft column above | same types | full snapshot at publish time, not a diff |
| `published_by` | `UUID NOT NULL REFERENCES users(id)` composite with `tenant_id` | who published |
| `published_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

Both tables: standard `tenant_id` + RLS pattern (`DATABASE_SCHEMA.md` §2).
`tenant_branding_versions` leads its lookup index with `tenant_id` per the
indexing rule (`idx_tenant_branding_versions_tenant_version` on
`(tenant_id, version_number DESC)`).

**Architect decision (2026-08-26)**: keep `tenant_branding` as the
mutable/current-working-copy table, no rename. This codebase already has
a directly analogous pair — `pipeline_stages` (the tenant's live, editable
config) and `pipeline_stage_default_snapshots` (an immutable
point-in-time snapshot table, qualified name, write-once) — same relation
`tenant_branding`/`tenant_branding_versions` needs. The "current working
copy keeps its plain name, the snapshot-history table gets the qualifier"
convention is already established, not a new one being invented for this
feature, so `tenant_branding` stays as-is and only
`tenant_branding_versions` is new. Rejected alternative: renaming to
`tenant_branding_draft` — adds a migration-of-a-migration and a model
rename for a clarity gain the existing precedent already achieves without
it (the pattern reads correctly the same way `pipeline_stages` does).

Rest of §5's column sketch confirmed sound as written: `accent_color`'s
regex-validated hex-string `TEXT`, `header_background`'s `CHECK`-
constrained enum, `typeface`'s `CHECK`-constrained closed set, and
`tenant_branding_versions`' full-snapshot-not-a-diff shape (mirroring
`pipeline_stage_default_snapshots` again) are all standard, low-risk
patterns already used elsewhere in this schema — no changes to the
sketch. `custom_domain` stays a plain nullable `TEXT` with no `CHECK`
(format validation, if any, belongs at the API/schema layer, not the DB,
since it's inert data with no routing behavior to protect).

## 6. API contract (sketch)

All under `/api/v1/branding`, all admin-only except the first:

- `GET /api/v1/branding` — **unchanged contract**, still any authenticated
  role. Now reads the **latest row in `tenant_branding_versions`**
  (`ORDER BY version_number DESC LIMIT 1`), not the draft table — a tenant
  that has only ever edited the draft and never published still renders
  fully unbranded, matching "nothing goes live until Publish."
- `GET /api/v1/branding/draft` — the mutable draft (auto-vivified empty on
  first read if no row exists yet).
- `PUT /api/v1/branding/draft` — partial update of the non-asset fields
  (`company_display_name`, `accent_color`, `header_background`,
  `typeface`, `custom_domain`). Asset fields go through upload/confirm.
- `POST /api/v1/branding/upload-url` / `POST /api/v1/branding/confirm` —
  same shape as today, `asset_type` gains `"favicon"` and
  `"login_backdrop"` alongside the existing `"logo"`/`"header"`. Confirm
  now always writes into the **draft** row (today it writes directly to
  the only row that exists, which doubles as "live" — that's exactly the
  behavior this phase changes).
- `POST /api/v1/branding/publish` — snapshots the current draft into a new
  `tenant_branding_versions` row (`version_number` = tenant's max + 1).
- `POST /api/v1/branding/discard` — overwrites the draft row's editable
  fields with the latest published version's values (or clears them to
  defaults if never published).
- `GET /api/v1/branding/versions` — list history, newest first.
- `POST /api/v1/branding/versions/{id}/restore` — copies that version's
  fields into the **draft** (not published) — a second, explicit Publish
  is required to go live, matching the wireframe's distinct
  Restore-vs-Publish actions.

`typeface` accepts only a small closed set the app actually ships fonts
for — **not an open picker**. Found while researching this plan:
`frontend/src/index.css` vendors Cormorant Garamond/Lora as local
`@font-face` `.woff2` files specifically *because* this app is
client-VPC-deployable with no guaranteed external egress (its own
comment: "not a Google Fonts `@import`... this app is client-VPC
deployable with no guaranteed egress to an external font CDN"). An
arbitrary Google-Fonts-catalog picker would violate that. Recommend
shipping 2–3 pre-vendored pairs total (e.g. `"serif"` = the current
Cormorant/Lora pairing, `"system"` = the OS font stack, maybe one more)
and constraining the dropdown to exactly that set, both client- and
server-side.

## 7. Multi-tenancy check

Standard RLS on both tables. Draft/publish/discard/restore all admin-only
(`require_admin`, matching the rest of Configurations). `GET /branding`
(live) stays open to every role, unchanged. No new tenant-trust path —
same `X-Tenant-Id`-from-validated-token chain every other route uses.
Restore must re-verify the target version row's `tenant_id` matches the
caller's tenant before copying (404 on cross-tenant id, consistent with
this codebase's established out-of-scope-looks-like-missing convention).

## 8. Frontend notes

- **Palette application**: `accent_color` overrides `--accent` (and a
  computed hover/subtle shade — reuse whatever shade math, if any, this
  app already has, else a simple lighten/darken); `header_background`
  overrides the Sidebar's own background var, independent of the
  viewer's light/dark theme preference. Needs care not to fight
  `ThemeToggle.tsx`'s existing `:root[data-theme]` token system — apply
  branding overrides as a second, more-specific layer (inline style or a
  scoped `<style>` block) rather than editing the base token
  definitions, and confirm both light and dark theme still hold with a
  branding override applied.
- **Contrast check**: pure client-side WCAG relative-luminance contrast
  ratio between `accent_color` and the resolved header background color,
  recomputed live as either changes. Decide warn-vs-block at
  implementation time (wireframe shows a warning chip, not a disabled
  Publish button — recommend warn, not block, so a deliberate low-contrast
  choice isn't hard-blocked).
- **Live preview**: App tab renders a real mini mockup of the draft state
  (logo/header/accent/header-background/typeface, matching the wireframe's
  small rendered preview). Login/Email tabs render the same kind of mini
  mockup but **must carry a visible "Preview only — not yet live" label**
  — this is the honesty requirement from §3, not optional polish.
- **Favicon**: dynamically swap `<link rel="icon">` in `index.html` from
  the published branding's `favicon_s3_key`-derived URL on app load;
  unbranded tenants keep the platform default.
- **"Where branding appears" checklist**: static per-row status, not a
  live toggle — App sidebar & header (Live), Login screen (Preview only),
  Outbound emails (Preview only), Invoices & PDFs (Not available yet).

## 9. Task breakdown (commit-sized)

1. `architect` pass: confirm the schema sketch in §5 (including the open
   naming question) and the scope decision in §3.
2. Migration: extend `tenant_branding` with the new draft columns; create
   `tenant_branding_versions`.
3. Backend: draft read/write endpoints + service functions.
4. Backend: publish/discard/versions/restore endpoints + service
   functions; re-point `GET /api/v1/branding` at the versions table.
5. Backend: extend upload/confirm for `favicon`/`login_backdrop` asset
   types; tests for the full draft → publish → live round trip, discard,
   restore, and tenant isolation on restore.
6. Frontend: Company identity box additions (display name, favicon,
   login backdrop wells).
7. Frontend: Palette & type box (accent swatches + custom picker, header
   background chips, typeface dropdown constrained to the vendored set,
   custom domain field with its "not yet active" note) + contrast check.
8. Frontend: Live preview panel (App/Login/Email tabs) + "where branding
   appears" checklist.
9. Frontend: Version history panel + Restore wiring; top-bar
   Discard/Publish buttons replacing today's immediate-apply model.
10. Frontend: `Sidebar.tsx` — apply `accent_color`/`header_background`,
    dynamic favicon; verify an unbranded tenant and a tenant with only an
    unpublished draft both still render exactly like today (no partial
    theme leaks from draft edits into the live app).

## 10. Acceptance criteria (met, 2026-08-26)

- A tenant with no published version renders identically to the current
  (unbranded) app, even if that tenant has an in-progress, unpublished
  draft — editing the draft alone never affects any live session.
  **Met** — `test_live_branding_default_when_unpublished`.
- Publish is the only action that changes what `GET /api/v1/branding`
  (and therefore the live app shell) returns; the response before and
  after a draft-only edit is byte-identical.
  **Met** — `test_draft_edits_dont_affect_live_until_published`,
  `test_publish_makes_draft_live`.
- Discard resets the draft to exactly the latest published version's
  values (or empty defaults pre-first-publish) — verified field-by-field,
  not just "form looks empty."
  **Met** — `test_discard_resets_to_published_values`,
  `test_discard_with_no_prior_publish_resets_to_defaults`; frontend
  `BrandingTab.test.tsx` "discarding resets the draft to what the endpoint
  returns" covers the form re-rendering with the reset values (the text
  inputs are keyed on `updated_at` so they actually remount instead of
  showing stale typed text).
- Restore populates the draft from a chosen prior version without
  publishing it automatically — a second, explicit Publish is required,
  and the live app is unaffected until then.
  **Met** — `test_restore_populates_draft_without_publishing`.
- A tenant-A admin cannot restore or view a tenant-B version by id (404).
  **Met** — `test_restore_rejects_cross_tenant_version_id`.
- The contrast check reflects the *current draft's* accent/header-background
  pair, updates without a save, and never blocks Publish outright (warns).
  **Met** — `BrandingTab.test.tsx` "warns when accent-on-header contrast is
  below the WCAG AA threshold"; the Publish button has no disabled/guard
  tied to the contrast result.
- The Login and Email preview tabs are visibly labeled as preview-only in
  the rendered UI, not just in an internal comment — a screenshot of
  either must make the "not live" status obvious to whoever's looking at
  it.
  **Met** — `PreviewOnlyNote` in `BrandingLivePreview.tsx` renders on both
  tabs in `--danger` text; covered by "shows preview-only notes for the
  login and email preview tabs".
- `typeface` rejects any value outside the small vendored set server-side,
  not just hidden from the dropdown client-side.
  **Met** — `ck_tenant_branding_typeface` CHECK constraint +
  `test_invalid_typeface_rejected`.
- Setting `custom_domain` saves and displays the value but has no
  observable effect on routing, auth, or any request's `Host` handling —
  verified by confirming no code path reads it outside the branding
  API/UI itself.
  **Met** — `test_custom_domain_saves_but_never_live`; repo-wide grep for
  `custom_domain` confirms zero references outside the branding stack
  (schema/model/service/route/tests + `api/branding.ts`/`BrandingTab.tsx`).
