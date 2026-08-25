"""app/workers/sla.py's compute_sla_states — PHASE_3_PLAN.md §9 step 14 /
§10 acceptance criterion 4. Calls the async implementation directly
(_compute_sla_states), not the Celery task wrapper — same convention
this repo already uses for testing async service logic without needing
a running Celery worker.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.workers.sla import _compute_sla_states

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
APP_URL = os.environ.get("DATABASE_APP_URL", "").replace("+psycopg", "")


def _reachable(url: str) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not (_reachable(MIGRATE_URL) and _reachable(APP_URL)),
    reason="DATABASE_URL/DATABASE_APP_URL not set or Postgres unreachable",
)


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    manager_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    course_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    deal_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "SLA Computation Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'manager')",
            (manager_id, tenant_id, f"sub-{manager_id}", "manager@example.test"),
        )
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role, manager_id) "
            "VALUES (%s, %s, %s, %s, 'counselor', %s)",
            (staff_id, tenant_id, f"sub-{staff_id}", "staff@example.test", manager_id),
        )
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute(
            "INSERT INTO pipeline_stages (id, tenant_id, name, sort_order) VALUES (%s, %s, %s, 1)",
            (stage_id, tenant_id, "Inquiry"),
        )
        cur.execute(
            "INSERT INTO contacts (id, tenant_id, full_name, lead_source, owner_id) "
            "VALUES (%s, %s, %s, 'web', %s)",
            (contact_id, tenant_id, "SLA Test Contact", staff_id),
        )
        # stage_changed_at 2 hours in the past — well past a 30-minute target.
        past = datetime.now(UTC) - timedelta(hours=2)
        cur.execute(
            "INSERT INTO deals (id, tenant_id, contact_id, course_id, stage_id, owner_id, "
            "stage_changed_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (deal_id, tenant_id, contact_id, course_id, stage_id, staff_id, past),
        )
        cur.execute(
            "INSERT INTO sla_policies (id, tenant_id, name, applies_to, stage_id, target_minutes) "
            "VALUES (%s, %s, %s, 'stage_entry', %s, 30)",
            (policy_id, tenant_id, "First contact", stage_id),
        )
        # 24/7 business hours — the default Mon-Fri 09-18 schedule would
        # make this test's pass/fail depend on what real-world weekday
        # it happens to run on, which is exactly the kind of flake
        # add_business_minutes' own unit tests (test_business_hours_service.py)
        # exist to avoid introducing here.
        always_open = '[["00:00","23:59"]]'
        cur.execute(
            "INSERT INTO tenant_sla_settings (id, tenant_id, business_hours) "
            "VALUES (%s, %s, %s::jsonb)",
            (
                uuid.uuid4(),
                tenant_id,
                (
                    '{"mon":' + always_open + ',"tue":' + always_open + ',"wed":' + always_open
                    + ',"thu":' + always_open + ',"fri":' + always_open + ',"sat":' + always_open
                    + ',"sun":' + always_open + "}"
                ),
            ),
        )
        cur.execute("RESET app.tenant_id")

    yield {"tenant_id": tenant_id, "deal_id": deal_id, "manager_id": manager_id}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        tables = (
            "escalations",
            "sla_states",
            "sla_policies",
            "tenant_sla_settings",
            "deals",
            "contacts",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "courses",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _counts(tenant_id):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("SELECT state FROM sla_states")
        states = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT count(*) FROM escalations WHERE source = 'sla_breach'")
        escalation_count = cur.fetchone()[0]
    return states, escalation_count


async def test_breached_deal_raises_exactly_one_escalation(scenario):
    await _compute_sla_states(scenario["tenant_id"])
    states, escalation_count = _counts(scenario["tenant_id"])
    assert states == ["breached"]
    assert escalation_count == 1

    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute("SELECT assigned_to FROM escalations WHERE source = 'sla_breach'")
        assigned_to = cur.fetchone()[0]
    assert str(assigned_to) == str(scenario["manager_id"])


async def test_retick_does_not_duplicate_the_escalation(scenario):
    await _compute_sla_states(scenario["tenant_id"])
    await _compute_sla_states(scenario["tenant_id"])
    _states, escalation_count = _counts(scenario["tenant_id"])
    assert escalation_count == 1
