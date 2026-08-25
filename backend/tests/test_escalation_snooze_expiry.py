"""app/workers/escalations.py's expire_snoozed_escalations —
OPENFUNNEL_REBRAND_PLAN.md Phase 7e acceptance criterion: a snoozed
escalation automatically reopens once snoozed_until passes, without any
user action. Calls the async implementation directly
(_expire_snoozed_escalations), same convention test_sla_computation.py
already uses for testing worker logic without a running Celery worker.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.workers.escalations import _expire_snoozed_escalations

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
    past_escalation_id = uuid.uuid4()
    future_escalation_id = uuid.uuid4()

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Snooze Expiry Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'manager')",
            (manager_id, tenant_id, f"sub-{manager_id}", "manager@example.test"),
        )
        cur.execute(
            "INSERT INTO escalations "
            "(id, tenant_id, source, raised_by, assigned_to, status, snoozed_until) "
            "VALUES (%s, %s, 'manual', %s, %s, 'snoozed', %s)",
            (
                past_escalation_id,
                tenant_id,
                manager_id,
                manager_id,
                datetime.now(UTC) - timedelta(hours=1),
            ),
        )
        cur.execute(
            "INSERT INTO escalations "
            "(id, tenant_id, source, raised_by, assigned_to, status, snoozed_until) "
            "VALUES (%s, %s, 'manual', %s, %s, 'snoozed', %s)",
            (
                future_escalation_id,
                tenant_id,
                manager_id,
                manager_id,
                datetime.now(UTC) + timedelta(hours=1),
            ),
        )
        cur.execute("RESET app.tenant_id")

    yield {
        "tenant_id": tenant_id,
        "past_escalation_id": past_escalation_id,
        "future_escalation_id": future_escalation_id,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("escalations", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _fetch(tenant_id, escalation_id):
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT status, snoozed_until FROM escalations WHERE id = %s", (escalation_id,)
        )
        row = cur.fetchone()
        cur.execute("RESET app.tenant_id")
        return row


async def test_expire_reopens_only_past_snoozed_escalations(scenario):
    await _expire_snoozed_escalations(scenario["tenant_id"])

    past_status, past_snoozed_until = _fetch(scenario["tenant_id"], scenario["past_escalation_id"])
    assert past_status == "open"
    assert past_snoozed_until is None

    future_status, future_snoozed_until = _fetch(
        scenario["tenant_id"], scenario["future_escalation_id"]
    )
    assert future_status == "snoozed"
    assert future_snoozed_until is not None
