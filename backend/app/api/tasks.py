import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import collection_envelope, data_envelope
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, ApiError
from app.core.reassignment import guard_reassignment
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task_service import create_task, get_task, list_tasks, update_task

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("")
async def post_task(
    request: Request,
    body: TaskCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    try:
        task = await create_task(context.db, context.tenant.id, body, context.user.id)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(
            400, VALIDATION_ERROR, "contact_id, deal_id, or assignee_id does not exist"
        ) from exc
    return data_envelope(
        TaskOut.model_validate(task).model_dump(mode="json"), request.state.request_id
    )


@router.get("")
async def get_tasks(
    request: Request,
    assignee_id: uuid.UUID | None = None,
    status: str | None = None,
    contact_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    tasks, total = await list_tasks(
        context.db,
        context.tenant.id,
        assignee_id,
        status,
        contact_id,
        page,
        page_size,
        scoped_owner_ids=scope.owner_ids,
    )
    items = [TaskOut.model_validate(t).model_dump(mode="json") for t in tasks]
    return collection_envelope(items, request.state.request_id, page, page_size, total)


@router.get("/{task_id}")
async def get_task_by_id(
    request: Request,
    task_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    task = await get_task(context.db, context.tenant.id, task_id, scope.owner_ids)
    if task is None:
        raise ApiError(404, NOT_FOUND, "Task not found")
    return data_envelope(
        TaskOut.model_validate(task).model_dump(mode="json"), request.state.request_id
    )


@router.patch("/{task_id}")
async def patch_task(
    request: Request,
    task_id: uuid.UUID,
    body: TaskUpdate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    task = await get_task(context.db, context.tenant.id, task_id, scope.owner_ids)
    if task is None:
        raise ApiError(404, NOT_FOUND, "Task not found")
    guard_reassignment(context, scope, body.model_dump(exclude_unset=True), "assignee_id")
    try:
        task = await update_task(context.db, task, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(400, VALIDATION_ERROR, "assignee_id does not exist") from exc
    return data_envelope(
        TaskOut.model_validate(task).model_dump(mode="json"), request.state.request_id
    )
