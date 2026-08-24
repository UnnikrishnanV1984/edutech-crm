"""GAP_FIXES_PLAN.md item 6 — audit_logs is write-only in v1 (no read API
yet), so these tests trigger the three real call sites through the actual
API and assert directly against the table."""

import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

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


def _headers(tenant_id, sub, role) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


def _audit_rows(tenant_id, entity_type: str) -> list[tuple]:
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT event_type, entity_id, actor_id, payload FROM audit_logs "
            "WHERE tenant_id = %s AND entity_type = %s ORDER BY created_at",
            (tenant_id, entity_type),
        )
        rows = cur.fetchall()
        cur.execute("RESET app.tenant_id")
    return rows


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Audit Log Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        admin_headers = _headers(tenant_id, "sub-admin", "admin")
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        staff_headers = _headers(tenant_id, "sub-staff", "counselor")

        client.get("/api/v1/me", headers=admin_headers)
        manager_id = client.get("/api/v1/me", headers=manager_headers).json()["data"]["user"]["id"]
        staff_id = client.get("/api/v1/me", headers=staff_headers).json()["data"]["user"]["id"]

        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Audit Contact", "lead_source": "web", "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id), "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]
        stages = client.get("/api/v1/pipeline-stages", headers=admin_headers).json()["data"]

    yield {
        "tenant_id": tenant_id,
        "admin_headers": admin_headers,
        "manager_headers": manager_headers,
        "staff_headers": staff_headers,
        "manager_id": manager_id,
        "staff_id": staff_id,
        "deal_id": deal["id"],
        "stages": stages,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "audit_logs",
            "escalations",
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stages",
            "users",
        ):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_manager_reassignment_is_logged(scenario):
    with TestClient(app) as client:
        client.patch(
            f"/api/v1/users/{scenario['staff_id']}",
            json={"manager_id": scenario["manager_id"]},
            headers=scenario["admin_headers"],
        )
    rows = _audit_rows(scenario["tenant_id"], "user")
    assert len(rows) == 1
    event_type, entity_id, actor_id, payload = rows[0]
    assert event_type == "user.manager_changed"
    assert str(entity_id) == scenario["staff_id"]
    assert payload["new_manager_id"] == scenario["manager_id"]


def test_deal_stage_change_is_logged(scenario):
    new_stage_id = next(s["id"] for s in scenario["stages"] if s["name"] == "Contacted")
    with TestClient(app) as client:
        client.patch(
            f"/api/v1/deals/{scenario['deal_id']}",
            json={"stage_id": new_stage_id},
            headers=scenario["admin_headers"],
        )
    rows = _audit_rows(scenario["tenant_id"], "deal")
    assert len(rows) == 1
    event_type, entity_id, actor_id, payload = rows[0]
    assert event_type == "deal.stage_changed"
    assert str(entity_id) == scenario["deal_id"]
    assert payload["new_stage_id"] == new_stage_id


def test_deal_patch_without_stage_change_logs_nothing(scenario):
    with TestClient(app) as client:
        client.patch(
            f"/api/v1/deals/{scenario['deal_id']}",
            json={"stage_id": scenario["stages"][0]["id"]},
            headers=scenario["admin_headers"],
        )
    assert _audit_rows(scenario["tenant_id"], "deal") == []


def test_escalation_lifecycle_is_logged(scenario):
    with TestClient(app) as client:
        client.patch(
            f"/api/v1/users/{scenario['staff_id']}",
            json={"manager_id": scenario["manager_id"]},
            headers=scenario["admin_headers"],
        )
        escalation = client.post(
            "/api/v1/escalations",
            json={"deal_id": scenario["deal_id"], "reason": "stuck"},
            headers=scenario["staff_headers"],
        ).json()["data"]
        client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["manager_headers"],
        )
        client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved"},
            headers=scenario["manager_headers"],
        )
    rows = _audit_rows(scenario["tenant_id"], "escalation")
    assert [row[0] for row in rows] == ["escalation.acknowledged", "escalation.resolved"]
    assert all(str(row[1]) == escalation["id"] for row in rows)


def test_audit_logs_are_tenant_isolated(scenario):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )

    with TestClient(app) as client:
        client.patch(
            f"/api/v1/users/{scenario['staff_id']}",
            json={"manager_id": scenario["manager_id"]},
            headers=scenario["admin_headers"],
        )

    # APP_URL (crm_app), not MIGRATE_URL (crm_migrate) — crm_migrate owns
    # this table and, per test_tenant_isolation_db.py's own
    # test_crm_app_has_no_superuser_or_bypassrls, only crm_app is
    # guaranteed to actually have RLS enforced against it rather than
    # bypassed.
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
        cur.execute("SELECT count(*) FROM audit_logs")
        count = cur.fetchone()[0]
        cur.execute("RESET app.tenant_id")

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
    assert count == 0
