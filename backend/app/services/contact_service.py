import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import CONFLICT, ApiError
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.follow_up_flag import FollowUpFlag
from app.models.pipeline_stage import PipelineStage
from app.models.sla_policy import SlaPolicy
from app.models.sla_state import SlaState
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


async def get_contact_detail_snapshot(
    db: AsyncSession, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> dict:
    """The single-contact counterpart to list_contacts' latest-deal
    enrichment — used by the Contact Detail page's header (stage/SLA
    pills) and SLA card (elapsed-vs-target). One contact, so no DISTINCT
    ON needed: just the most-recently-updated deal, if any. sla_target_at/
    sla_target_minutes come from the same sla_states row as sla_state
    (joined on to sla_policies for target_minutes), so the frontend can
    compute an elapsed/target progress bar without a second request."""
    stmt = (
        select(
            Deal.id,
            PipelineStage.id,
            PipelineStage.name,
            SlaState.state,
            SlaState.target_at,
            SlaPolicy.target_minutes,
        )
        .select_from(Deal)
        .outerjoin(
            PipelineStage,
            (PipelineStage.id == Deal.stage_id) & (PipelineStage.tenant_id == tenant_id),
        )
        .outerjoin(SlaState, (SlaState.deal_id == Deal.id) & (SlaState.tenant_id == tenant_id))
        .outerjoin(
            SlaPolicy,
            (SlaPolicy.id == SlaState.sla_policy_id) & (SlaPolicy.tenant_id == tenant_id),
        )
        .where(Deal.tenant_id == tenant_id, Deal.contact_id == contact_id)
        .order_by(Deal.updated_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()

    has_open_follow_up = (
        await db.execute(
            select(
                exists().where(
                    FollowUpFlag.tenant_id == tenant_id,
                    FollowUpFlag.contact_id == contact_id,
                    FollowUpFlag.resolved_at.is_(None),
                )
            )
        )
    ).scalar_one()

    if row is None:
        return {
            "current_deal_id": None,
            "stage_id": None,
            "stage_name": None,
            "sla_state": None,
            "sla_target_at": None,
            "sla_target_minutes": None,
            "has_open_follow_up": has_open_follow_up,
        }
    deal_id, stage_id, stage_name, sla_state, target_at, target_minutes = row
    return {
        "current_deal_id": deal_id,
        "stage_id": stage_id,
        "stage_name": stage_name,
        "sla_state": sla_state,
        "sla_target_at": target_at,
        "sla_target_minutes": target_minutes,
        "has_open_follow_up": has_open_follow_up,
    }


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
    stage_id: uuid.UUID | None = None,
    has_follow_up_flag: bool | None = None,
    ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int]:
    """owner_id is the caller-supplied ?owner_id= filter; scoped_owner_ids
    is the RowScope enforcement (PHASE_3_PLAN.md §4) — the two compose:
    a Manager can still filter to one teammate via owner_id, but can
    never widen past scoped_owner_ids.

    ids batch-fetches a known, caller-bounded set of contacts (e.g. the
    Pipeline board resolving each deal's contact) in one round trip instead
    of one request per contact — pagination doesn't apply, since the
    caller already knows exactly which rows it wants.

    Each contact is enriched with its most-recently-updated deal's stage
    and SLA state — a contact can have zero or many deals, so "most
    recently updated" is this list view's own definition of "current"
    (design_handoff_crm_wireframes/README.md screen 3's Stage/SLA
    columns and Stage filter), plus whether it has an unresolved
    follow-up flag (the Follow-up filter). The latest-deal join uses
    Postgres DISTINCT ON, one row per contact, so it never multiplies
    the contact row count — the outerjoins after it stay 1:1."""
    latest_deal = (
        select(Deal.id.label("deal_id"), Deal.contact_id.label("contact_id"))
        .where(Deal.tenant_id == tenant_id)
        .order_by(Deal.contact_id, Deal.updated_at.desc())
        .distinct(Deal.contact_id)
        .subquery()
    )
    deal = aliased(Deal)

    joined = (
        select(Contact)
        .where(Contact.tenant_id == tenant_id)
        .outerjoin(latest_deal, latest_deal.c.contact_id == Contact.id)
        .outerjoin(deal, (deal.id == latest_deal.c.deal_id) & (deal.tenant_id == tenant_id))
        .outerjoin(
            PipelineStage,
            (PipelineStage.id == deal.stage_id) & (PipelineStage.tenant_id == tenant_id),
        )
        .outerjoin(SlaState, (SlaState.deal_id == deal.id) & (SlaState.tenant_id == tenant_id))
    )
    if scoped_owner_ids is not None:
        joined = joined.where(Contact.owner_id.in_(scoped_owner_ids))
    if ids is not None:
        joined = joined.where(Contact.id.in_(ids))
    if search:
        pattern = f"%{search.lower()}%"
        joined = joined.where(
            or_(
                func.lower(Contact.full_name).like(pattern),
                func.lower(Contact.email).like(pattern),
                Contact.phone.like(f"%{search}%"),
            )
        )
    if lead_source:
        joined = joined.where(Contact.lead_source == lead_source)
    if owner_id:
        joined = joined.where(Contact.owner_id == owner_id)
    if stage_id is not None:
        joined = joined.where(deal.stage_id == stage_id)
    if has_follow_up_flag:
        joined = joined.where(
            exists().where(
                FollowUpFlag.tenant_id == tenant_id,
                FollowUpFlag.contact_id == Contact.id,
                FollowUpFlag.resolved_at.is_(None),
            )
        )

    count_result = await db.execute(select(func.count()).select_from(joined.subquery()))
    total = count_result.scalar_one()

    stmt = joined.add_columns(
        PipelineStage.id.label("stage_id"),
        PipelineStage.name.label("stage_name"),
        SlaState.state.label("sla_state"),
    )
    stmt = _apply_sort(stmt, sort)
    if ids is None:
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    open_flag_contact_ids: set[uuid.UUID] = set()
    if rows:
        contact_ids = [contact.id for contact, *_ in rows]
        flagged = await db.execute(
            select(FollowUpFlag.contact_id).where(
                FollowUpFlag.tenant_id == tenant_id,
                FollowUpFlag.contact_id.in_(contact_ids),
                FollowUpFlag.resolved_at.is_(None),
            )
        )
        open_flag_contact_ids = {cid for (cid,) in flagged}

    return [
        {
            "contact": contact,
            "stage_id": stage_id_,
            "stage_name": stage_name,
            "sla_state": sla_state,
            "has_open_follow_up": contact.id in open_flag_contact_ids,
        }
        for contact, stage_id_, stage_name, sla_state in rows
    ], total


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
