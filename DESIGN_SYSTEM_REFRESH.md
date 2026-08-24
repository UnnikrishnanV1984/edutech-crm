# Design system refresh — visual tokens & component polish

Produced by the `ui-designer` skill. Pure visual refresh — every
interaction state, layout, and component structure in
`PHASE_1_UI_DESIGN.md` stays exactly as specified there; only token
*values* and each component's visual treatment change. No flow changes,
no code in this pass — precise enough for `feature-builder` to restyle
`frontend/src/index.css` and the existing components directly.

**Grounding** (per the user's ask to reference real CRM design systems —
cited, not invented):
- **Attio**: a monochrome black/white base with restrained *per-section*
  pastel accents rather than one saturated color used everywhere.
- **Linear**: token-based, dark-mode-first; low-contrast panel borders; a
  single saturated accent sitting in an otherwise quiet, desaturated
  system — the accent reads as "the one thing that matters" precisely
  because nothing else competes with it.
- **General SaaS dashboard guidance**: token architecture should be
  primitives → semantic tokens → component tokens, not raw hex sprinkled
  through components; a true dark-mode base should be a soft dark grey in
  the `#0E`–`#1A` range, never pure black (halation/eye strain over long
  sessions); prefer layered elevation via background-lightness steps over
  heavy box-shadow; one primary + one neutral scale + one accent +
  functional colors, not a rainbow; WCAG AA 4.5:1 text contrast is a hard
  floor in both themes.

Applied here as: pastel **badge-style chips** (soft tinted background +
a deeper-toned, same-hue text — not solid color + white text) for every
stage/lead-source/status indicator, a single saturated accent reserved
for interactive/primary-action elements only, and a true-grey (not
black) dark base with elevation expressed as lightness steps.

---

## 1. Token architecture

Three layers, all as CSS custom properties in `index.css`'s existing
`:root` + `@media (prefers-color-scheme: dark)` structure — no new
theming mechanism (no CSS-in-JS, no Tailwind); this app is small enough
that plain custom properties stay easy to reason about, and introducing a
build-time CSS pipeline would be a real cost for no benefit here.

1. **Primitives** — raw color/size values, not referenced directly by
   components (documented below for where each semantic token comes
   from, but only the semantic/component layer actually ships as
   `--tokens` in the CSS).
2. **Semantic tokens** — today's `--bg`/`--surface`/`--text`/etc., kept
   as the primary thing components reference. Every existing token name
   is kept (nothing renamed, so no component needs a token-name update,
   only value changes) plus a small number of additions listed below.
3. **Component tokens** — a few cases (badges, buttons) get their own
   narrow token set built from the semantic layer, because "the accent
   color" and "a badge's fill" are different enough concerns that
   reusing one token for both gets confusing once there are six badge
   hues.

## 2. Neutral scale (primitive → `--bg`/`--surface`/`--border`/`--text*`)

**Light** — warm-tinted (very slightly violet) greys, not pure grey, so
the neutral scale feels coherent with the violet accent rather than
fighting it:

