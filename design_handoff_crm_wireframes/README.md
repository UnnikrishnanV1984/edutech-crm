# Handoff: White-label CRM — wireframe set (light + dark)

## Overview
Wireframes for the multi-tenant white-label CRM in `edutech-crm`: Dashboard,
Pipelines, Contacts, Contact detail, Tasks, Escalations, Follow-ups, Workflow
rules, and a single tabbed **Configurations** shell covering SLA policies,
External integrations, Pipelines, **Branding (white-label logo/header upload)**
and Users & roles — plus a responsive phone set. 13 screens, one direction each.
Everything renders in both light and dark from one token set.

## About the design files
The files in this bundle are **design references authored in HTML** — prototypes
of intended structure, layout and behaviour. They are **not production code to
copy**. Recreate them inside `edutech-crm/frontend` using its established
patterns (React 19 + Vite, `src/components/*`, CSS custom properties in
`src/index.css`, react-router NavLink nav, existing `Badge`/`Avatar`/`Card`/
`Button` primitives). Do not introduce a new styling library.

## Fidelity
**Low-fidelity wireframes.** Grey bars and hatched wells stand in for real copy,
data and imagery. Treat the *layout, hierarchy, grouping, states and controls* as
the spec; take the *visual styling* from the Classical design system tokens in
this bundle (`styles.css` + `tokens.css`) mapped onto the app's existing
`--*` variables in `frontend/src/index.css`.

## Screens / views

All desktop frames share one shell: a **190px sidebar** (border-right hairline,
surface `--s`) + fluid main column; sidebar holds the tenant **logo well**
(38px tall, dashed `--ln3`, 8px radius), then nav groups **Workspace**
(Dashboard, Pipelines, Contacts, Tasks) / **Team** (Escalations, Follow-ups,
Workflow rules) / **Admin** (Configurations), matching the role gates already in
`Sidebar.tsx` (Team hidden from counselor, Admin admin-only), and a footer with
avatar + user name + tenant name. Active nav item: `--at` fill, 2px `--ac`
left border, right side pill-rounded. Page header: hairline bottom border,
24px Cormorant Garamond title, italic sub-label, actions right-aligned
(primary = accent-outlined, never filled).

1. **Dashboard** — four metric cards (label + 30px tabular numeral + trend bar),
   then a 1.4:1 row of "Pipeline by stage" bar chart and "My queue today"
   (checkbox rows with Overdue/Today pills), then a Team SLA table
   (Counselor / On track / At risk / Breached / Avg first response). Manager and
   counselor variants differ only in whether the Team SLA block renders.
2. **Pipelines** — pipeline switcher in the header; filter strip (Mine/Everyone,
   Lead source, Course, SLA state, Board/Table). Columns are 196px, built from
   the tenant's stage config in `sort_order` — never a fixed set — and the row
   scrolls horizontally (`overflow-x:auto`). Card: contact bar, course bar,
   owner avatar, days-in-stage, 2px left rule (accent when SLA at risk, plus a
   labelled "SLA" pill — never colour alone). Won stage: accent header rule +
   ✓ glyph; lost: 55% opacity + — glyph. Drag states: lifted card
   (soft shadow, .6° tilt), dashed drop target in the source slot.
3. **Contacts** — 196px filter rail (owner toggle, lead-source checkboxes, stage
   chips, follow-up flag) + full-width table (Name, Lead source, Stage, Owner,
   SLA, Updated). Selecting rows swaps the toolbar in place for bulk actions
   (Assign owner, Add task, Flag follow-up). Numbered pagination + per-page.
4. **Contact detail** — header (name, lead-source pill, SLA pill, actions) over a
   meta row (Owner/Phone/Email/Created). Body is 1.5:1 — left: Deals table,
   Activity timeline (dot + connector); right: SLA card with progress + Escalate,
   Tasks, Documents (upload progress + failed row), Follow-up flag. Each panel
   loads and errors independently.
