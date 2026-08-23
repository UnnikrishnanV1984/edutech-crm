from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import CONFLICT, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.course import CourseCreate, CourseOut
from app.services.course_service import create_course, list_courses

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


@router.post("")
async def post_course(
    request: Request,
    body: CourseCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    try:
        course = await create_course(context.db, context.tenant.id, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(409, CONFLICT, "A course with this code already exists") from exc
    return data_envelope(
        CourseOut.model_validate(course).model_dump(mode="json"), request.state.request_id
    )


@router.get("")
async def get_courses(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    courses = await list_courses(context.db, context.tenant.id)
    items = [CourseOut.model_validate(c).model_dump(mode="json") for c in courses]
    return data_envelope(items, request.state.request_id)
