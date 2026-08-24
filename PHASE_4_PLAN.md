# Phase 4 plan — reporting, forecasting, and role dashboards

Per `FEATURES_AND_PLAN.md`, Phase 4 covers reporting, forecasting, and the
conversion feedback loop. Phase 3's exit criteria are met (RBAC, SLA
engine, and workflow rule engine shipped and verified — see
`PHASE_3_PLAN.md`), so per `CLAUDE.md`'s phase-sequencing rule, Phase 4 can
now be planned.

This plan covers everything in Phase 4 that does **not** depend on a new
external provider, and is scoped down from the full feature list in
several places where building the "real" version would require product
decisions or schema this repo doesn't have yet — each cut is called out
explicitly below with why, not silently narrowed.

**Explicitly out of scope, architect-blocked**: Meta Conversions API and
Google offline conversions (sending enrollment/fee-paid events back to ad
platforms). New external provider integrations — per `CLAUDE.md`'s "what
to ask about" list and `DEVELOPMENT_PLAN.md` §9 ("Outbound conversion
APIs → architect first"), same rule that deferred Phase 3's WhatsApp
outbound/email. Not planned here; send to `architect` first when ready.

**Explicitly out of scope, missing prerequisite data — not a decision to
silently work around:**

- **Source ROI in dollar terms / cost-per-enrollment.** Nothing in this
  schema tracks ad spend or campaign cost — `FEATURES_AND_PLAN.md`/
  `REQUIREMENTS.md` both assume it exists. This plan ships **lead counts
  by source** instead of cost-per-enrollment; real ROI needs a product
  decision on how cost data enters the system (manual admin entry per
  campaign? a platform spend-API pull — itself a new external
  integration) before it can be built.
- **Forecasting is a weighted headcount, not a revenue figure.** `deals`
  has no value/price column (`payments` — Fee/EMI — is a separate,
  still-unbuilt `FEATURES_AND_PLAN.md` line item, not a per-deal
  expected-value field). "Stage-weighted forecasting" here means
  `Σ deals-in-stage × stage.win_probability_pct`, a probable-enrollment
  count. A real $ forecast needs a `deals.expected_value` or
  `courses.price` field — flagged, not invented here.
- **Staff "response time" and "demo attendance rate" stats
  (`REQUIREMENTS.md` §5.1).** Neither is trackable today: there's no
  first-contact timestamp, and "demo attended" has no fixed-meaning flag
  the way `is_won`/`is_lost` do — matching by stage *name* would be
  fragile since stage names are tenant-editable. Both need a schema
  decision (a `deals.first_contacted_at` column; a `pipeline_stages`
  milestone flag analogous to `is_won`) before they can be built
  correctly. Staff "My stats" in this plan ships only what's cleanly
  computable: leads worked, conversion rate.
- **SLA compliance "trending over time" (`REQUIREMENTS.md` §5.2).**
  `sla_states` only holds current state, not history. Trending needs a
  new daily-snapshot table + Beat task — real additional scope, deferred;
  this plan ships current breach/at-risk/on-track counts per counselor,
  no trend line.
- **Admin "Integration health" error counts.** `lead_source_connections`
  has no failure-tracking column. This plan's Integration health panel
  shows connection status + `last_synced_at` (both already exist) and
  flags error-count tracking as a follow-up.
- **Audit log.** Still unclaimed by any phase — `DEVELOPMENT_PLAN.md` §8
  flagged this gap after Phase 0; it remains unresolved after Phase 3 too.
  Not built here either.

## 1. Prerequisites check

Phase 3 exit criteria met (verified this session — a configured workflow
rule fires and notifies, an SLA breach auto-escalates, both proven live
against the running stack). No blockers to starting Phase 4's unblocked
work.

## 2. Affected layers

