# Phase 1 UI design — Core CRM

Produced by the `ui-designer` skill against `PHASE_1_UX_FLOWS.md` (flow
decisions, not re-derived here) and `PHASE_1_PLAN.md` (data/API contract).
Visual/component description only — precise enough for `feature-builder`
to implement directly (`PHASE_1_PLAN.md` §7 steps 18–21). No code, no new
flow decisions.

## Design tokens

Extends `frontend/src/index.css`'s existing custom properties
(`--text`/`--text-h`/`--bg`/`--border`/`--sans`, light/dark via
`prefers-color-scheme`) rather than replacing them. New tokens, both
palettes:

| Token | Light | Dark | Use |
|---|---|---|---|
| `--surface` | `#f7f7f8` | `#1c1d24` | Cards, panels, nav bar — one step off `--bg` for layering |
| `--surface-hover` | `#eeeef0` | `#24252d` | Row/card hover |
| `--text-muted` | `#9a94a3` | `#6b7280` | Secondary text (meta, timestamps) |
| `--accent` | `#aa3bff` | `#c084fc` | Primary actions — reuses the existing (currently unused) `--accent`/`--accent-border` scale already defined in `index.css`'s dark block, extended to light |
| `--accent-fg` | `#fff` | `#16171d` | Text/icons on `--accent` |
| `--danger` | `#d3232f` | `#f87171` | Errors, overdue, failed states |
| `--danger-bg` | `#fdecec` | `#3a1f22` | Danger row/banner backgrounds |
| `--success` | `#1a7f4b` | `#4ade80` | Won stage treatment |
| `--radius` | `6px` | same | Single radius, matches the button style already in `index.css` |

**Stage color sequence** — six muted, position-assigned tints (not
semantic — see below): `#5b8def #a855f7 #d97706 #0d9488 #ec4899 #64748b`,
cycled by column index. Used as a column's top-border strip and a card's
left-border strip.

**Why position-based, not name-based**: stage names/count are
tenant-configurable (`PHASE_1_PLAN.md` §4.2), so a fixed name→color map
would break or collide the moment a tenant renames a stage or two tenants
pick overlapping names. Position-in-`sort_order` is the one thing that's
always stable within a render, so color is assigned by column index, not
by matching stage name/id to anything.

**`is_won`/`is_lost` override the sequence**, since those two flags carry
real, fixed meaning regardless of what the tenant named the stage:
`is_won` → `--success` border + a small checkmark glyph next to the
column/badge name. `is_lost` → muted gray (desaturate the card ~15%
opacity) + a small dash glyph — deliberately *not* red/alarming, since a
dropped lead is a normal business outcome, not an error state.

**Color is never the only signal**: every stage badge/column header shows
the stage *name* as text plus its color — matches `ui-designer`'s
standing rule and matters doubly here since tenants can pick colliding
hues for differently-named stages.

**Lead source badges are the one place fixed color-by-value is fine** —
`lead_source` is a fixed enum (Meta/Google/Web/WhatsApp/Manual), not a
tenant setting, so: Meta `#5b8def`, Google `#d97706`, Web `#64748b`,
WhatsApp `#22c55e`, Manual `#9a94a3`. Text label always shown alongside.

## Layout

