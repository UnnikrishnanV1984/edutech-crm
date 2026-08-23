"""Row-level scoping on top of RLS — REQUIREMENTS.md §1.3: RLS remains the
tenant boundary; RowScope is the role boundary within a tenant. Deliberately
an application-layer filter, not a second RLS policy, since team membership
changes over time and doesn't belong baked into a DB policy (same doc,
same section). See PHASE_3_PLAN.md §4/§8.
"""

from dataclasses import dataclass

from fastapi import Depends

from app.deps.tenant import TenantContext, get_tenant_context
from app.services.user_service import list_team_member_ids


@dataclass
class RowScope:
    owner_ids: list | None
    """None = unrestricted (Admin). Otherwise the caller's own id plus,
    for a Manager, their direct reports' ids — apply as
    Model.owner_id.in_(owner_ids) (or assignee_id for tasks)."""


async def get_row_scope(context: TenantContext = Depends(get_tenant_context)) -> RowScope:
    if context.user_role == "admin":
        return RowScope(owner_ids=None)
    if context.user_role == "manager":
        team_ids = await list_team_member_ids(context.db, context.tenant.id, context.user.id)
        return RowScope(owner_ids=[context.user.id, *team_ids])
    return RowScope(owner_ids=[context.user.id])  # counselor — REQUIREMENTS.md's "Staff"
