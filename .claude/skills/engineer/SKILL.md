---
name: engineer
description: General-purpose day-to-day coding on OpenFunnel - bug fixes, refactors, small non-structural changes, dependency bumps, test fixes. Use when the work is too small to need feature-planner or architect. Trigger on "fix this bug", "refactor X", "why is this test failing".
---

# Engineer

Default skill for routine work that isn't a new feature and isn't a
structural decision. If a "small" fix turns out to touch the schema, RLS, or
tenant isolation, stop and switch to `architect` instead of pushing through.

## Ground rules (always apply)

- Never touch tenant isolation logic without re-reading `CLAUDE.md`'s
  non-negotiable rules first.
- Match the existing conventions in the file you're editing rather than
  introducing a new pattern for one fix.
- Run the relevant service's lint/test commands (see `CLAUDE.md`) before
  considering a fix done.
- If a bug turns out to be caused by a missing tenant filter, a missing RLS
  policy, or a missing composite index, treat it as a priority fix
  regardless of how it was originally reported — these are the failure modes
  called out throughout `ARCHITECTURE.md` and `DATABASE_SCHEMA.md`.

## Process

1. Reproduce the bug or clearly scope the refactor before changing code.
2. Make the smallest change that correctly fixes the issue — resist
   drive-by refactors in the same commit.
3. Add or update a test that would have caught the bug.
4. Run lint + tests for every service touched.
5. Note in the commit message which layer(s) changed and why.

## When to escalate

- Bug traces back to a schema or RLS issue → `architect`.
- Fix requires a new endpoint or table → `feature-planner`.
- Fix is purely visual/UX → hand off to `ui-designer` or `ux-designer`.
