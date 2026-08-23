"""Shared reassignment guard for contacts.owner_id / deals.owner_id /
tasks.assignee_id PATCHes — REQUIREMENTS.md §1.2's "Reassign leads" row
(Admin yes, Manager within team, Staff no). PHASE_3_PLAN.md §4.
"""

import uuid

from app.core.errors import FORBIDDEN, ApiError
from app.deps.scope import RowScope
from app.deps.tenant import TenantContext


def guard_reassignment(
    context: TenantContext, scope: RowScope, updates: dict, field: str
) -> None:
    """updates is the request body's model_dump(exclude_unset=True); field
    is "owner_id" or "assignee_id". A Staff request that even mentions the
    field is rejected outright — Staff never has reassignment capability,
    so there's nothing to inspect the value for. A Manager may only set it
    to someone within their own RowScope (self + direct reports)."""
    if field not in updates:
        return
    if context.user_role == "counselor":
        raise ApiError(403, FORBIDDEN, "Staff cannot reassign")
    if context.user_role == "manager":
        target: uuid.UUID | None = updates[field]
        if scope.owner_ids is not None and target not in scope.owner_ids:
            raise ApiError(403, FORBIDDEN, "Cannot assign outside your team")