- **Nav** (replaces `MeShell.tsx`'s standalone full-page rendering):
  fixed top bar, 56px, `--surface` background, `--border` bottom border.
  Left: app name + tabs (Contacts / Pipeline / Tasks — Tasks carries a
  small `--accent` badge with the counselor's own open-task count, only
  rendered when > 0). Right: tenant name (muted) + user name/avatar +
  logout — this is `MeShell`'s current content, relocated into the
  persistent corner rather than being the whole page.
- **List/detail pages** (Contacts list, Contact detail, Tasks): content
  max-width ~1280px, centered, `--bg` background.
- **Pipeline board**: full-bleed, no max-width — columns need the room,
  and the column row scrolls horizontally rather than wrapping.

## Shared components (build once, reuse everywhere)

`Badge` (lead source / stage / count variants), `Avatar` (initials
fallback), `Button` (primary/secondary/text), `SlideOverPanel` (shared by
create-contact and create-task — same component, different form content),
`Toast`, `Skeleton` (row/card/block variants), `EmptyState` (icon-free:
headline + optional subtext + optional action).

---

## 1. Contacts list

Header row: "Contacts" title, search input, filter chips (lead source
select, owner "Mine"/"Everyone" toggle), "+ New Contact" (primary,
top-right).

Table columns: Name, Lead source (`Badge`), Owner (`Avatar` + name),
Updated (relative time). Row hover → `--surface-hover`; click → detail.
Footer: numbered pagination (matches `page`/`page_size` exactly — no
infinite scroll).

**States**: Loading — 5 skeleton rows. Empty (zero contacts ever) —
`EmptyState` "No leads yet" + "New Contact" action. Empty (filtered, zero
matches) — distinct copy, "No contacts match your filters" + "Clear
filters" link (the fix differs from true-empty, so the copy must too).
Error — inline retry banner above a blank table area.

## 2. Create-contact panel

`SlideOverPanel`, ~420px, right-anchored, page dims behind it (click-out
or Esc closes). Header "New Contact" + close. Fields stacked: Full name*,
Email, Phone, Lead source (select), Owner (select, default self, closed
state shows `Avatar` + name). Footer: "Cancel" (text, left) / "Create
Contact" (primary, right — shows spinner + "Creating…" while in flight,
disabled).

**Validation error**: red border + inline message under the field, panel
stays open.

**409 state** — *not* a new panel, the same panel's content swaps in
place: "We found a possible duplicate" headline, then a compact read-only
card (existing contact's name/email/phone/owner, same row density as the
list). Two actions: "Open existing contact" (primary) / "Go back"
(secondary — returns to the form, values still filled). No third option —
force-create doesn't exist in this phase (`PHASE_1_UX_FLOWS.md` §1.2).

## 3. Contact detail

Two-column on wide viewports (density-first for an internal tool); single
column, `PHASE_1_UX_FLOWS.md`'s exact order, on narrow ones.

- **Left column**: Header → Deals → Activity (Activity is deal-stage
  history, so it reads naturally right under Deals).
- **Right column**: Tasks → Documents (reference panels a counselor
  checks while working the left column, not primary reading order).

**Header**: large name (click → inline edit, input in place, blur/Enter
saves, small inline spinner mid-save, revert + error flash on failure),
lead-source `Badge` beside it, owner `Avatar` + name (click → select
popover), muted "Created {date}".

**Deals**: section header "Deals" + count `Badge` + "+ New Deal"
(top-right). Row per deal: course name, stage `Badge` — **using the same
position-based stage color as the pipeline board**, so a deal's badge
here visually matches its board column. Not a stage-change control:
stage changes happen only via the board's drag interaction
(`PHASE_1_UX_FLOWS.md` §2.3) — keeping one place for that action avoids
two UIs that could disagree.

**Tasks**: header "Tasks" + count + "+ Add task". Open tasks first
(checkbox, title, due date — `--danger` if overdue), then a collapsed "X
completed" disclosure.

**Documents**: header "Documents" + "+ Upload". Row states in §6.

**Activity**: vertical timeline (dot + connector line), each entry
"{course} moved {old stage} → {new stage} · {actor} · {relative time}".
Empty (zero deals) — muted "No activity yet", not hidden.

**States**: each section loads/errors **independently** — `PHASE_1_PLAN.md`
§5 has Deals/Tasks/Documents/Activity as separate calls, so one slow or
failed section (skeleton block, or inline "Couldn't load — Retry") never
blocks the rest of the page.

## 4. Pipeline board

Filter bar: owner "Mine"/"Everyone" toggle, "+ New Deal" (right).

**Columns**: built from `GET /api/v1/pipeline-stages`, in `sort_order` —
count and names are never assumed fixed. Header: stage name, count
`Badge`, top-border strip in that column's sequence color; `is_won` adds
a checkmark glyph, `is_lost` gets the muted/desaturated treatment. Fixed
column width (~280px); the column row scrolls horizontally, columns don't
wrap.

