# Phase 1 UX flows — Core CRM

Produced by the `ux-designer` skill against `PHASE_1_PLAN.md`. Flow and
interaction design only — no visual/component styling (that's
`ui-designer`, next) and no code.

## Cross-cutting

**Nav**: Contacts | Pipeline | Tasks. Tasks shows a badge count of the
counselor's own open tasks (`?assignee_id=me&status=open`) — the single
strongest "what do I do right now" signal for the counselor persona.

**Persona default**: every list defaults to scoped-to-me first
(`owner_id=me` on contacts, `assignee_id=me` on tasks), with an explicit
toggle to see everyone's. Managers/admins toggle off by habit; counselors
usually don't need to.

**Lead source is always visible**: shown as a badge on every contact row
and at the top of contact detail — never buried behind a click. A lead's
channel (Meta/Google/web/WhatsApp) changes what a counselor expects the
next contact attempt to look like, so it can't be secondary information.

**Not in this phase, so not in these flows**: no free-form "log an
activity" action — `PHASE_1_PLAN.md` §4.5 says Phase 1 writes exactly one
activity type (`deal_stage_changed`), so the activity log only ever shows
stage-change history, not calls/emails/notes. No automation, no reminders,
no SLA alerts — `stage_changed_at`/days-in-stage is a passive display
value only, nothing fires on it yet (that's Phase 3). Force-create past a
dedupe conflict does not exist yet (`PHASE_1_PLAN.md` §5 explicitly defers
it) — the only resolutions below are "view the existing contact" or
"go back and fix the duplicate field."

---

## 1. Contacts

### 1.1 List

1. Entry: nav → Contacts. Default: `owner_id=me`, sorted `-updated_at`.
2. Search box (name/email/phone) and filter chips (lead source, owner —
   with an "everyone" toggle for managers). Filters compose with search.
3. Row click → contact detail.
4. Empty state (new tenant, zero contacts): "No leads yet" + primary
   "New Contact" action — this is the only entry point a brand-new tenant
   has, so it can't be a quiet empty table.
5. Pagination: numbered pages (matches the backend's `page`/`page_size`
   contract exactly — no infinite-scroll behavior the API doesn't support).

### 1.2 Create contact

1. "New Contact" (from list header, or empty state) opens a **slide-over
   panel**, not a full-page navigation — the list stays visible behind it,
   so creating a contact never loses the counselor's current
   search/filter/scroll position.
2. Fields: Full name (required), Email, Phone, Lead source (Meta/Google/
   Web/WhatsApp/Manual), Owner (defaults to self).
3. Submit → `POST /api/v1/contacts`.
   - **Success**: panel closes, navigate straight to the new contact's
     detail view. (Not back to the list — the next thing a counselor does
     after logging a lead is almost always add a deal or a task, so land
     them where that happens.)
   - **409 Conflict** (dedupe hit on email or phone): panel content is
     replaced (not closed) with a "Possible duplicate" state showing the
     *existing* contact's name, email, phone, and owner (from
     `error.details`). Two actions: **"Open existing contact"** (primary —
     navigates there, discards the new-contact draft) and **"Go back"**
     (secondary — returns to the form with everything the counselor typed
     still filled in, so a typo'd email/phone is a one-field fix, not a
     re-type). No third "create anyway" option — that path doesn't exist
     in this phase.
   - **Validation error**: inline, per-field, form stays open, entered
     values preserved.

### 1.3 Detail

Sections, in order:

1. **Header** — name, lead source badge, owner, created date.
2. **Deals** — this contact's deals (course + current stage badge each).
   "+ New Deal" action (see 2.2). A contact can have several concurrent
   deals; each is its own row here, not collapsed into one status.
3. **Tasks** — tasks linked to this contact (open first, then done,
   collapsed). "+ Add task" pre-fills `contact_id` (see 3.2).
4. **Documents** — uploaded files with download links. "+ Upload" (see 4).
5. **Activity** — chronological `deal_stage_changed` events only (which
   deal, old stage → new stage, who, when). If there are no deals yet,
   this section is empty with a one-line "No activity yet" — not hidden
   entirely, so it's clear the section exists once a deal starts moving.

Edit: inline field editing on the header (click a field, edit, blur to
save via `PATCH`) rather than a separate edit mode — these are short
fields, a whole edit-mode toggle is unnecessary friction.

---

## 2. Pipeline board

### 2.1 Board layout

1. Entry: nav → Pipeline.
2. Columns = `pipeline_stages` ordered by `sort_order`, fetched live —
   **never a hardcoded stage list or count**, since tenants can rename/
   reorder their own stages. Many-column tenants scroll the column area
   horizontally; columns don't wrap.
3. Each card: contact name, course, owner avatar, days-in-stage (derived
   from `stage_changed_at` — a passive number, not a warning color; no
   SLA alerting exists yet).
4. Filter bar above the board: owner (defaults to me, toggle for
   everyone), same pattern as the contacts list.

### 2.2 Create a deal

Two entry points, same underlying steps:

- From a contact's detail page ("+ New Deal"): contact is already known.
- From the board header ("+ New Deal"): first step is search-or-create a
  contact (reuses the contacts search from 1.1, or the create-contact
  panel from 1.2 inline) — this composes existing endpoints, it doesn't
  add a new one.

Then: course picker, stage picker (defaults to the first non-`is_won`/
`is_lost` stage by `sort_order`) → `POST /api/v1/contacts/{id}/deals` →
new card appears on the board in that stage and in the contact's Deals
section.

### 2.3 Drag-and-drop stage change

1. Counselor drags a card from column A to column B.
2. **Optimistic**: the card moves in the UI immediately, before any
   network call — this is the single highest-frequency action in the
   whole app, it cannot wait on a round trip.
3. Background: `PATCH /api/v1/deals/{id} {stage_id: B}`.
4. **Success**: a brief, subtle highlight fade on the card — no blocking
   toast. A success toast on every single-second action would become
   noise fast for someone moving a dozen cards a day.
5. **Failure** (network error, or the deal was moved by someone else
   concurrently): card **reverts** to column A, and a toast appears:
   "Couldn't move [Contact] to [Stage] — Retry" with a retry action that
   re-issues the same `PATCH`.
6. **Dropping into a `is_won`/`is_lost` stage**: a small inline confirm
   popover anchored to the card ("Mark as Enrolled?" / "Mark as Dropped?"
   — Confirm / Cancel), not a full modal. These are usually terminal and
   harder to reverse, so a stray drag shouldn't silently commit one, but
   the confirm has to stay fast, not a page-blocking dialog.

---

## 3. Tasks

### 3.1 List / board

1. Entry: nav → Tasks. Default filter: `assignee_id=me&status=open`,
   sorted by `due_at` ascending — most urgent first, by default, always.
2. View toggle: **List** (default — grouped Overdue / Today / Upcoming,
   most scannable for due-date urgency) vs **Board** (columns Open/Done,
   per `FEATURES_AND_PLAN.md`'s explicit "list/board view").
3. Overdue tasks: `due_at` in the past shown with a red due-date — a
   passive flag only, nothing fires automatically (no reminders yet).

### 3.2 Create a task

1. "+ New Task" — from the nav (global; requires picking a contact, since
   `contact_id` is required on the model) or from a contact's detail page
   (pre-fills `contact_id`, and `deal_id` if opened from a specific deal).
2. Fields: Title (required), description, assignee (defaults to self),
   due date/time, contact (required — search-or-select if not pre-filled).
3. Submit → `POST /api/v1/tasks`.
   - Assigned to self: appears immediately at the correct position in the
     counselor's own list.
   - **Assigned to a teammate**: it will not appear in the creator's own
     "mine" view afterward, so a confirmation toast fires — "Task
     assigned to [Name]" — that's the only feedback the creator gets that
     it actually went through, since it otherwise vanishes.

### 3.3 Complete a task

1. Checkbox/complete action on a row or card.
2. **Optimistic**: shows as done (strikethrough) immediately, with an
   **"Undo"** affordance visible for a few seconds before the task drops
   out of the open-filtered view — completing via checkbox is exactly the
   kind of dense-list action that gets misclicked, so instant, reversible
   feedback matters more than a confirm dialog would.
3. Background: `PATCH /api/v1/tasks/{id} {status: 'done'}`.
4. **Failure**: revert to open, toast with retry — same pattern as the
   pipeline drag failure (3.2.5).

---

## 4. Document upload

### 4.1 Upload

Entry: contact detail → Documents → "+ Upload" (native file picker;
drag-and-drop onto the panel is a reasonable later enhancement, not
required here).

Steps, with the two-call backend flow surfaced as one continuous UI state,
not two:

1. File selected → row appears immediately in the Documents list with an
   **"Uploading…"** state and a determinate progress bar.
2. `POST /api/v1/contacts/{id}/documents/upload-url` → presigned PUT URL
   + `s3_key`.
3. Direct client `PUT` to that URL — progress bar tracks this upload.
4. `POST /api/v1/contacts/{id}/documents` to confirm/create the row.
5. Row updates from "Uploading…" to final state: filename, size,
   uploaded-by, timestamp, download icon.

Each file uploads independently — multiple concurrent uploads each get
their own row/progress, and the counselor isn't blocked from doing
anything else while one is in flight.

**Failure branches** (each surfaces "X failed — Retry" on that file's row,
not a global error):

- **Step 2 fails** (can't get an upload URL): retry re-runs from step 2.
- **Step 3 fails** (the PUT itself drops): retry re-runs from step 2 —
  request a fresh presigned URL rather than reuse one that may have
  expired mid-failure.
- **Step 4 fails** (file landed in storage, but confirming the row
  failed): the file now exists in S3 with no DB row pointing at it. Retry
  automatically 2–3 times with backoff before surfacing anything to the
  counselor. If it still fails, show "Uploaded but couldn't save — Retry"
  — that retry re-attempts **only step 4**, reusing the already-returned
  `s3_key`, so the file is never re-uploaded.

### 4.2 Download

1. Click a document row → `GET /api/v1/documents/{id}/download-url`.
2. Browser opens/downloads the returned URL immediately — it's
   short-lived, so it's requested at click time, never pre-fetched or
   cached ahead of that.
3. Failure (network/expired session): inline error on that row, retry.

---

## Handoff

For `ui-designer`: the surfaces to design are the contacts list, the
create-contact panel (including its 409 conflict state), contact detail
(5 sections above), the pipeline board (including the drag states and the
won/lost confirm popover), the task list and board views, and the
documents panel (including per-row upload progress/failure and the
uploading/uploaded/failed states). For `feature-builder`: every optimistic
update above has an explicit revert-on-failure path — implement the
failure branch in the same commit as the happy path, not as a follow-up.
