# Phase 7a — Rebrand + design token foundation: commit-level plan

Companion to `OPENFUNNEL_REBRAND_PLAN.md` §4 "Phase 7a", which fixes this
phase's scope and acceptance criteria. This doc sizes that phase-level entry
down to a sequence of reviewable commits, same rhythm
`PIPELINE_CONFIG_RESET_PLAN.md`'s §7 used for that feature. Not re-deriving
the gap analysis or re-opening scope — only sequencing and the concrete
token-mapping decision the phase-level doc deliberately left open ("exact
existing-name mapping table is this phase's own first task").

## 1. Located

`FEATURES_AND_PLAN.md` Phase 7, sub-phase 7a, per `OPENFUNNEL_REBRAND_PLAN.md`
§4. Gates every other Phase 7 sub-phase — nothing else in Phase 7 should
start before this lands.

## 2. Prerequisites check

None. Frontend-only, no dependency on Phase 5/6's in-flight work (already
established in the phase-level doc §2).

## 3. Affected layers

Frontend only: `frontend/src/index.css`, `frontend/index.html`,
`frontend/src/Sidebar.tsx`, the shared component set (`Button.tsx`,
`Card.tsx`, `Badge.tsx`, `EmptyState.tsx`, `Avatar.tsx`, `ThemeToggle.tsx`),
plus prose in `README.md`, `DEVELOPMENT_PLAN.md`, `ARCHITECTURE.md`,
`CLAUDE.md`, `backend/app/main.py` (FastAPI `title=`), `backend/pyproject.toml`
(`description`), `deploy/helm/*/Chart.yaml` (`description`), and
`keycloak/realm-export.json` (the `web` client's display `"name"` field,
shown on Keycloak's own login/consent screens — a user-facing string, not
the realm slug). No backend logic, no BFF, no database, no background jobs.

**Confirmed by direct grep**: 17 files contain the literal string
`"EdTech CRM"`. All 17 are display strings, titles, or prose descriptions —
none is an internal identifier. The repo folder name, Docker image names,
`edutech_crm` Postgres DB name, and the `edutech-crm` Keycloak realm slug
use the separate lowercase-hyphenated form and never matched this search —
confirms the phase-level doc's exclusion list is already clean, nothing to
avoid touching by accident.

## 4. Database changes

None.

## 5. API contract

None — `backend/app/main.py`'s FastAPI `title="EdTech CRM API"` is
display-only (shows up in the auto-generated OpenAPI docs page), not a
contract field any client parses.

## 6. Multi-tenancy check

N/A — no data path touched, confirmed in the phase-level doc.

## 7. Task breakdown (commit-level)

### Commit 1 — Token value remap in `index.css` (light + dark)

Remap the *values* of the app's existing `--*` custom properties to
`tokens.css`'s Classical palette. Keep every existing name — nothing in the
rest of the app references a new name. Starting-point mapping (verify
visually against both themes before finalizing exact values — these are the
closest role match, not pixel-locked):

| Existing token | Role | New light value (from `tokens.css`) | New dark value |
|---|---|---|---|
| `--bg` | page ground | `--p` `#fdfcfa` | `--p` `#1b1917` |
| `--surface` | raised surface (cards, inputs) | `--p2` `#ffffff` | `--p2` `#221f1c` |
| `--surface-hover` | quiet hover fill | `--s2` `#f7f5ef` | `--s2` `#272320` |
| `--elevation-2` | card background (`Card.tsx`) | same as `--surface` → `#ffffff` | same as `--surface` → `#221f1c` |
| `--border` | hairline | `--ln` `#e6e2d8` | `--ln` `#332f29` |
| `--text-muted` | muted labels | `--mut` `#6f6a61` | `--mut` `#a49b8c` |
| `--text` | body text | `--ink2` `#4c473f` | `--ink2` `#cec7ba` |
| `--text-h` | heading text | `--ink` `#201f1d` | `--ink` `#efe9de` |
| `--accent` | accent stroke/text | `--ac` `#b68235` | `--ac` `#c99a4e` |
| `--accent-hover` | accent emphasis | `--act` `#8a6323` | `--act` `#dcb877` |
| `--accent-subtle` | accent tint fill | `--at` `#f7f0e2` | `--at` `#2f2618` |
| `--accent-fg` | text/icon on a *filled* accent surface | low-usage after Commit 3 (primary buttons stop filling) — keep resolvable: `--ink` on light / `--ink` on dark | same |