| Step | Hex | Maps to |
|---|---|---|
| 0 | `#ffffff` | `--bg` |
| 50 | `#f9f8fb` | `--surface` |
| 100 | `#f1eff5` | `--surface-hover` |
| 200 | `#e6e3ec` | `--border` |
| 500 | `#736c82` | `--text-muted` (darkened from an initial `#8b859a` — that only cleared 3.55:1 against `--bg`, short of AA; see §7's note on how every color pair here was checked numerically) |
| 700 | `#4a4556` | `--text` |
| 900 | `#1c1a22` | `--text-h` |

**Dark** — true-grey base in the `#0E`–`#1A` range (not pure black), then
each elevation step *lighter* than the last — the standard "closer
surfaces catch more light" dark-mode convention, and it's also just more
headroom than light mode has (light mode is already capped at white):

| Step | Hex | Maps to |
|---|---|---|
| 950 | `#121319` | `--bg` |
| 900 | `#191a22` | `--surface` |
| 800 | `#21222c` | `--surface-hover` |
| 700 | `#2b2c38` | `--border` |
| 400 | `#8d8fa3` | `--text-muted` |
| 200 | `#c7c8d6` | `--text` |
| 50 | `#f5f5f9` | `--text-h` |

Both scales checked against WCAG AA 4.5:1 for `--text`/`--text-h` against
`--bg` and `--surface` — all pass.

## 3. Elevation

A named 3-step scale, added because `SlideOverPanel`/`Toast`/popovers
currently have no defined relationship to `--surface`:

- **`--elevation-0`** (page): `--bg`.
- **`--elevation-1`** (cards, table rows on hover, nav bar): `--surface`.
- **`--elevation-2`** (`SlideOverPanel`, `Toast`, dropdowns, the
  won/lost confirm popover, the owner-select popover): in dark mode this
  is a step *lighter* than `--surface` (`#21222c` — same value as
  `--surface-hover`, which is fine, they're different concerns reused at
  the same lightness); in light mode there's no headroom left above
  white, so elevation-2 stays white but gains a visible `--border` plus
  `--shadow-md` (below) to read as "above" the tinted `--surface` layer
  beneath it. This asymmetry between the two themes is intentional, not
  an oversight — light mode substitutes shadow for the lightness step
  dark mode gets for free.

New tokens: `--elevation-2` (`#ffffff` light / `#21222c` dark).

## 4. Shadows

Used sparingly — only where elevation's lightness step alone doesn't
read clearly (light-mode panels/popovers, and the pipeline card's
dragging-lift state in both themes):

| Token | Light | Dark |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(20,16,30,.06)` | `0 1px 2px rgba(0,0,0,.3)` |
| `--shadow-md` | `0 4px 16px rgba(20,16,30,.10)` | `0 4px 16px rgba(0,0,0,.35)` |
| `--shadow-lg` (drag-lift) | `0 8px 24px rgba(20,16,30,.16)` | `0 8px 24px rgba(0,0,0,.45)` |

## 5. Spacing & radius scales

Added because current spacing is one-off (`8px 16px` on buttons/inputs,
nothing elsewhere named) — a small scale, not over-built:

`--space-1: 4px` `--space-2: 8px` `--space-3: 12px` `--space-4: 16px`
`--space-5: 24px` `--space-6: 32px` `--space-7: 48px`

`--radius-sm: 4px` (badges/chips) · `--radius: 8px` (buttons, inputs,
cards — bumped from the current flat `6px`, reads slightly softer/more
current without becoming bubbly) · `--radius-lg: 12px` (panels, toasts,
popovers).

## 6. Typography scale

One `h1` rule today, everything else inherits the 16px body default.
Internal, data-dense tool → slightly denser base than a marketing site,
matching `ui-designer`'s own standing density-first guidance:

| Token | Size/line-height | Use |
|---|---|---|
| `--text-xs` | 12px/16px | Badge labels, timestamps, meta lines |
| `--text-sm` | 13px/18px | Table cells, secondary UI text |
| `--text-base` | 14px/20px | Default body (was 16px) |
| `--text-lg` | 16px/24px | In-page section headers ("Deals", "Tasks") |
| `--text-xl` | 20px/28px | Page-level subheads |
| `--text-2xl` | 24px/32px | `h1` (same size as today, now tokenized) |

`--weight-normal: 400` `--weight-medium: 500` (buttons, badges, section
headers) `--weight-semibold: 600` (`h1`, page titles)

## 7. Semantic action/status colors

Single saturated accent — kept in the existing violet family (continuity
with what's already shipped) but the value is refined so it reads as
*the one accent*, not one of several bright colors once badges go
pastel. **Every value below was checked programmatically against WCAG
AA's 4.5:1 text-contrast floor against the background it's actually
paired with** (not eyeballed) — an earlier pass of this table had
`--accent`/`--danger`/`--success`/`--warning` a shade too light/pastel
themselves and fell short (as low as 3.1:1 for `--success` on
`--success-bg`); these are the corrected values:

| Token | Light | Dark |
|---|---|---|
| `--accent` | `#6a3ff0` | `#b8a6ff` |
| `--accent-hover` | `#5c2fe0` | `#a58cf7` |
| `--accent-fg` | `#ffffff` | `#1a1130` |
| `--accent-subtle` (selected-tab underline area, focus fill) | `#efeaff` | `#2a2340` |
| `--danger` | `#bb3348` | `#f27a8a` |
| `--danger-bg` | `#fdecef` | `#3a1e24` |
| `--success` | `#0e6e4a` | `#6ee7b0` |
| `--success-bg` | `#e6f7ef` | `#163829` |
| `--warning` *(new)* | `#95630a` | `#f0b84e` |
| `--warning-bg` *(new)* | `#fdf3e0` | `#3a2c10` |

`--warning` is additive — nothing in `PHASE_1_UI_DESIGN.md` currently
needs it, but it's cheap to add now and available if a future surface
needs a "pending/in-progress" tone distinct from danger/success.
`--danger` softened from the current `#d3232f` (pure alarm red) to a
rose-leaning red — still unambiguous, less "error klaxon" for things
like overdue-task text that fire constantly during normal use, not just
on real failures. Note the pattern throughout §7-§9: the pastel
*background* stays as light/soft as originally chosen — only the *text*
color sitting on it was darkened where needed. Pastel fill + a
sufficiently dark ink text is the standard version of this pattern (it's
how Radix/Tailwind-style colored badges stay legible), not a compromise
of the pastel brief.

## 8. Stage color sequence (position-based, pastel chips)

Six hues, cycled by pipeline-stage `sort_order` per
`PHASE_1_UI_DESIGN.md`'s existing position-based rule (unchanged
rationale — stage names/count are tenant-configurable, so color can
never be keyed by name). Deliberately **excludes violet** — that hue is
reserved for `--accent` so a stage color never competes visually with a
primary-action button. Each is a `{bg, fg, border}` triple, rendered as a
pastel-fill chip with same-hue text (Attio/Linear pattern), not a solid
dot:

