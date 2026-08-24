"""PHASE_3_PLAN.md §5/§10 acceptance criterion 5 — escalation lifecycle."""

import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")


def _reachable(url: str) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(MIGRATE_URL), reason="DATABASE_URL not set or Postgres unreachable"
)


def _headers(tenant_id, sub, role) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Escalation Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        staff_headers = _headers(tenant_id, "sub-staff", "counselor")
        other_manager_headers = _headers(tenant_id, "sub-other-manager", "manager")
        admin_headers = _headers(tenant_id, "sub-admin", "admin")

        manager_id = client.get("/api/v1/me", headers=manager_headers).json()["data"]["user"]["id"]
        staff_id = client.get("/api/v1/me", headers=staff_headers).json()["data"]["user"]["id"]
        client.get("/api/v1/me", headers=other_manager_headers)
        client.get("/api/v1/me", headers=admin_headers)

        client.patch(
            f"/api/v1/users/{staff_id}", json={"manager_id": manager_id}, headers=admin_headers
        )

        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Escalation Contact", "lead_source": "web", "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]
        deal_id = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id), "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]["id"]

    yield {
        "tenant_id": tenant_id,
        "manager_headers": manager_headers,
        "staff_headers": staff_headers,
        "other_manager_headers": other_manager_headers,
        "admin_headers": admin_headers,
        "deal_id": deal_id,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        tables = (
            "audit_logs",
            "escalations",
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stages",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _raise(client, headers, deal_id, **overrides) -> dict:
    body = {"deal_id": deal_id, "reason": "stuck"}
    body.update(overrides)
    return client.post("/api/v1/escalations", json=body, headers=headers).json()["data"]


def test_staff_can_raise_escalation_to_their_manager(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
    assert escalation["source"] == "manual"
    assert escalation["status"] == "open"


def test_staff_with_no_manager_gets_409(scenario):
    tenant_id = scenario["tenant_id"]
    orphan_headers = _headers(tenant_id, "sub-orphan-staff", "counselor")
    with TestClient(app) as client:
        client.get("/api/v1/me", headers=orphan_headers)
        response = client.post(
            "/api/v1/escalations",
            json={"deal_id": scenario["deal_id"], "reason": "stuck"},
            headers=orphan_headers,
        )
    assert response.status_code == 409


def test_raise_against_unknown_deal_is_404(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/escalations",
            json={"deal_id": str(uuid.uuid4()), "reason": "stuck"},
            headers=scenario["staff_headers"],
        )
    assert response.status_code == 404


def test_manager_sees_escalation_assigned_to_them(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/escalations", headers=scenario["manager_headers"])
    assert len(response.json()["data"]) == 1


def test_unrelated_manager_does_not_see_it(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/escalations", headers=scenario["other_manager_headers"])
    assert response.json()["data"] == []


def test_open_to_resolved_directly_is_rejected(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved"},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 400


def test_open_then_acknowledged_then_resolved_succeeds(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        ack = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["manager_headers"],
        )
        resolved = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved", "resolution_note": "sorted"},
            headers=scenario["manager_headers"],
        )
    assert ack.status_code == 200
    assert ack.json()["data"]["status"] == "acknowledged"
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"


def test_staff_cannot_acknowledge(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["staff_headers"],
        )
    assert response.status_code == 403


def test_unrelated_manager_cannot_act_on_it(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["other_manager_headers"],
        )
    assert response.status_code == 403
