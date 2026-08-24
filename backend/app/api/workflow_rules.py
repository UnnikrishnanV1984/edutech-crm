import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, ApiError
from app.deps.roles import require_admin, require_manager_or_admin
from app.deps.tenant import TenantContext
from app.schemas.workflow_rule import WorkflowRuleCreate, WorkflowRuleDecision, WorkflowRuleOut
from app.services.workflow_rule_service import create_rule, decide_rule, get_rule, list_rules

router = APIRouter(prefix="/api/v1/workflow-rules", tags=["workflow-rules"])


def _out(rule) -> dict:
    return WorkflowRuleOut.model_validate(rule).model_dump(mode="json")


@router.get("")
async def get_workflow_rules(
    request: Request, context: TenantContext = Depends(require_manager_or_admin)
) -> dict:
    rules = await list_rules(context.db, context.tenant.id, context.user_role, context.user.id)
    return data_envelope([_out(r) for r in rules], request.state.request_id)


@router.post("")
async def post_workflow_rule(
    request: Request,
    body: WorkflowRuleCreate,
    context: TenantContext = Depends(require_manager_or_admin),
) -> dict:
    rule = await create_rule(
        context.db, context.tenant.id, context.user.id, context.user_role, body
    )
    return data_envelope(_out(rule), request.state.request_id)


@router.patch("/{rule_id}")
async def patch_workflow_rule(
    request: Request,
    rule_id: uuid.UUID,
    body: WorkflowRuleDecision,
    context: TenantContext = Depends(require_admin),
) -> dict:
    rule = await get_rule(context.db, context.tenant.id, rule_id)
    if rule is None:
        raise ApiError(404, NOT_FOUND, "Workflow rule not found")
    rule = await decide_rule(context.db, rule, context.user.id, body)
    return data_envelope(_out(rule), request.state.request_id)
