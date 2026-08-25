"""app/connectors/ingestion_service.py — proves seeded leads go through
the same service-layer functions a real HTTP request uses (dedupe,
default-stage lookup, RLS), that re-running is a no-op via the Redis
idempotency key, and that a tenant with no counselors is skipped rather
than crashing (SEED_CONNECTORS_PLAN.md acceptance criteria)."""

import os
import uuid

import psycopg
import pytest
import redis.asyncio as redis_asyncio

from app.connectors.ingestion_service import ingest_all

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
APP_URL = os.environ.get("DATABASE_APP_URL", "").replace("+psycopg", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

TOTAL_SAMPLE_LEADS = 12  # 3 per source x 4 sources (meta/google/web/whatsapp)


def _pg_reachable(url: str) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


async def _redis_reachable() -> bool:
    if not REDIS_URL:
        return False
    try:
        client = redis_asyncio.from_url(REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


def _reachable() -> bool:
    import asyncio

    return (
        MIGRATE_URL
        and APP_URL
        and _pg_reachable(MIGRATE_URL)
        and asyncio.run(_redis_reachable())
    )


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason="DATABASE_URL/DATABASE_APP_URL/REDIS_URL not set or Postgres/Redis unreachable",
)


@pytest.fixture
def tenant_with_counselors():
    tid = uuid.uuid4()
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tid, f"t-{tid}", "Ingestion Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) VALUES "
            "(%s, %s, %s, %s, 'counselor'), (%s, %s, %s, %s, 'counselor')",
            (
                user_a, tid, f"sub-{user_a}", "counselor-a@example.test",
                user_b, tid, f"sub-{user_b}", "counselor-b@example.test",
            ),
        )
    yield tid
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        for table in (
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "users",
        ):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))


@pytest.fixture
def tenant_without_counselors():
    tid = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tid, f"t-{tid}", "No Counselors Tenant"),
        )
    yield tid
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute("DELETE FROM courses WHERE tenant_id = %s", (tid,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))


def _counts(tenant_id):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("SELECT count(*) FROM contacts")
        contacts = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM deals")
        deals = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM activities WHERE type = 'lead_captured'")
        activities = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM courses")
        courses = cur.fetchone()[0]
        cur.execute("SELECT DISTINCT owner_id FROM contacts")
        owners = {row[0] for row in cur.fetchall()}
    return contacts, deals, activities, courses, owners


async def test_ingest_all_creates_contacts_deals_and_activities(tenant_with_counselors):
    ingested = await ingest_all(tenant_with_counselors)

    assert ingested == TOTAL_SAMPLE_LEADS
    contacts, deals, activities, courses, owners = _counts(tenant_with_counselors)
    assert contacts == TOTAL_SAMPLE_LEADS
    assert deals == TOTAL_SAMPLE_LEADS
    assert activities == TOTAL_SAMPLE_LEADS
    assert courses == 4
    assert len(owners) == 2  # round-robin touched both seeded counselors


async def test_rerunning_ingest_all_does_not_duplicate(tenant_with_counselors):
    first = await ingest_all(tenant_with_counselors)
    second = await ingest_all(tenant_with_counselors)

    assert first == TOTAL_SAMPLE_LEADS
    assert second == 0
    contacts, deals, activities, _, _ = _counts(tenant_with_counselors)
    assert contacts == TOTAL_SAMPLE_LEADS
    assert deals == TOTAL_SAMPLE_LEADS
    assert activities == TOTAL_SAMPLE_LEADS


async def test_tenant_with_no_counselors_is_skipped_not_crashed(tenant_without_counselors):
    ingested = await ingest_all(tenant_without_counselors)

    assert ingested == 0
    contacts, deals, activities, courses, _ = _counts(tenant_without_counselors)
    assert contacts == 0
    assert deals == 0
    assert activities == 0
