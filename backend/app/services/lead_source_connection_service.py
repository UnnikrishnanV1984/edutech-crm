"""Every function below takes tenant_id explicitly and filters on it —
except resolve_connection, the one sanctioned exception, documented at
its definition. There is no RLS backstop for this table (see
alembic/versions/0009_lead_source_connections.py), so a missing filter
here is a real cross-tenant leak, not just noise — PHASE_2_PLAN.md §5/§8
acceptance criterion 6 requires a dedicated test proving every other
function includes it.
"""

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_token
from app.models.lead_source_connection import LeadSourceConnection
from app.schemas.lead_source_connection import LeadSourceConnectionCreate


async def create_connection(
    db: AsyncSession, tenant_id: uuid.UUID, data: LeadSourceConnectionCreate
) -> LeadSourceConnection:
    external_account_id = data.external_account_id
    access_token_encrypted = None
    refresh_token_encrypted = None

    if data.source == "web":
        # The "credential" is the public, non-secret embed key itself —
        # architect note in PHASE_2_PLAN.md §3.
        external_account_id = secrets.token_urlsafe(16)
    else:
        if data.access_token:
            access_token_encrypted = await encrypt_token(db, data.access_token)
        if data.refresh_token:
            refresh_token_encrypted = await encrypt_token(db, data.refresh_token)

    connection = LeadSourceConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source=data.source,
        external_account_id=external_account_id,
        access_token_encrypted=access_token_encrypted,
        refresh_token_encrypted=refresh_token_encrypted,
        token_expires_at=data.token_expires_at,
    )
    db.add(connection)
    await db.flush()
    await db.refresh(connection)
    return connection


async def list_connections(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[LeadSourceConnection]:
    result = await db.execute(
        select(LeadSourceConnection)
        .where(LeadSourceConnection.tenant_id == tenant_id)
        .order_by(LeadSourceConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def get_connection(
    db: AsyncSession, tenant_id: uuid.UUID, connection_id: uuid.UUID
) -> LeadSourceConnection | None:
    result = await db.execute(
        select(LeadSourceConnection).where(
            LeadSourceConnection.tenant_id == tenant_id,
            LeadSourceConnection.id == connection_id,
        )
    )
    return result.scalar_one_or_none()


async def update_status(
    db: AsyncSession, connection: LeadSourceConnection, status: str
) -> LeadSourceConnection:
    connection.status = status
    await db.flush()
    await db.refresh(connection)
    return connection


async def resolve_connection(
    db: AsyncSession, source: str, external_account_id: str
) -> LeadSourceConnection | None:
    """The one sanctioned query against this table with no tenant_id
    filter — this IS how a webhook discovers tenant_id in the first
    place, before app.tenant_id can be set (PHASE_2_PLAN.md §3). Only
    ever called from app/webhooks/* and the Google sync path, never from
    an admin-facing route (those always know tenant_id already, via
    get_connection above)."""
    result = await db.execute(
        select(LeadSourceConnection).where(
            LeadSourceConnection.source == source,
            LeadSourceConnection.external_account_id == external_account_id,
            LeadSourceConnection.status == "active",
        )
    )
    return result.scalar_one_or_none()
