import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.schemas.course import CourseCreate


async def create_course(db: AsyncSession, tenant_id: uuid.UUID, data: CourseCreate) -> Course:
    course = Course(id=uuid.uuid4(), tenant_id=tenant_id, name=data.name, code=data.code)
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course


async def get_course_by_code(db: AsyncSession, tenant_id: uuid.UUID, code: str) -> Course | None:
    result = await db.execute(
        select(Course).where(Course.tenant_id == tenant_id, Course.code == code)
    )
    return result.scalar_one_or_none()


async def list_courses(db: AsyncSession, tenant_id: uuid.UUID) -> list[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.tenant_id == tenant_id, Course.status == "active")
        .order_by(Course.name)
    )
    return list(result.scalars().all())