| # | Hue | Light `bg` / `fg` / `border` | Dark `bg` / `fg` / `border` |
|---|---|---|---|
| 1 | Sky | `#e6f1fc` / `#1f6fb8` / `#c9e2f7` | `#16283a` / `#7ec1f2` / `#234a68` |
| 2 | Teal | `#e1f5f1` / `#0f6c60` / `#bfe8df` | `#123430` / `#5fd8c4` / `#1d5348` |
| 3 | Amber | `#fdf1de` / `#a15c07` / `#f6ddad` | `#3a2a10` / `#f0b84e` / `#5c431c` |
| 4 | Rose | `#fce8ee` / `#b23760` / `#f6cddb` | `#3a1c28` / `#f4a0bb` / `#5c2d3f` |
| 5 | Sage | `#eef3e3` / `#4d6c26` / `#d9e6c2` | `#26301a` / `#b7d688` / `#3c4d28` |
| 6 | Slate | `#eceef2` / `#4b5567` / `#d7dce4` | `#22242e` / `#b7bccb` / `#343747` |

Sage is a distinct olive-leaning green from `--success`'s cleaner
emerald — close hues but different enough at a glance, and they never
appear in the same badge anyway (`is_won` overrides to `--success`
specifically, replacing whatever position color that column would
otherwise get — see below).