| Layer | Touched? | What changes |
|---|---|---|
| Frontend | Yes, substantial | Three new role-specific dashboard pages (Staff/Manager/Admin per `REQUIREMENTS.md` §5); `ui-designer`/`ux-designer` input needed — this is the first phase since Phase 1 with a genuinely new surface type, same reasoning `DEVELOPMENT_PLAN.md` §9 gave for why Phase 1 needed them |
| BFF | No changes | Same generic `/api/v1` proxy as every resource so far |
| Backend | Yes, substantial | `pipeline_stages.win_probability_pct`, new reporting service + endpoints, Redis cache-aside layer, a new SLA-state read path (missing from Phase 3 — see §5) |
| Database | Yes | One new column, no new tables |
| Background jobs | No changes | Reports are cache-aside (query, cache 60s, serve), not a new Celery precompute job — see §6 for why |

## 3. Database changes

### 3.1 `pipeline_stages.win_probability_pct`

```sql
ALTER TABLE pipeline_stages ADD COLUMN win_probability_pct INT NOT NULL DEFAULT 0
    CHECK (win_probability_pct BETWEEN 0 AND 100);
```

Admin-configurable per stage (extends the existing
`PATCH /api/v1/pipeline-stages/{id}`, no new endpoint). Default `0` means
an untouched tenant's forecast is `0` until an admin actually sets
probabilities — deliberately not a guessed default like "20% per stage
in order," which would silently fabricate a number no admin chose.

No other schema changes — every other reporting number in this plan is
computed from existing tables (`contacts`, `deals`, `tasks`, `sla_states`,
`escalations`) at query time.

## 4. API contract

New file `app/api/reports.py`, service `app/services/report_service.py`.
Every endpoint is `GET`, tenant-scoped via `get_tenant_context`, and
**role-scoped by reusing `app/deps/scope.py`'s existing `RowScope`** — the
same Admin/Manager/Staff visibility rules Phase 3 already established for
contacts/deals/tasks apply identically here, not a second scoping system.

```
GET /api/v1/reports/funnel                lead/deal counts per pipeline
                                           stage, RowScope-filtered by
                                           owner_id
GET /api/v1/reports/source-attribution    lead counts per lead_source,
                                           RowScope-filtered
GET /api/v1/reports/forecast              Σ (deals-in-stage ×
                                           stage.win_probability_pct),
                                           RowScope-filtered, plus a
                                           by-stage breakdown
GET /api/v1/reports/sla-compliance        per-counselor breach/at_risk/
                                           on_track counts — gated by
                                           app/deps/roles.py's existing
                                           require_manager_or_admin
                                           (Phase 3, already used by
                                           follow-up flags/workflow
                                           rules), 403 for Staff
                                           (REQUIREMENTS.md §5.2, not a
                                           Staff-visible view)
GET /api/v1/reports/my-queue              Staff's own assigned deals,
                                           joined with current sla_states,
                                           sorted breached-first then
                                           at-risk then on-track —
                                           REQUIREMENTS.md §5.1's first
                                           bullet, and the missing
                                           sla_states *read* path Phase 3
                                           didn't build (it only wrote
                                           sla_states, via the Celery
                                           task — nothing ever read it
                                           back through the API)
GET /api/v1/reports/my-stats              Staff's own leads-worked count
                                           + conversion rate (is_won
                                           share) — response-time/demo-
                                           attendance omitted, see this
                                           plan's intro
```

Every response follows `API_CONVENTIONS.md` §3's envelope
(`{"data": ..., "meta": {"request_id", ...}}`) — these are read-only
aggregate shapes, not paginated collections, so `meta` carries only
`request_id` plus a `cached_at` timestamp (when the value was computed,
not necessarily "now" — see §6) so the frontend can show "as of HH:MM"
rather than implying live data.

## 5. The missing `sla_states` read path

