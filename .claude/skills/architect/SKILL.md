---
name: architect
description: Use for structural or cross-cutting decisions - new integrations, infra/deployment changes, schema changes affecting existing tables, or anything touching multi-tenancy. Trigger on "how should we structure X", "we need to add a new integration", "this affects the schema/deployment", or before any change flagged in CLAUDE.md's "what to ask about before proceeding".
---

# Architect

Reasons about structure before anyone writes code. Produces a short design
note, not application code.

## When this skill is required, not optional

Per `CLAUDE.md`, these always go through this skill first:
- Any change that removes or weakens an RLS policy
- Any new external integration (new API keys/secrets)
- Any schema change to a table already in production use
- Anything affecting the local-to-AWS module mapping in `ARCHITECTURE.md`
  Section 6 (new service, new Dockerfile, new Helm chart)

## Process

1. **State the problem** in one or two sentences — what's being added or
   changed, and why.
2. **Check existing docs first.** Read `ARCHITECTURE.md`,
   `DATABASE_SCHEMA.md`, and `FEATURES_AND_PLAN.md` for whether this is
   already decided, partially decided, or genuinely new ground.
3. **Multi-tenancy impact.** Does this change need to behave differently for
   pooled SaaS tenants vs. single-tenant/VPC deployments? State explicitly —
   most changes should work identically across both per the "same images,
   different config" principle.
4. **Propose the change**, including:
   - Which layer(s) it touches (web / bff / backend / db / redis / keycloak)
   - Any new table or index, following the standard pattern in
     `DATABASE_SCHEMA.md`
   - Any new environment variable or secret, and whether it's needed in
     Docker Compose, Helm values, or both
5. **Note trade-offs** — at least one alternative considered and why it was
   rejected, especially for anything with real cost (a new service to run,
   a new external dependency).
6. **Update the docs.** If the decision is accepted, update the relevant
   file (`ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, etc.) in the same change —
   don't let the docs drift from what was actually built.

## Output

A short design note (a few paragraphs, not a full RFC) that a human can
approve quickly. Hand off to `feature-planner`/`feature-builder` once
approved.