**Card**: contact name (bold), course (muted, smaller), owner `Avatar`
(small, bottom-left), days-in-stage (muted, bottom-right, e.g. "3d" — a
passive number, not a warning color; no SLA logic exists yet). Left
border in the column's sequence color, so a card reads its column even
mid-scroll.

**Drag states** (per `PHASE_1_UX_FLOWS.md` §2.3):
- Dragging: card lifts (larger shadow), source slot shows a dashed
  placeholder.
- Over a valid column: subtle background tint on that column.
- Success: soft `--accent` flash across the card (~600ms), then settles —
  no toast; this fires on essentially every card move, a toast per move
  would be noise.
- Failure: card animates back to its original slot, `Toast` (bottom):
  "Couldn't move {Contact} to {Stage} — Retry".
- Drop into `is_won`/`is_lost`: small popover anchored at the drop point
  (not a centered modal) — "Mark as {stage name}?" Confirm/Cancel; Cancel
  plays the same revert animation as a failure.

**States**: Loading — generic 3-column skeleton first (stage count isn't
known until `pipeline-stages` resolves), replaced by real columns, then
cards populate as `GET /api/v1/deals` resolves — two independent loading
phases, matching the two separate calls. Empty column — faint dashed
placeholder, no message needed (the header already explains the column).
Error — full-width retry banner above the board area.

## 5. Tasks

View toggle (List / Board, segmented control, top-right). List is
default.

**List**: grouped headers "Overdue" (`--danger` text) / "Today" /
"Upcoming" — only groups with items render. Row: checkbox, title, contact
name (link), due date/time (`--danger` if overdue), assignee `Avatar`
(shown only in "Everyone" mode — redundant in "Mine").

**Board**: Open / Done columns, same row content adapted to card form.

**Complete**: checkbox click → immediate strikethrough + inline "Undo"
text-button where the due-date was, ~5s, then fades out of the open view.
Undo restores instantly and either cancels the in-flight `PATCH` or fires
a reversing one if it already landed.

**Create-task**: reuses `SlideOverPanel`. Fields: Title*, Description,
Assignee (default self), Due date/time, Contact (search-select, required
— pre-filled and locked if opened from a contact page).

**States**: Loading — skeleton rows/cards. Empty ("mine" + open, zero) —
positive framing, "You're all caught up", no action needed. Empty
(someone else, zero) — neutral "No open tasks." Error — same inline
retry-banner pattern as the contacts list.

## 6. Documents (rows within Contact detail's Documents section)

Row: file-type icon, filename, size/meta line.

- **Uploading**: meta line replaced by a determinate progress bar +
  percentage; row slightly lower-opacity (pending, not yet committed).
- **Uploaded**: meta = "uploaded by {name} · {relative time} · {size}",
  download icon on the right.
- **Failed** (any of `PHASE_1_UX_FLOWS.md` §4.1's three branches — start,
  PUT, or confirm failure): meta line replaced by `--danger` text + inline
  "Retry" text-button; row keeps a `--danger`-tinted left border until
  resolved. Copy varies by branch ("Couldn't start upload", "Upload
  failed", "Uploaded but couldn't save") but the visual treatment is
  identical across all three.

Multiple concurrent uploads: fully independent rows, no shared/blocking
progress UI.

---

## States coverage summary

Covered explicitly for every surface above: empty, loading, populated,
error — plus the specific in-flight/failure states each surface's flow
called for (409 conflict, drag success/failure/confirm, upload's three
failure branches, task-complete undo).

**Deferred, deliberately** — internal tool, no one asked for these:
dark-mode-specific redesign beyond the existing token-driven light/dark
split; any animation beyond CSS transitions; a print/export layout for
any list. Not a design decision, but flagged for `feature-builder`:
native HTML5 drag-and-drop is fiddly for reordering across columns —
worth a quick evaluation of a small library rather than hand-rolling it,
though that choice belongs to implementation, not this doc.

**Nothing kicked back to `ux-designer`** — `PHASE_1_UX_FLOWS.md` already
resolved every edge case this design needed (dedupe resolution, drag
failure handling, upload failure branches); no open flow questions
remain.