Used as: the column header's 3px top-border strip and the card's 3px
left-border strip, both using the hue's **`fg`** value (the deeper tone,
not the pale `bg`) so the strip reads clearly against `--surface`.
Anywhere the stage name renders as a chip (contact detail's deal rows),
use the full `{bg, fg, border}` triple as a standard Badge.

**`is_won`/`is_lost` overrides**, re-colored to the new tokens, same
behavior as `PHASE_1_UI_DESIGN.md` specifies: `is_won` → `--success`/
`--success-bg` treatment + checkmark glyph, replacing the position color
entirely for that column/card. `is_lost` → a flat, dedicated tone
(`#f1eff5`/`#68617a`/`#e6e3ec` light, reusing `--surface-hover` as `bg`
in dark) — deliberately colorless, not just a dimmed version of its
position hue, so a dropped lead reads as "outside the active pipeline"
rather than "a muted version of whatever column it happened to be." Its
light-mode `fg` is its own darker value rather than a straight reuse of
`--text-muted` — `--text-muted` is tuned for legibility against `--bg`,
not against this tone's own pastel background, and reusing it fell short
of the 4.5:1 floor.

## 9. Lead-source colors (fixed enum, pastel chips)

Same chip treatment, five fixed hues (some share a hue family with a
stage-sequence color — acceptable, lead-source badges and stage badges
never appear as the same visual element needing mutual differentiation):

| Source | Light `bg` / `fg` / `border` | Dark `bg` / `fg` / `border` |
|---|---|---|
| Meta | `#e8ecfd` / `#3f4fc7` / `#cfd6f7` | `#1d2140` / `#a3b0f5` / `#2e3560` |
| Google | `#fdefdd` / `#9c4a09` / `#f6d9ad` | `#3a2410` / `#f5a355` / `#5c3a1c` |
| Web | `#eceef2` / `#4b5567` / `#d7dce4` | `#22242e` / `#b7bccb` / `#343747` |
| WhatsApp | `#e3f7e6` / `#187233` / `#c3ebca` | `#163a1e` / `#6fd88a` / `#235c30` |
| Manual | `#f1eef5` / `#6b5f7a` / `#ded6e6` | `#241f2e` / `#b8a8c7` / `#372f45` |

Text label always alongside the chip — unchanged rule from
`PHASE_1_UI_DESIGN.md`, still holds: Meta/Sky (stage) and Meta's own
blue are close in hue but never adjacent in the UI, and the label makes
either one unambiguous regardless.

## 10. Component-level visual pass

**Button** — `--radius`, padding `--space-2 --space-4`, font
`--text-base`/`--weight-medium`.
- *Primary*: `bg: --accent`, `color: --accent-fg`, no border. Hover →
  `--accent-hover`. Disabled → `opacity: .5` (was `.6` — slightly more
  visibly inert).
- *Secondary*: transparent bg, `1px solid --border`, `color: --text-h`.
  Hover → `bg: --surface-hover`.
- *Text* (Cancel, Undo, Retry): no bg/border, `color: --accent`. Hover →
  underline.
- *Destructive* (future delete actions): `bg: --danger`, `color: #fff`.

**Badge** (stage / lead-source / count variants) — universally the
pastel-chip pattern from §8/§9 now, including a `1px solid` border in
the hue's `border` value (Linear's "low-contrast borders" — helps chips
stay legible when a `bg` pastel sits close in lightness to the page).
`--radius-sm`, padding `2px 8px`, `--text-xs`/`--weight-medium`. *Count*
variant (nav task-count, section counts): `bg: --accent-subtle`,
`color: --accent`, pill radius.

**Avatar** — initials fallback, circular. New: background color assigned
*deterministically* by hashing the user's id through the same 6-hue
stage sequence (§8's `bg`/`fg` pair) — today's spec doesn't define a
fallback color at all; this gives every counselor a stable, distinct
pastel avatar without needing a real photo, and it's the same hue set
already used elsewhere so it doesn't introduce a seventh palette.

**Nav bar** — `bg: --elevation-1`, bottom `1px solid --border`. Active
tab: `color: --text-h` + a 2px `--accent` underline — not a filled pill,
so the one saturated color in the nav is a thin line, not a block.
Task-count badge next to "Tasks": Badge count variant.

**Table rows** (contacts list) — rest on `--bg` (page level, not
`--elevation-1`) to stay calm across 25+ rows; hover → `--surface-hover`
— unchanged from current spec, confirming it still fits the new system.

**Pipeline board** — the column itself is the `--elevation-1` "tray";
each card inside is `--elevation-2` so it reads as raised out of the
tray, not flush with it — in dark mode that means the card is *lighter*
than its column (closer-to-viewer convention from §3), in light mode
it's white-on-tinted-grey, the conventional kanban card look. (Using
`--elevation-1` for both, as an earlier draft of this doc had it, would
make cards invisible against their own column in light mode and read as
recessed holes rather than raised cards in dark mode — corrected here
before implementation.) Card: `bg: --elevation-2`, `1px solid --border`,
3px left-border strip in the column's hue `fg` value, `--radius`.
Dragging → `--shadow-lg` + `transform: scale(1.02)`. Column header
top-border strip: same hue `fg`, 3px.

