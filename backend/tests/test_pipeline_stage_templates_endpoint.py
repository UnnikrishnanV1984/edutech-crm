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
            (tenant_id, f"t-{tenant_id}", "Template Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_admin_can_list_templates(tenant):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/pipeline-stage-templates", headers=_headers(tenant, "sub-admin", "admin")
        )
    assert response.status_code == 200
    names = {t["name"] for t in response.json()["data"]}
    assert "Invoice Sent" in names
    assert "Invoice Rework" in names


def test_non_admin_cannot_list_templates(tenant):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/pipeline-stage-templates",
            headers=_headers(tenant, "sub-counselor", "counselor"),
        )
    assert response.status_code == 403


def test_templates_are_identical_across_tenants(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            first = client.get(
                "/api/v1/pipeline-stage-templates", headers=_headers(tenant, "sub-admin", "admin")
            ).json()["data"]
            second = client.get(
                "/api/v1/pipeline-stage-templates",
                headers=_headers(other_tenant_id, "sub-other-admin", "admin"),
            ).json()["data"]
        assert [t["name"] for t in first] == [t["name"] for t in second]
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))


def test_no_mutating_routes_exist_for_templates(tenant):
    """PIPELINE_AND_REVENUE_PLAN.md §8 — hard requirement: the entire
    justification for skipping RLS on this table is that no tenant-facing
    write path exists, ever."""
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        post_response = client.post(
            "/api/v1/pipeline-stage-templates", json={"name": "Hacked"}, headers=admin_headers
        )
        patch_response = client.patch(
            "/api/v1/pipeline-stage-templates/00000000-0000-0000-0000-000000000000",
            json={"name": "Hacked"},
            headers=admin_headers,
        )
        delete_response = client.delete(
            "/api/v1/pipeline-stage-templates/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
        )
    assert post_response.status_code in (404, 405)
    assert patch_response.status_code in (404, 405)
    assert delete_response.status_code in (404, 405)
