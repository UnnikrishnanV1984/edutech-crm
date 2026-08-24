"""PHASE_3_PLAN.md §7.3/§10 acceptance criterion 7 — manager-proposed
rules are always forced to pending_approval."""

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
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Workflow Rules Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("workflow_rules", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


_ACTIONS = [{"type": "notify_manager", "config": {}}]


def test_staff_cannot_see_or_create_rules(tenant):
    with TestClient(app) as client:
        get_response = client.get(
            "/api/v1/workflow-rules", headers=_headers(tenant, "sub-staff", "counselor")
        )
        post_response = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-staff", "counselor"),
        )
    assert get_response.status_code == 403
    assert post_response.status_code == 403


def test_manager_created_rule_is_forced_pending_approval(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Auto-assign new leads",
                "trigger_type": "lead_created",
                "actions": _ACTIONS,
                "status": "active",  # deliberately claims active — must be overridden
            },
            headers=_headers(tenant, "sub-manager", "manager"),
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending_approval"


def test_admin_created_rule_honors_requested_status(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Auto-assign new leads",
                "trigger_type": "lead_created",
                "actions": _ACTIONS,
                "status": "active",
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_manager_cannot_approve_own_rule(tenant):
    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager", "manager"),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/workflow-rules/{rule['id']}",
            json={"status": "active"},
            headers=_headers(tenant, "sub-manager", "manager"),
        )
    assert response.status_code == 403


def test_admin_approves_pending_rule(tenant):
    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager", "manager"),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/workflow-rules/{rule['id']}",
            json={"status": "active"},
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "active"
    assert body["approved_by"] is not None


def test_manager_sees_own_proposal_but_not_other_managers_draft(tenant):
    with TestClient(app) as client:
        client.post(
            "/api/v1/workflow-rules",
            json={"name": "mine", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager-a", "manager"),
        )
        client.post(
            "/api/v1/workflow-rules",
            json={"name": "theirs", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager-b", "manager"),
        )
        listed = client.get(
            "/api/v1/workflow-rules", headers=_headers(tenant, "sub-manager-a", "manager")
        )
    names = {r["name"] for r in listed.json()["data"]}
    assert names == {"mine"}


def test_invalid_action_type_is_rejected(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "x",
                "trigger_type": "lead_created",
                "actions": [{"type": "not_a_real_action"}],
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400