5. **Tasks** — Mine/Everyone, List/Board toggle; groups Overdue (accent rule) /
   Today / Upcoming, only rendered when non-empty. Completed row: struck bar +
   inline Undo replacing the due date (~5s). Empty state: "You're all caught up".
6. **Escalations** — counters (Open, Breaching within 1h, Avg time to resolve,
   Reopened), status filter pills, table (Contact/deal, Reason, Rule, Owner,
   Status, Opened) with a right-anchored **376px resolve drawer**: breach detail,
   radio outcomes (Contacted-close / Reassign / Snooze), note, Cancel/Resolve.
   Same drawer component as create-contact and create-task.
7. **Follow-ups** — four columns Overdue / Due today / This week / Snoozed as
   working queues; each card carries Reason + Snooze + Done inline, so a flag can
   be cleared without opening the record. Below: full flag table with filters.
8. **Workflow rules** — table (Rule, Trigger, Actions, Last run, Status) + run
   sparkline, beside a 392px **when / if / then builder**: trigger select,
   condition rows (field / operator / value with AND), ordered action cards,
   plain-English preview, Test run + Save.
9. **Configurations — SLA** — one tabbed shell (SLA · Integrations · Pipelines ·
   Branding · Users & roles; active tab = 3px accent underline) replacing four
   separate sidebar pages. Policy table + breach behaviour + 352px detail panel
   (targets, business-hours day pills, hours, holiday calendar).
10. **Configurations — Integrations** — per-source health cards (Connected /
    Needs auth / Add a source), table (Source, Account, Status, Field mapping,
    Conversion target, Last synced), explicit source→CRM field mapping rows, and
    a webhook panel (endpoint, secret + Rotate, delivery strip, Send test event).
11. **Configurations — Pipelines** — pipeline list rail + drag-to-reorder stage
    rows (grip, position chip, name, SLA chip, Edit), dashed insertion gap,
    stage flags (won / lost / requires invoice / allows rework), templates, and a
    boxed accent-ruled destructive **Reset** kept away from Save.
12. **Configurations — Branding (white-label)** — the key admin screen. Two
    upload wells: **square logo mark** and **wide header lockup (max 320×64)**,
    both dashed `--ln3`, hatched, with Browse; plus favicon, login backdrop,
    company display name, accent swatch picker, header background (Light/Dark/
    Accent), typeface, custom domain, and a contrast check. Right column: **live
    preview** with App/Login/Email tabs rendering the tenant mark in a miniature
    app shell, a "Where branding appears" checklist (app, login, emails,
    invoices) and version history with Restore. Nothing goes live until
    **Publish branding**; Discard reverts the draft.
13. **Responsive (phone, 334px)** — bottom tab bar (Home/Pipe/Contact/Tasks/
    More); dashboard = counters + queue cards; pipeline = one stage at a time
    with a swipeable stage bar and an explicit "Move ▾" instead of drag; contact
    = header actions (Call/WhatsApp/Note), tabbed Deals/Tasks/Activity/Docs, and
    a sticky Advance-stage bar. The tenant mark sits in the app bar.

## Interactions & behaviour
- Nav: react-router links; active state = tint + accent left rule (position and
  fill, not colour alone).
- Board: drag to change stage; drop into a won/lost stage opens a small popover
  anchored at the drop point ("Mark as {stage}?"); failure animates the card back
  and shows a retry toast. Success flashes the card ~600ms, no toast.
- Drawers (create contact / create task / resolve escalation / connect source):
  right-anchored, ~376–420px, page dims behind, Esc or click-out closes,
  in-flight button shows a spinner and disables.
- Duplicate contact (409): the same drawer's content swaps in place to
  "We found a possible duplicate" with Open existing / Go back.
- Task complete: optimistic strikethrough + inline Undo for ~5s.
- Branding: uploads are staged as a draft; Publish commits, Discard reverts;
  contrast check warns when accent-on-header falls under 3:1.
- Every list has four states — loading (skeleton rows/cards), empty (distinct
  copy for never-any vs filtered-none), populated, error (inline retry banner).
- Responsive: ≥1280px two-column detail and full board; <900px the filter rail
  collapses to a Filters button, detail becomes single column (left order first),
  board becomes one-stage-at-a-time.

