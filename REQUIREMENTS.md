# CRM Requirements — Roles, Workflows, SLA, Escalation, Dashboards

This document elaborates the operational layer of the CRM: who can do what,
how work is automated, how service levels are enforced, what happens when
something is at risk or blocked, and what each role sees day to day. It
extends `FEATURES_AND_PLAN.md` (which lists *what* gets built and *when*)
and `DATABASE_SCHEMA.md` (which lists the entities) with the *behavior*
those entities need to support.

## 1. Roles & RBAC

### 1.1 Roles

| Role | Who | Scope |
|---|---|---|
| **Admin** | Tenant admin, ops lead | Full tenant configuration and visibility |
| **Manager** | Admissions/sales manager, team lead | Own team's leads, escalations, reporting |
| **Staff** | Counselor / telecaller | Own assigned leads and tasks |
| **Auditor** (optional) | Compliance/read-only reviewer | Read-only across the tenant, no write actions |

Roles are realm/tenant-scoped in Keycloak (see `ARCHITECTURE.md` Section 4)
and carried on the access token. The BFF resolves role alongside
`tenant_id`; FastAPI enforces it per-endpoint and, for Staff, per-row
(a counselor's queries are always additionally scoped to
`owner_id = current_user`, not just `tenant_id`).

### 1.2 Permission matrix

| Capability | Admin | Manager | Staff |
|---|:---:|:---:|:---:|
| View own leads/tasks | ✓ | ✓ | ✓ |
| View team's leads/tasks | ✓ | ✓ | — |
| View org-wide leads/tasks | ✓ | — | — |
| Create/edit contacts | ✓ | ✓ | ✓ |
| Reassign leads | ✓ | ✓ (within team) | — |
| Configure pipeline stages | ✓ | — | — |
| Configure workflow rules | ✓ | propose only* | — |
| Configure SLA policies | ✓ | — | — |
| Acknowledge/resolve escalations | ✓ | ✓ (own team) | can raise, not resolve |
| Manage users & roles | ✓ | — | — |
| View org-wide reports/forecast | ✓ | team-level only | own stats only |
| Manage integrations (Meta/Google/WhatsApp) | ✓ | — | — |
| Export data | ✓ | team-level | — |
| View audit log | ✓ | — | — |

\* Managers can propose a workflow rule change; it requires Admin approval
before activation — see Section 2.4.

### 1.3 Enforcement layers

- **BFF**: route-level — a Staff-role token cannot even reach an
  admin-only route.
- **FastAPI**: row-level — every query for a Staff user adds
  `owner_id = :user_id` in addition to the standard `tenant_id` filter;
  every query for a Manager adds `owner_id IN (:team_member_ids)`. Admin
  queries add no additional filter beyond `tenant_id`.
- **Database**: RLS remains the tenant boundary (see `DATABASE_SCHEMA.md`);
  role-based row scoping is an application-layer concern on top of it, not a
  second RLS policy, since "team" membership changes over time and doesn't
  belong baked into a DB policy.

## 2. Workflow automation

### 2.1 Structure

Every rule has: **trigger** → **conditions** → **actions**, evaluated by the
workflow engine (background worker, see `ARCHITECTURE.md`).

- **Triggers**: time-based (elapsed time since an event), event-based (stage
  change, form submitted, payment received, document uploaded), or
  field-based (lead score crosses a threshold).
- **Conditions**: AND/OR combinations over stage, source, course, assigned
  counselor, tenant-configured custom fields.
- **Actions**: assign/reassign, send email/SMS/WhatsApp, create task, change
  stage, notify manager, **raise escalation** (Section 3).

### 2.2 Representative rules (EdTech-specific)

| Trigger | Condition | Action |
|---|---|---|
| New inquiry created | any source | Auto-assign counselor (round robin/territory), create "first contact" task due in 30 min |
| No activity logged | 24h since assignment, stage = Contacted or earlier | Escalate to manager (SLA breach — Section 3) |
| Demo scheduled, not marked attended | 2h after scheduled time | Notify counselor + reminder to reschedule |
| Fee due date | 3 days before | WhatsApp reminder to student |
| No activity logged | 7 days, any stage before Enrolled | Mark lead "cold", notify manager for reallocation |

### 2.3 Failure handling

A failed action (e.g., WhatsApp send fails) retries with backoff up to a
configured limit, then itself raises an escalation to the assigned
counselor's manager — automation failures should never fail silently.

### 2.4 Manager-proposed rules

Managers can draft a rule from their dashboard; it's saved in a
`pending` state, visible to Admin for one-click approval or rejection.
Rules never go live without Admin approval — see the permission matrix.

## 3. SLA framework

### 3.1 SLA policy

Each tenant configures SLA targets per stage and per task type, e.g.:

- First contact: within 30 minutes of inquiry
- Demo scheduling: within 24 hours of first contact
- Application follow-up: within 48 hours of application submission
- Any assigned task: by its due date

SLA clocks run against tenant-configured business hours (pause outside
working hours and on configured holidays) — a lead arriving at 11pm doesn't
start burning SLA time until the counselor's next working hour.

### 3.2 SLA states

Each SLA-tracked item moves through: `on_track` → `at_risk` (a
tenant-configured warning threshold before breach, e.g. 80% of target time
elapsed) → `breached`. State transitions are computed by a scheduled
background job, not on-demand at page load, so dashboards can query
precomputed state cheaply.

### 3.3 What happens on breach

