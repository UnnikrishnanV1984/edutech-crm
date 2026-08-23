import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


async def create_task(
    db: AsyncSession, tenant_id: uuid.UUID, data: TaskCreate, default_assignee_id: uuid.UUID
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contact_id=data.contact_id,
        deal_id=data.deal_id,
        assignee_id=data.assignee_id or default_assignee_id,
        title=data.title,
        description=data.description,
        due_at=data.due_at,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


async def get_task(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(select(Task).where(Task.tenant_id == tenant_id, Task.id == task_id))
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    assignee_id: uuid.UUID | None,
    status: str | None,
    contact_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[Task], int]:
    stmt = select(Task).where(Task.tenant_id == tenant_id)
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if contact_id:
        stmt = stmt.where(Task.contact_id == contact_id)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = stmt.order_by(Task.due_at.asc().nulls_last()).offset((page - 1) * page_size).limit(
        page_size
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_task(db: AsyncSession, task: Task, data: TaskUpdate) -> Task:
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        if updates["status"] == "done" and task.status != "done":
            updates["completed_at"] = datetime.now(UTC)
        elif updates["status"] == "open" and task.status != "open":
            updates["completed_at"] = None

    for key, value in updates.items():
        setattr(task, key, value)
    await db.flush()
    await db.refresh(task)
    return task
