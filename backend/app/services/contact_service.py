import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CONFLICT, ApiError
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate


async def _find_dedupe_conflict(
    db: AsyncSession, tenant_id: uuid.UUID, email: str | None, phone: str | None
) -> Contact | None:
    if not email and not phone:
        return None
    conditions = []
    if email:
        conditions.append(func.lower(Contact.email) == email.lower())
    if phone:
        conditions.append(Contact.phone == phone)
    result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, or_(*conditions)).limit(1)
    )
    return result.scalar_one_or_none()


def _conflict_error(existing: Contact) -> ApiError:
    field = "email"
    return ApiError(
        409,
        CONFLICT,
        "A contact with this email or phone already exists",
        details=[
            {
                "field": field,
                "issue": "duplicate",
                "existing_contact_id": str(existing.id),
            }
        ],
    )


async def create_contact(
    db: AsyncSession, tenant_id: uuid.UUID, data: ContactCreate, default_owner_id: uuid.UUID
) -> Contact:
    email = str(data.email) if data.email else None

    existing = await _find_dedupe_conflict(db, tenant_id, email, data.phone)
    if existing is not None:
        raise _conflict_error(existing)

    contact = Contact(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        full_name=data.full_name,
        email=email,
        phone=data.phone,
        lead_source=data.lead_source,
        owner_id=data.owner_id or default_owner_id,
        territory=data.territory,
    )
    db.add(contact)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Race-condition fallback — the proactive check above already
        # covers the common case, but a concurrent insert can still land
        # between the check and this flush. The DB's partial unique
        # indexes are the real guarantee; this just turns that guarantee
        # into the same 409 shape instead of a raw 500.
        await db.rollback()
        existing = await _find_dedupe_conflict(db, tenant_id, email, data.phone)
        if existing is not None:
            raise _conflict_error(existing) from exc
        raise
    await db.refresh(contact)
    return contact


async def get_contact(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    owner_ids: list[uuid.UUID] | None = None,
) -> Contact | None:
    """owner_ids is the RowScope filter (PHASE_3_PLAN.md §4) — None means
    unrestricted, used by call sites that check contact existence for a
    related-resource action (creating a deal/document under it) rather
    than the contact itself being viewed/edited, where row-scoping
    doesn't apply per REQUIREMENTS.md §1.2's "Create/edit contacts" row."""
    stmt = select(Contact).where(Contact.tenant_id == tenant_id, Contact.id == contact_id)
    if owner_ids is not None:
        stmt = stmt.where(Contact.owner_id.in_(owner_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


SORTABLE_FIELDS = {
    "updated_at": Contact.updated_at,
    "created_at": Contact.created_at,
    "full_name": Contact.full_name,
}


def _apply_sort(stmt, sort: str | None):
    field_name = (sort or "-updated_at").lstrip("-")
    column = SORTABLE_FIELDS.get(field_name, Contact.updated_at)
    descending = (sort or "-updated_at").startswith("-")
    return stmt.order_by(column.desc() if descending else column.asc())


async def list_contacts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    search: str | None,
    lead_source: str | None,
    owner_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort: str | None = None,
    scoped_owner_ids: list[uuid.UUID] | None = None,
) -> tuple[list[Contact], int]:
    """owner_id is the caller-supplied ?owner_id= filter; scoped_owner_ids
    is the RowScope enforcement (PHASE_3_PLAN.md §4) — the two compose:
    a Manager can still filter to one teammate via owner_id, but can
    never widen past scoped_owner_ids."""
    stmt = select(Contact).where(Contact.tenant_id == tenant_id)
    if scoped_owner_ids is not None:
        stmt = stmt.where(Contact.owner_id.in_(scoped_owner_ids))
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Contact.full_name).like(pattern),
                func.lower(Contact.email).like(pattern),
                Contact.phone.like(f"%{search}%"),
            )
        )
    if lead_source:
        stmt = stmt.where(Contact.lead_source == lead_source)
    if owner_id:
        stmt = stmt.where(Contact.owner_id == owner_id)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = _apply_sort(stmt, sort).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_contact(db: AsyncSession, contact: Contact, data: ContactUpdate) -> Contact:
    updates = data.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"])

    new_email = updates.get("email", contact.email)
    new_phone = updates.get("phone", contact.phone)
    if ("email" in updates and new_email != contact.email) or (
        "phone" in updates and new_phone != contact.phone
    ):
        existing = await _find_dedupe_conflict(db, contact.tenant_id, new_email, new_phone)
        if existing is not None and existing.id != contact.id:
            raise _conflict_error(existing)

    for key, value in updates.items():
        setattr(contact, key, value)
    await db.flush()
    await db.refresh(contact)
    return contact
