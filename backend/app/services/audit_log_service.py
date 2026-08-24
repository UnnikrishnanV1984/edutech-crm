"""v1 is write-only (GAP_FIXES_PLAN.md item 6) — no read API/UI yet, just
`record()`, called from the three call sites that actually change
something an admin would want a trail of: a user's manager reassignment
(app/services/user_service.py), a deal's stage change (app/api/deals.py),
and an escalation's acknowledge/resolve/reassign transitions
(app/services/escalation_service.py). Always called inside the same
transaction as the change it's recording, so a row's tenant_id can never
diverge from the change it describes."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(entry)
    await db.flush()
    return entry