## State management
Per screen: filter/query state (owner scope, lead source, stage, SLA state,
search, page, page_size), selection set for bulk actions, drawer open + form
state + in-flight/error, optimistic stage move (with rollback), optimistic task
complete (with undo window), branding draft (assets + palette + preview surface)
separate from published branding, and the tenant theme (light/dark) persisted per
user. Data: paginated contacts, deals by pipeline stage, tasks grouped by due
bucket, escalations, follow-up flags, workflow rules + run history, SLA policies,
lead-source connections, pipelines/stages, branding config.

## Design tokens
Colour (light → dark), from `tokens.css`:

| Token | Role | Light | Dark |
|---|---|---|---|
| `--p` | paper ground | #fdfcfa | #1b1917 |
| `--p2` | raised surface | #ffffff | #221f1c |
| `--s` | subtle surface | #faf8f4 | #1f1c1a |
| `--s2` | quiet fill | #f7f5ef | #272320 |
| `--at` | accent tint | #f7f0e2 | #2f2618 |
| `--ink` / `--ink2` | text / secondary | #201f1d / #4c473f | #efe9de / #cec7ba |
| `--mut` | muted labels | #6f6a61 | #a49b8c |
| `--ln` / `--ln2` / `--ln3` | hairline / strong / dashed | #e6e2d8 / #d8d3c9 / #cfc8b8 | #332f29 / #3e3931 / #4d463c |
| `--bar` / `--bar2` | placeholder bars | #e5e1d7 / #ece8de | #37322b / #2d2924 |
| `--ac` / `--act` / `--acl` | accent / accent text / accent line | #b68235 / #8a6323 / #e0cda6 | #c99a4e / #dcb877 / #6a5533 |

Accent is applied as **stroke** — outlines, 2px rules, pill borders, tinted
fills — never as a solid block; primary buttons are accent-outlined.

Type: Cormorant Garamond 400 for headings (24px page title, 30px display
numerals, tabular figures) over Lora 400/500 for body (13px base, 12px table,
11.5px fields, 9.5px uppercase labels at .14em tracking). Bold is not used.

Radius (rounded everywhere): pills 999px (chips, bars, active nav, avatars),
cards 10px, outer frames 14px, buttons/fields/thin cards 8px, misc 5px,
phone frames 22px.

Spacing: 22px page padding, 20px section gap, 16px row gap, 15px card padding,
9–13px control gaps. Elevation is a whisper: `0 1px 2px rgba(32,31,29,.05)`,
drawers `-16px 0 28px rgba(...)`.

## Assets
None real. Hatched dashed wells are placeholders for tenant logo, header lockup,
favicon and login backdrop; grey pills stand in for copy; the bar/spark charts
are placeholder geometry, not data. Icons: use **Lucide** (per the design system)
— the wireframes deliberately show none.

## Files
- `CRM Wireframes.dc.html` — the wireframe set (13 screens + light/dark
  palette board). Open it in a browser next to `support.js`; the Theme control
  switches light/dark.
- `support.js` — runtime needed to open the file above locally.
- `tokens.css` — light + dark token set, ready to merge into
  `frontend/src/index.css`.
- `styles.css` — the Classical design system stylesheet (source of truth for
  colour ramps, type, spacing, radii, and the `.btn`/`.tag`/`.card`/
  `.table`/`.field`/`.dialog`/`.hr`/`.plate` component classes).
- Source of truth for behaviour already documented in the repo:
  `PHASE_1_UX_FLOWS.md`, `PHASE_1_UI_DESIGN.md`, `PHASE_1_PLAN.md`.

## Notes for the implementer
- Stage colour must stay **position-derived** (index in `sort_order`), with
  `is_won`/`is_lost` overriding — tenants rename and reorder stages.
- Branding is per-tenant and must reach app shell, login, outbound email and
  PDFs; keep published vs draft separate and version it.
- Wireframes intentionally omit icons, real copy and imagery — ask before
  inventing any.
