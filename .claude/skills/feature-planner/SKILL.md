---
name: feature-planner
description: Use before writing any code for a new feature or user story on OpenFunnel. Turns a feature request into a scoped implementation plan across frontend, BFF, backend, and database before any code is written. Trigger on requests like "let's build X", "plan out Y", or when picking up the next item from FEATURES_AND_PLAN.md.
---

# Feature planner

Produces a written plan before implementation starts. Do not write
application code in this skill — only the plan artifact described below.

## Process

1. **Locate the feature.** Check `FEATURES_AND_PLAN.md` for which phase it
   belongs to. If it's not listed, flag that explicitly and ask whether it
   should be added to the plan or treated as an ad-hoc request.
2. **Check prerequisites.** Per `CLAUDE.md`, do not plan Phase N+1 work until
   Phase N's exit criteria are met. If they aren't, say so before proceeding.
3. **Identify affected layers.** For each of frontend, BFF, backend,
   database, background jobs: state whether it's touched, and if so, what
   changes.
4. **Database changes.** If new tables/columns are needed, sketch them
   against the pattern in `DATABASE_SCHEMA.md` (tenant_id, RLS, composite
   index) — do not omit these even for a "simple" table.
5. **API contract.** New or changed endpoints, following `API_CONVENTIONS.md`
   (envelope shape, error codes, pagination). List request/response shapes.
6. **Multi-tenancy check.** Confirm the feature respects tenant isolation —
   no cross-tenant queries, no tenant ID trusted from anywhere but the
   validated Keycloak token (see `ARCHITECTURE.md` Section 4).
7. **Task breakdown.** A short ordered list of implementation steps, sized so
   each is a reviewable commit.
8. **Acceptance criteria.** Concrete, testable statements — not vague
   ("works correctly") but specific ("a counselor in tenant A cannot see a
   lead created in tenant B").

## Output

A markdown plan with the sections above. Hand this plan to the
`feature-builder` skill (or a human reviewer) before implementation begins.
Do not skip straight to code even if the feature looks small — the point of
this skill is catching multi-tenancy and schema mistakes before they're
written, not after.