Phase 3 built `sla_states` as a Celery-computed, Celery-written table with
admin CRUD on the *policies* that drive it (`sla_policies`) — but no route
ever reads a deal's own computed SLA state back. `REQUIREMENTS.md` §5.1's
"SLA timers: visible per lead" and "My queue... sorted by SLA urgency"
both need exactly that. `GET /api/v1/reports/my-queue` (§4) is where this
plan adds it, rather than a separate `GET /api/v1/deals/{id}/sla-state` —
the queue view is the only place `REQUIREMENTS.md` actually asks for this,
and a single joined query is simpler than a per-deal sub-resource plus a
frontend N+1 fetch loop.

## 6. Caching — cache-aside, not a new precompute job

`REQUIREMENTS.md` §5's "read from precomputed reporting aggregates...
rather than running heavy aggregate queries live on every page load" is
satisfied here with a **60-second TTL Redis cache in front of a normal
indexed `GROUP BY` query** (`report:{tenant_id}:{report_type}:{scope_hash}`,
reusing `app/core/redis.py`'s existing client), not a new Celery
precomputation task writing a summary table. At this repo's actual data
volume (hundreds to low thousands of rows per tenant in dev; nothing here
is a Phase-5-scale problem yet), a live `GROUP BY` over an already-indexed
column runs in single-digit milliseconds — the cache exists to avoid
*repeating* that work on every dashboard poll, not because the query
itself is heavy. A write-invalidation strategy (bust the cache the moment
a deal's stage changes) was considered and rejected for this pass: it
would touch every write path that affects any report (stage changes,
task creation, SLA computation, escalation creation) for a benefit — data
at most 60 seconds stale — that doesn't justify the coupling. Precomputed
summary tables belong in Phase 5 if real scale ever demands them
(`FEATURES_AND_PLAN.md` Phase 5 is explicitly the hardening/scale phase).

`scope_hash` is a hash of the caller's `RowScope.owner_ids` (or a fixed
sentinel for Admin's `None`) — this is the one place a cache key
correctness bug would leak cross-tenant *or cross-role* data, so it's
called out as its own required test in §9.

## 7. Multi-tenancy check

- Every reporting query filters `tenant_id` (via `get_tenant_context`,
  same as every other endpoint) **and** `RowScope.owner_ids` (via
  `get_row_scope`, same dependency Phase 3's contacts/deals/tasks already
  use) — no new scoping mechanism.
- Redis cache keys are namespaced `{tenant_id}:{report_type}:{scope_hash}`
  — a missing or wrong `tenant_id`/`scope_hash` component would serve one
  tenant's (or one role's) cached numbers to another, which is why §9
  requires a dedicated test proving the key actually varies with both.
- `sla-compliance` and `my-queue`/`my-stats` are asymmetric on purpose
  (`sla-compliance` explicitly excludes Staff, the other two are Staff's
  own view only) — mirrors the permission matrix's own asymmetry
  (`REQUIREMENTS.md` §1.2: org/team reporting is Manager+Admin only).

## 8. Task breakdown

1. Migration: `pipeline_stages.win_probability_pct`. Extend
   `PipelineStageUpdate`/`update_stage` to accept it (existing PATCH
   route, no new route).
2. Backend: `app/core/report_cache.py` — `get_or_compute(key, ttl,
   compute_fn)` helper wrapping the Redis get/set-with-TTL pattern, used
   by every report function below rather than each duplicating it.
3. Backend: `report_service.get_funnel` + `GET /api/v1/reports/funnel`.
   Tests: RowScope filtering per role; cache key varies by scope (§7).
4. Backend: `report_service.get_source_attribution` +
   `GET /api/v1/reports/source-attribution`. Tests per role.
5. Backend: `report_service.get_forecast` +
   `GET /api/v1/reports/forecast`. Tests: a stage with
   `win_probability_pct = 0` contributes `0`, not silently excluded from
   the by-stage breakdown; matches manual arithmetic on a small fixture.
6. Backend: `report_service.get_sla_compliance` +
   `GET /api/v1/reports/sla-compliance`. Tests: Staff gets `403`; Manager
   sees only their team's counselors.
7. Backend: `report_service.get_my_queue` (deals + `sla_states` join,
   breached-first sort) + `GET /api/v1/reports/my-queue`. Tests: sort
   order across all three states; a deal with no computed `sla_states`
   row yet (no policy has ticked it) still appears, sorted last.
8. Backend: `report_service.get_my_stats` +
   `GET /api/v1/reports/my-stats`. Tests: conversion rate math on a small
   fixture (N won / N total).
9. Cross-cutting test: two tenants, same report type, prove cache keys
   never collide across tenant *or* role (§6/§7's flagged risk).
10. `ux-designer`: flow for how a counselor moves from "My queue" into
    acting on an urgent item (already-built deal/task actions, this is
    about entry point and urgency-first ordering, not new mechanics).
11. `ui-designer`: visual spec for the three dashboards — funnel
    (bar/stage breakdown), SLA compliance (per-counselor table/chart),
    forecast (by-stage breakdown) — reusing `DESIGN_SYSTEM_REFRESH.md`'s
    existing tokens, no new component system.
12. Frontend: `api/reports.ts` client.
13. Frontend: Staff dashboard (`/dashboard` or role-conditional home) —
    My queue, Tasks today (existing tasks endpoint, `due_at <= today`
    filter client-side or a new query param — reuse, don't duplicate),
    My stats. Quick activity logging deferred — no activity-creation UI
    exists anywhere yet, including outside dashboards, so this isn't a
    dashboard-specific gap to solve here.
14. Frontend: Manager dashboard — Team funnel, SLA compliance, plus
    **reusing already-built screens** for Escalations queue and
    Follow-up flags (Phase 3) rather than re-implementing them inline;
    Lead reallocation reuses the existing `PATCH /api/v1/contacts/{id}`
    (`owner_id`) — already Manager-within-team-guarded (Phase 3) — via a
    small reassign control on the funnel/queue view, not a new endpoint.
15. Frontend: Admin dashboard — Org funnel + source attribution,
    Integration health (reuses Phase 2's `GET /api/v1/lead-source-connections`,
    no new endpoint), plus links out to the already-built SLA policy and
    workflow rule screens (Phase 3) rather than duplicating them.
16. Docs: `API_CONVENTIONS.md` gets the `cached_at` meta field noted as a
    documented exception to the standard envelope (§4); `DATABASE_SCHEMA.md`
    confirms `pipeline_stages`' entity-table row still accurate.

## 9. Acceptance criteria

1. A Staff user's `GET /api/v1/reports/funnel` counts only their own
   deals; a Manager's includes their team's; an Admin's is org-wide —
   same three-way split already proven for contacts/deals/tasks in
   Phase 3, now proven for aggregates too.
2. `GET /api/v1/reports/sla-compliance` is `403` for a Staff token.
3. `GET /api/v1/reports/my-queue` sorts breached items before at-risk
   before on-track, and a deal with no `sla_states` row yet still
   appears (sorted last), rather than being silently dropped.
4. A stage with `win_probability_pct = 0` still appears in
   `GET /api/v1/reports/forecast`'s by-stage breakdown with a `0`
   contribution, not omitted.
5. Two different tenants requesting the same report type never observe
   each other's cached numbers; two different roles within the same
   tenant requesting the same report type never observe each other's
   cached numbers either (the asymmetric-scope risk flagged in §6/§7).
6. Every dashboard's numbers are traceable to a real query against
   existing tables — no metric in this phase is a placeholder or a
   fabricated default (e.g., no invented per-stage win probability; a
   tenant that hasn't configured one gets `0`, not a guess).
7. `marketing team can see cost-per-enrollment by channel` from
   `FEATURES_AND_PLAN.md`'s Phase 4 exit criteria is **not** met by this
   plan (see the ROI cut in this plan's intro) — flagged here explicitly
   rather than claimed done. The other two clauses of that exit
   criterion (ad platforms receiving conversion signals; each role
   seeing its `REQUIREMENTS.md` §5 dashboard) are partially met: the
   dashboards ship, conversion signals remain architect-blocked.