`--danger`/`--danger-bg`, `--success`/`--success-bg`, `--warning`/
`--warning-bg` have **no equivalent in `tokens.css`** — the Classical system
is explicitly single-accent ("Accent is applied as stroke... never a solid
block", per the wireframe README). Pick three muted, warm-palette-consistent
values by hand (e.g. a muted terracotta for danger, a muted sage/olive for
success, an amber close to `--ac` but distinguishable for warning) rather
than keeping the current saturated purple-adjacent set — flag this as a
judgment call to sanity-check against real SLA/status badges (breached/
on-track/at-risk) before finalizing, since those are read at a glance
throughout the app.

Radius — adopt `tokens.css`'s `--wf-radius-*` scale onto the existing
names:
- `--radius-sm` (badges/chips) → 5px (`--wf-radius-xs`)
- `--radius` (buttons, inputs, controls) → 8px (`--wf-radius-sm`)
- `--radius-lg` (`Card.tsx`) → 10px (`--wf-radius-md`)
- No current token maps to the wireframe's 14px "outer frame" or 999px
  "pill" radii — `Badge`'s count variant already hardcodes `999` inline
  (no change needed); confirm whether any component needs the 14px value
  once Commit 3 is underway, don't add a token speculatively.

Spacing — shift toward `styles.css`'s tighter rhythm as a starting point
(round, don't force to decimals): `--space-1` 4→5px, `--space-2` 8→9px,
`--space-3` 12→14px, `--space-4` 16→18px, `--space-5` 24px (no direct
source step, leave as-is or nudge to ~23px), `--space-6` 32→28px,
`--space-7` 48px (beyond `styles.css`'s own defined range — leave as-is
unless it visually overshoots once fonts/radius change). Treat these as a
first pass to eyeball against real pages, not a locked table.

Shadows — keep the existing `rgba(...)` structure in `--shadow-sm/md/lg`,
just recolor the tint from the current blue-purple base
(`rgba(20,16,30,...)`) to an ink-based tint consistent with `--ink`
(`rgba(32,31,29,...)`), matching `styles.css`'s own shadow approach.

Do **not** touch `--text-xs`…`--text-2xl`/`--line-*`/`--weight-*` sizes in
this commit — font family changes in Commit 2 and component restyle in
Commit 3 are where type actually changes; the size/line-height scale itself
isn't part of this phase's scope per the phase-level doc.

### Commit 2 — Fonts: Cormorant Garamond + Lora, vendored locally

Add two new tokens (additive, nothing currently uses these names):
`--font-heading: 'Cormorant Garamond', Georgia, serif` and
`--font-body: 'Lora', Georgia, serif` — matching `tokens.css`'s
`--wf-font-heading`/`--wf-font-body` fallback stacks exactly. Apply
`--font-heading` to `h1`–`h6` and `Card.tsx`'s title `h2`; apply
`--font-body` to the `:root` font shorthand (replacing the current
`--sans` default for body text); keep `--sans` defined and available as a
fallback for any UI chrome where a serif reads poorly (to be judged during
Commit 3's component pass, not decided here). `--weight-semibold` (600)
already matches the wireframe's stated heading-weight ceiling ("Bold is not
used") — no new weight token needed.

**Font-loading decision (resolving the open CSP/offline-dev question from
the phase-level doc)**: vendor the two font families' `.woff2` files locally
under `frontend/public/fonts/` and declare them via `@font-face`, rather
than `styles.css`'s Google Fonts `@import`. Reasoning: this app has no CSP
configured anywhere today (grepped clean across `bff`/`backend`), so a CSP
block isn't the actual risk — the real one is `CLAUDE.md`'s own
single-tenant/client-VPC deployment model. A client VPC has no guaranteed
egress to `fonts.googleapis.com`, and `docker compose up` should keep
working identically offline (same "same images, different config, no
hidden external dependency" principle already applied to `db`/`redis`/
`keycloak` in `CLAUDE.md` rule 8). Vendoring is a one-time asset add, not a
new moving part — cheaper than carrying a runtime dependency on an external
CDN for text rendering.

### Commit 3 — Restyle shared components: `Button`, `Card`, `Badge`, `EmptyState`, `Avatar`, `ThemeToggle`

Values-only restyle against `styles.css`'s `.btn`/`.card`/`.tag` definitions
— no new global CSS classes, no second styling system (per the phase-level
doc's explicit warning against fragmenting the codebase). Concretely:

- `Button.tsx`: `primary` variant currently fills solid
  (`background: var(--accent)`) — change to accent-**outlined**
  (`background: transparent; color: var(--accent); border: 1px solid
  var(--accent)`), matching `.btn-primary` in `styles.css` and the
  wireframe README's explicit rule ("primary = accent-outlined, never
  filled"). `secondary`/`text` variants keep their current structural
  approach, just inherit the remapped tokens automatically via Commit 1 —
  no changes needed there beyond what Commit 1 already provides. Update
  `index.css`'s `.btn-primary:hover` rule (currently `background:
  var(--accent-hover)`, appropriate for a filled button) to a tint hover
  instead (e.g. `background: var(--accent-subtle)`), consistent with the
  outline-only rule.
- `Card.tsx`: inherits Commit 1's `--elevation-2`/`--border`/
  `--radius-lg`/`--shadow-sm` automatically — verify visually, no code
  change expected beyond the token values already changing underneath it.
- `Badge.tsx`: chip variant already uses tone-based bg/fg/border (mostly
  automatic via Commit 1); count variant already uses `--accent-subtle`/
  `--accent` — verify contrast holds with the new warm palette.
- `EmptyState.tsx`, `Avatar.tsx`: inherit remapped tokens automatically —
  visual check only.
- `ThemeToggle.tsx`: inherits `--surface`/`--border`/`--radius`/
  `--elevation-2`/`--accent`/`--text-muted` automatically — the selected-
  option contrast (currently `--elevation-2` bg + `--accent` text vs.
  `--text-muted` for unselected) should be re-checked once the new accent
  color lands, since `--ac`'s amber is a different hue/lightness than the
  current purple and the raised/tinted-selected state needs to stay clearly
  distinguishable at a glance.

### Commit 4 — Rebrand: "EdTech CRM" → "OpenFunnel"

Replace the literal display string in all 17 grepped locations (§3 above),
excluding nothing else (no internal identifier matched):
`frontend/src/Sidebar.tsx:104`, `frontend/index.html:20` (`<title>`),
`README.md`, `DEVELOPMENT_PLAN.md`, `ARCHITECTURE.md`, `CLAUDE.md`,
`backend/app/main.py:70` (`FastAPI(title=...)`),
`backend/pyproject.toml` (`description`),
`deploy/helm/{web,bff,backend,keycloak}/Chart.yaml` (`description`),
`keycloak/realm-export.json` (the `web` client's display `"name"` field —
verify this doesn't also require a Keycloak container restart to
re-import; note it in the commit if so, same as any other realm-export
edit per `CLAUDE.md`'s Keycloak instructions), plus `.claude/skills/
feature-planner/SKILL.md` and `.claude/skills/engineer/SKILL.md` if those
matches turn out to be example/prose text rather than functional skill
logic — confirm before editing, since skill files are process config, not
docs about the product itself. Leave `design_handoff_crm_wireframes/`
untouched — it's an as-received reference bundle, not a doc this app
maintains.

### Commit 5 — Visual verification pass + acceptance sign-off

No code change expected; if the visual check surfaces a leftover hardcoded
color/font (something that bypassed the token system), fix it here as a
small follow-up within this same commit's scope rather than opening a new
task. Walk every existing page in both light and dark, confirm:
- No hardcoded hex color or font-family remains outside `index.css`'s
  token definitions (grep for stray `#` hex literals and `font-family:` in
  `frontend/src` outside `index.css`/`stageColor.ts` as a mechanical check).
- Primary buttons are outline-only everywhere, never a filled accent block.
- Dark mode renders correctly for every page — both the `prefers-color-
  scheme` path and the explicit `data-theme="dark"` override path (both
  blocks in `index.css` must stay in sync, per the existing comment there).

## 8. Acceptance criteria

(Restated from the phase-level doc, unchanged — this plan doesn't loosen or
add to them.)

- Every existing page renders with the new palette/type in both light and
  dark with no hardcoded color/font left over from the old palette.
- Sidebar, browser tab, and `README.md` all say "OpenFunnel"; no internal
  identifier (repo folder, Docker image name, `edutech_crm` DB name,
  `edutech-crm` Keycloak realm slug, `tenant-a`/`tenant-b` slugs) changed —
  confirmed by re-running the same grep from §3 and finding zero remaining
  `"EdTech CRM"` matches outside `design_handoff_crm_wireframes/`.
- A visual pass confirms accent is never used as a solid fill on a primary
  button (stroke/outline only).
- `docker compose up` still reaches a working login with no external
  network dependency for fonts (fonts load from the vendored local files,
  not a Google Fonts fetch) — testable by disabling network egress during
  a local check, or at minimum confirming the `@font-face` `src` points at
  a local path, not a remote URL.
