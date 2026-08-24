from fastapi import Depends

from app.core.errors import FORBIDDEN, ApiError
from app.deps.tenant import TenantContext, get_tenant_context


async def require_admin(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    """First role-gated endpoint dependency in this codebase
    (PHASE_2_PLAN.md §4.1) — a one-line guard on the role X-User-Role
    already carries, not a preview of REQUIREMENTS.md §1.3's full
    row-level RBAC system (explicitly Phase 3 scope). Resist extending
    this beyond "is the caller an admin"."""
    if context.user_role != "admin":
        raise ApiError(403, FORBIDDEN, "Admin role required")
    return context


async def require_manager_or_admin(
    context: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    """REQUIREMENTS.md §1.2 — several capabilities (workflow rule
    proposals, follow-up flags) are Manager+Admin, with no Staff access
    at all, unlike escalations where Staff can at least raise one."""
    if context.user_role not in ("manager", "admin"):
        raise ApiError(403, FORBIDDEN, "Manager or admin role required")
    return context
