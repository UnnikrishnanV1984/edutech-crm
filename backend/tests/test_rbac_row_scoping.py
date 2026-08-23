"""PHASE_3_PLAN.md §4/§10 acceptance criteria 1-3 — RowScope applied to
contacts/deals/tasks list/get/patch, plus the reassignment guard.
"""

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
    """One tenant: an admin, a manager, staff-a (reports to the manager),
    staff-b (no manager) — a contact owned by each staff member."""
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "RBAC Test Tenant"),
        )

    with TestClient(app) as client:
        admin_headers = _headers(tenant_id, "sub-admin", "admin")
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        staff_a_headers = _headers(tenant_id, "sub-staff-a", "counselor")
        staff_b_headers = _headers(tenant_id, "sub-staff-b", "counselor")

        client.get("/api/v1/me", headers=admin_headers)  # JIT-provision the admin row
        manager_id = client.get("/api/v1/me", headers=manager_headers).json()["data"]["user"]["id"]
        staff_a_id = client.get("/api/v1/me", headers=staff_a_headers).json()["data"]["user"]["id"]
        staff_b_id = client.get("/api/v1/me", headers=staff_b_headers).json()["data"]["user"]["id"]

        client.patch(
            f"/api/v1/users/{staff_a_id}",
            json={"manager_id": manager_id},
            headers=admin_headers,
        )

        contact_a = client.post(
            "/api/v1/contacts",
            json={"full_name": "Staff A's Lead", "lead_source": "web", "owner_id": staff_a_id},
            headers=admin_headers,
        ).json()["data"]
        contact_b = client.post(
            "/api/v1/contacts",
            json={"full_name": "Staff B's Lead", "lead_source": "web", "owner_id": staff_b_id},
            headers=admin_headers,
        ).json()["data"]

    yield {
        "tenant_id": tenant_id,
        "admin_headers": admin_headers,
        "manager_headers": manager_headers,
        "staff_a_headers": staff_a_headers,
        "staff_b_headers": staff_b_headers,
        "manager_id": manager_id,
        "staff_a_id": staff_a_id,
        "staff_b_id": staff_b_id,
        "contact_a": contact_a,
        "contact_b": contact_b,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("activities", "deals", "contacts", "tasks", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_staff_list_only_sees_own_contact(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/contacts", headers=scenario["staff_a_headers"])
    names = {c["full_name"] for c in response.json()["data"]}
    assert names == {"Staff A's Lead"}


def test_manager_list_sees_own_team_not_unrelated_staff(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/contacts", headers=scenario["manager_headers"])
    names = {c["full_name"] for c in response.json()["data"]}
    assert names == {"Staff A's Lead"}  # not Staff B's — no manager_id relation


def test_admin_list_sees_everything(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/contacts", headers=scenario["admin_headers"])
    names = {c["full_name"] for c in response.json()["data"]}
    assert names == {"Staff A's Lead", "Staff B's Lead"}


def test_staff_get_outside_scope_is_404_not_403(scenario):
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/contacts/{scenario['contact_b']['id']}", headers=scenario["staff_a_headers"]
        )
    assert response.status_code == 404


def test_manager_get_within_team_succeeds(scenario):
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/contacts/{scenario['contact_a']['id']}", headers=scenario["manager_headers"]
        )
    assert response.status_code == 200


def test_staff_cannot_reassign_even_own_contact(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/contacts/{scenario['contact_a']['id']}",
            json={"owner_id": scenario["staff_a_id"]},
            headers=scenario["staff_a_headers"],
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_manager_can_reassign_within_team(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/contacts/{scenario['contact_a']['id']}",
            json={"owner_id": scenario["manager_id"]},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
    assert response.json()["data"]["owner_id"] == scenario["manager_id"]


def test_manager_cannot_reassign_outside_team(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/contacts/{scenario['contact_a']['id']}",
            json={"owner_id": scenario["staff_b_id"]},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 403


def test_admin_can_reassign_anyone(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/contacts/{scenario['contact_a']['id']}",
            json={"owner_id": scenario["staff_b_id"]},
            headers=scenario["admin_headers"],
        )
    assert response.status_code == 200


def test_non_manager_manager_id_target_is_rejected(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/users/{scenario['staff_b_id']}",
            json={"manager_id": scenario["staff_a_id"]},  # staff_a is not a manager
            headers=scenario["admin_headers"],
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_admin_cannot_patch_users(scenario):
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/users/{scenario['staff_b_id']}",
            json={"manager_id": scenario["manager_id"]},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 403