A breach automatically raises an escalation (Section 3 ties directly into
Section 4) — SLA breach is one specific, always-on escalation trigger, not
a separate mechanism.

## 4. Escalation & roadblocks

### 4.1 Escalation sources

1. **Automatic — SLA breach** (Section 3.3)
2. **Automatic — workflow failure** (Section 2.3)
3. **Manual — counselor-flagged roadblock**: a counselor marks a lead as
   blocked (e.g., "waiting on document from student", "payment gateway
   issue", "needs pricing exception") with a reason and optional note.

### 4.2 Escalation lifecycle

`open` → `acknowledged` → `resolved` (or `reassigned` as an alternate exit).

- **Escalation chain**: Staff-raised or system-raised escalations go to the
  counselor's Manager by default; a tenant can configure a further
  Manager → Admin step for escalations unacknowledged past a second
  threshold (an "escalation SLA" on top of the original SLA).
- Every escalation records: source (SLA/workflow/manual), the lead/task it's
  tied to, who it's assigned to, timestamps for each state transition, and
  resolution notes.
- Manager acknowledgement should be fast to do from the dashboard (single
  action), since the point of escalation is surfacing it, not adding
  process weight.

### 4.3 Manager follow-ups

Distinct from escalations: a Manager can place a **follow-up flag** on any
lead independent of SLA/automation — e.g., "check on this personally next
week." This is a lightweight reminder mechanism (shows on the manager's
dashboard on the target date) and does not notify or block the counselor;
it's a tracking tool, not a directive.

The Follow-ups queue (`FollowUpFlagsPage.tsx`) is team-wide visibility, not
locked to each Manager's own list: its filter offers Mine / Everyone / any
specific person, and any Manager or Admin can select any of those (revised
2026-08-25 — this supersedes an earlier "manager's own personal list only"
framing). A per-contact indicator (the Contact Detail page's follow-up flag
card) is the exception — it stays scoped to the viewing Manager's own flag
on that contact specifically, since it's a personal "did I flag this"
signal rather than the team queue. Acting on a flag (resolve/snooze) is
still restricted to its own Manager or an Admin regardless of who can see
it — broader visibility doesn't grant edit rights to someone else's
reminder.

## 5. Dashboards by role

All three dashboards read from precomputed reporting aggregates (see
`ARCHITECTURE.md` Section 8 on Redis caching and `FEATURES_AND_PLAN.md`
Phase 4) rather than running heavy aggregate queries live on every page
load.

### 5.1 Staff dashboard

- **My queue**: assigned leads sorted by SLA urgency (breached first, then
  at-risk, then on-track), not just by recency
- **Tasks today**: due today and overdue, one-click complete
- **SLA timers**: visible per lead (e.g., "18 min left to first contact")
- **Quick activity logging**: log a call/email/WhatsApp inline without
  leaving the queue view
- **My stats**: leads worked, response time, conversion rate, demo
  attendance rate — personal only, not comparative to peers (avoid a
  leaderboard-pressure UI at the individual level; that's the manager view)
- **My pipeline value** *(proposed, Phase 6)*: sum of `deal.value` for own
  open deals, plus invoiced-but-unpaid amount — `PIPELINE_AND_REVENUE.md`
  Section 4
- **Notifications**: escalation acknowledgements, manager comments,
  reassignments

### 5.2 Manager dashboard

- **Team pipeline funnel**: all team members' leads by stage, filterable per
  counselor
- **SLA compliance view**: breach/at-risk counts per counselor, trending
  over time — this is where a leaderboard-style comparison is appropriate
- **Escalations queue**: open and acknowledged, sorted by age, with
  one-click acknowledge/resolve/reassign
- **Follow-up flags**: the manager's own personal tracking list (Section
  4.3)
- **Team forecast**: stage-weighted forecast rolled up for the team
- **Team pipeline value** *(proposed, Phase 6)*: $ by stage, weighted
  forecast in dollars, invoice rework rate for the team —
  `PIPELINE_AND_REVENUE.md` Section 4
- **Lead reallocation**: reassign leads across the team directly from the
  dashboard

### 5.3 Admin dashboard

- **Org-wide funnel & source ROI**: channel-level attribution, cost per
  enrollment (ties into the Meta/Google conversion feedback loop —
  `FEATURES_AND_PLAN.md` Phase 4)
- **Revenue overview** *(proposed, Phase 6)*: invoiced vs. paid vs.
  outstanding, invoice rework rate, average time in the invoice stage —
  `PIPELINE_AND_REVENUE.md` Section 4
- **SLA policy management**: configure targets, thresholds, business hours,
  holidays
- **Workflow rule management**: active rules, pending manager-proposed
  rules awaiting approval, execution/failure logs
- **User & role management**: invite users, assign roles, manage
  manager-to-team mappings
- **Integration health**: Meta/Google/WhatsApp connection status, last
  successful sync, error counts
- **Audit log**: who changed what configuration, when

## 6. New entities this introduces

To be added to `DATABASE_SCHEMA.md`'s entity table when implemented:

| Table | Purpose |
|---|---|
| `sla_policies` | Tenant-configured SLA targets per stage/task type |
| `sla_states` | Computed on_track/at_risk/breached state per tracked item |
| `escalations` | Escalation records with lifecycle and resolution notes |
| `follow_up_flags` | Manager's personal follow-up reminders on leads |
| `audit_log` | Configuration change history for Admin visibility |

All follow the standard tenant-scoped table pattern (tenant_id + RLS +
leading composite index) already defined in `DATABASE_SCHEMA.md` Section 2.
