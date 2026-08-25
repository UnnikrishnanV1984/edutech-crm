from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.roles import require_manager_or_admin
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.services import report_service
from app.services.report_service import DEFAULT_PERIOD

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/funnel")
async def get_funnel_report(
    request: Request,
    period: str = DEFAULT_PERIOD,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    data, cached_at = await report_service.get_funnel(
        context.db, context.tenant.id, scope.owner_ids, period
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/source-attribution")
async def get_source_attribution_report(
    request: Request,
    period: str = DEFAULT_PERIOD,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    data, cached_at = await report_service.get_source_attribution(
        context.db, context.tenant.id, scope.owner_ids, period
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/forecast")
async def get_forecast_report(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    data, cached_at = await report_service.get_forecast(
        context.db, context.tenant.id, scope.owner_ids
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/sla-compliance")
async def get_sla_compliance_report(
    request: Request,
    period: str = DEFAULT_PERIOD,
    context: TenantContext = Depends(require_manager_or_admin),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    data, cached_at = await report_service.get_sla_compliance(
        context.db, context.tenant.id, scope.owner_ids, period
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/invoices")
async def get_invoice_summary_report(
    request: Request,
    period: str = DEFAULT_PERIOD,
    context: TenantContext = Depends(require_manager_or_admin),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    data, cached_at = await report_service.get_invoice_summary(
        context.db, context.tenant.id, scope.owner_ids, period
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/my-queue")
async def get_my_queue_report(
    request: Request, context: TenantContext = Depends(get_tenant_context)
) -> dict:
    data, cached_at = await report_service.get_my_queue(
        context.db, context.tenant.id, context.user.id
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})


@router.get("/my-stats")
async def get_my_stats_report(
    request: Request,
    period: str = DEFAULT_PERIOD,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    data, cached_at = await report_service.get_my_stats(
        context.db, context.tenant.id, context.user.id, period
    )
    return data_envelope(data, request.state.request_id, {"cached_at": cached_at})
