import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import CONFLICT, NOT_FOUND, VALIDATION_ERROR, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext
from app.schemas.lead_source_connection import (
    LeadSourceConnectionCreate,
    LeadSourceConnectionOut,
    LeadSourceConnectionUpdate,
)
from app.services import lead_source_connection_service as connections
from app.services.google_sync_service import sync_connection

router = APIRouter(prefix="/api/v1/lead-source-connections", tags=["lead-source-connections"])


def _out(connection) -> dict:
    return LeadSourceConnectionOut.model_validate(connection).model_dump(mode="json")


@router.get("")
async def get_connections(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    rows = await connections.list_connections(context.db, context.tenant.id)
    return data_envelope([_out(r) for r in rows], request.state.request_id)


@router.post("")
async def post_connection(
    request: Request,
    body: LeadSourceConnectionCreate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    try:
        connection = await connections.create_connection(context.db, context.tenant.id, body)
    except IntegrityError as exc:
        await context.db.rollback()
        # Global uniqueness (alembic 0009) — message deliberately doesn't
        # say which tenant already holds it (PHASE_2_PLAN.md §4.1/§8
        # acceptance criterion 8).
        raise ApiError(409, CONFLICT, "This account is already connected") from exc
    return data_envelope(_out(connection), request.state.request_id)


@router.patch("/{connection_id}")
async def patch_connection(
    request: Request,
    connection_id: uuid.UUID,
    body: LeadSourceConnectionUpdate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    connection = await connections.get_connection(context.db, context.tenant.id, connection_id)
    if connection is None:
        raise ApiError(404, NOT_FOUND, "Connection not found")
    connection = await connections.update_connection(context.db, connection, body)
    return data_envelope(_out(connection), request.state.request_id)


@router.post("/{connection_id}/sync")
async def post_connection_sync(
    request: Request,
    connection_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
) -> dict:
    connection = await connections.get_connection(context.db, context.tenant.id, connection_id)
    if connection is None:
        raise ApiError(404, NOT_FOUND, "Connection not found")
    if connection.source != "google":
        raise ApiError(400, VALIDATION_ERROR, "Sync is only supported for google connections")
    ingested = await sync_connection(context.db, context.tenant.id, connection)
    return data_envelope({"ingested": ingested}, request.state.request_id)