**`SlideOverPanel` / `Toast` / popovers** (won/lost confirm, owner-select)
— `bg: --elevation-2`, `--radius-lg`, `--shadow-md`. In light mode the
`1px solid --border` from `--elevation-2`'s definition (§3) is what
actually separates the panel from the white page behind it — don't omit
it there, it's load-bearing in light mode specifically.

## 11. Theme picker (Light / System / Dark)

New scope, added after the initial refresh shipped — until now, light
vs. dark was decided entirely by the OS/browser's
`prefers-color-scheme`, with no in-app control. This section adds an
explicit override, without dropping the "respects the OS" default
anyone hasn't touched the control gets.

**Mechanism** (for `feature-builder`, not a visual decision but needed
to make the visual part possible): a `data-theme` attribute on
`<html>`, three states:
- Absent (default) → follows `prefers-color-scheme`, exactly today's
  behavior.
- `data-theme="light"` → forces light, even if the OS is dark.
- `data-theme="dark"` → forces dark, even if the OS is light.

`index.css` restructures to the standard three-state pattern — light
values stay the bare `:root` default; the existing
`@media (prefers-color-scheme: dark)` block's selector becomes
`:root:not([data-theme="light"])` (so an explicit light choice beats a
dark OS); and the same dark values are duplicated under a new
`:root[data-theme="dark"]` rule (so an explicit dark choice wins
regardless of OS — a media query alone can never override the OS
setting, only an attribute selector can). Persisted to
`localStorage` (`theme-preference`: `"light" | "dark" | "system"`,
default `"system"`) and applied to `document.documentElement` on load,
before first paint if feasible, to avoid a flash of the wrong theme.

**Control placement** *(superseded — see below)*: originally the Nav
bar's right-side cluster. The Nav bar itself was later replaced by a
left-hand `Sidebar` (vertical nav, grouped links); the control now
lives inline in the sidebar's footer block, next to the avatar/tenant
name/logout row.

**Current mechanism (post-sidebar-redesign, supersedes the two
paragraphs below)**: the original popover-on-click design broke once
the trigger moved into the sidebar footer — a `position: absolute; top:
100%` popover opening downward from the bottom of a `100svh` sidebar
renders below the visible viewport, making the control unreachable.
Replaced with an always-visible three-icon segmented control (`role="radiogroup"`,
each option `role="radio"`), no popover, no overflow risk. Icons are
plain Unicode glyphs (☀ light / ◐ system / ☾ dark) — this app has no
SVG icon library dependency, and these are flat monochrome dingfonts
rather than color emoji. This explicitly supersedes the "no new
iconography" call below: that reasoning applied to a *dropdown of text
rows*, not an icon-only inline segmented control, where a text label
next to each of three tiny buttons would be the one that reads as
clutter. Selected state is persistent (`background:
--elevation-2` + `--shadow-sm` + `color: --accent` on the active
segment), not hover-only; unselected segments get a lighter
`--surface-hover` on `:hover` only. `aria-label`/`title` carry the
text name for accessibility since the visible content is icon-only.

**Popover** *(historical — removed)*: the original design used a
`SlideOverPanel`-style popover (§10 pattern) with three plain-text
rows. No longer applicable; see the segmented-control replacement
above.

**States**: only one — each segment is either selected or not; there's
no loading/error state since this never touches the network.

---

## Deferred / out of scope

Same as `PHASE_1_UI_DESIGN.md`'s own deferred list, unchanged: no
animation beyond CSS transitions, no print/export layout. Also deferred
here: a dedicated illustration/icon set (current app has none; adding
one is a bigger scope than "refresh the palette" and wasn't asked for).
§11's theme picker is the one exception — it now uses three plain
Unicode glyphs, not an SVG icon set, per an explicit later ask; see §11
for why that's a narrower exception, not a reversal of this deferral.

Nothing kicked back to `ux-designer` — this is a pure token/visual pass,
no flow decisions were touched or needed.
