---
name: feature-builder
description: Use to implement a feature that already has a plan from feature-planner (or a clearly-scoped ask). Writes the actual frontend/BFF/backend/database code in small, reviewable commits following repo conventions. Trigger on "implement X", "build the Y feature", "let's code this up".
---

# Feature builder

Implements code. If no plan exists yet for anything beyond a trivial change,
stop and run the `feature-planner` skill first — do not improvise schema or
API shape decisions inline.

## Before writing code

- Re-read `CLAUDE.md` non-negotiable rules: every tenant-scoped table gets
  `tenant_id` + RLS + a leading composite index; every FastAPI endpoint
  validates `X-Tenant-Id`; tenant identity is only ever trusted from the
  BFF's forwarded, Keycloak-validated headers.
- Re-read `API_CONVENTIONS.md` for the response envelope, error format, and
  pagination pattern — do not invent a new shape for this endpoint.
- Re-read `DATABASE_SCHEMA.md` for the standard table pattern before writing
  a migration.

## Process

1. **Database layer first** (if applicable): write the Alembic migration
   using the standard tenant-scoped table pattern. Include RLS policy and
   composite index in the same migration, not a follow-up.
2. **Backend (FastAPI)**: implement the endpoint(s) — Pydantic
   schemas, service logic, route registration. Validate tenant context at
   the top of every handler.
3. **BFF (Express)**: add/update the route that proxies to FastAPI, forwards
   `X-Tenant-Id` / `X-User-Id` / `X-Request-Id`, and shapes the response for
   the frontend if needed.
4. **Frontend (React)**: build the UI against the BFF contract. Check
   whether `ui-designer` or `ux-designer` input is needed for anything
   user-facing and not already specified.
5. **Tests**: unit tests for backend service logic, an integration test that
   proves tenant isolation for any new table/endpoint (per
   `feature-planner`'s acceptance criteria), and frontend component tests
   where relevant.
6. **Docs**: if the change adds or changes an API endpoint, update
   `API_CONVENTIONS.md` or an endpoint reference if one exists. If it adds a
   table, confirm `DATABASE_SCHEMA.md`'s entity table is still accurate.

## Commit discipline

Small, scoped commits — one per layer or one per logical slice, not one
giant commit for the whole feature. Run lint/tests for each touched service
before committing (see `CLAUDE.md` commands section).
