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


def _headers(tenant_id, user_sub="sub-task-test") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": user_sub,
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Task Contact", "lead_source": "web"},
            headers=_headers(tenant_id),
        ).json()["data"]

    yield {"tenant_id": tenant_id, "contact_id": contact["id"]}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM tasks WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM contacts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_create_task_defaults_assignee_to_acting_user(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks",
            json={"contact_id": scenario["contact_id"], "title": "Call back"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "open"
    assert body["completed_at"] is None


def test_create_task_unknown_contact_returns_400(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks",
            json={"contact_id": str(uuid.uuid4()), "title": "Call back"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_complete_task_sets_completed_at(scenario):
    with TestClient(app) as client:
        task = client.post(
            "/api/v1/tasks",
            json={"contact_id": scenario["contact_id"], "title": "Call back"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]

        completed = client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"status": "done"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert completed.status_code == 200
    body = completed.json()["data"]
    assert body["status"] == "done"
    assert body["completed_at"] is not None


def test_undo_complete_clears_completed_at(scenario):
    with TestClient(app) as client:
        task = client.post(
            "/api/v1/tasks",
            json={"contact_id": scenario["contact_id"], "title": "Call back"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"status": "done"},
            headers=_headers(scenario["tenant_id"]),
        )
        undone = client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"status": "open"},
            headers=_headers(scenario["tenant_id"]),
        )
    body = undone.json()["data"]
    assert body["status"] == "open"
    assert body["completed_at"] is None


def test_list_tasks_filters_by_status(scenario):
    with TestClient(app) as client:
        t1 = client.post(
            "/api/v1/tasks",
            json={"contact_id": scenario["contact_id"], "title": "Open one"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        t2 = client.post(
            "/api/v1/tasks",
            json={"contact_id": scenario["contact_id"], "title": "Done one"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        client.patch(
            f"/api/v1/tasks/{t2['id']}",
            json={"status": "done"},
            headers=_headers(scenario["tenant_id"]),
        )

        open_tasks = client.get(
            "/api/v1/tasks?status=open", headers=_headers(scenario["tenant_id"])
        ).json()["data"]

    assert [t["id"] for t in open_tasks] == [t1["id"]]


def test_assigning_to_a_different_tenants_user_is_rejected(scenario):
    """PHASE_1_PLAN.md §8 criterion 6 — a real user id, just not one that
    exists in *this* tenant. Composite FK (assignee_id, tenant_id) already
    proved this at the raw-SQL level when the tasks migration was built;
    this is the same check at the API layer."""
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            # JIT-provisions a real users row in the other tenant.
            other_user = client.get(
                "/api/v1/me", headers=_headers(other_tenant_id, "sub-other-tenant-user")
            ).json()["data"]["user"]

            response = client.post(
                "/api/v1/tasks",
                json={
                    "contact_id": scenario["contact_id"],
                    "title": "Cross-tenant assignee",
                    "assignee_id": other_user["id"],
                },
                headers=_headers(scenario["tenant_id"]),
            )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
