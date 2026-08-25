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


def _headers(tenant_id, role="admin") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": "sub-sla-test",
        "X-User-Email": "user@example.test",
        "X-User-Role": role,
    }


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "SLA Policy Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM sla_policies WHERE tenant_id = %s", (tenant_id,))
        cur.execute(
            "DELETE FROM pipeline_stage_default_snapshots WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_counselor_gets_403(tenant):
    with TestClient(app) as client:
        response = client.get("/api/v1/sla-policies", headers=_headers(tenant, "counselor"))
    assert response.status_code == 403


def test_create_task_due_policy(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sla-policies",
            json={"name": "Task SLA", "applies_to": "task_due", "target_minutes": 60},
            headers=_headers(tenant),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["applies_to"] == "task_due"
    assert body["stage_id"] is None
    assert body["warning_threshold_pct"] == 80


def test_create_stage_entry_policy_requires_stage_id(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sla-policies",
            json={"name": "First contact", "applies_to": "stage_entry", "target_minutes": 30},
            headers=_headers(tenant),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_stage_entry_policy_with_stage_id(tenant):
    with TestClient(app) as client:
        stages = client.get("/api/v1/pipeline-stages", headers=_headers(tenant)).json()["data"]
        response = client.post(
            "/api/v1/sla-policies",
            json={
                "name": "First contact",
                "applies_to": "stage_entry",
                "stage_id": stages[0]["id"],
                "target_minutes": 30,
            },
            headers=_headers(tenant),
        )
    assert response.status_code == 200
    assert response.json()["data"]["stage_id"] == stages[0]["id"]


def test_patch_disables_policy(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sla-policies",
            json={"name": "Task SLA", "applies_to": "task_due", "target_minutes": 60},
            headers=_headers(tenant),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/sla-policies/{created['id']}",
            json={"status": "disabled"},
            headers=_headers(tenant),
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "disabled"
