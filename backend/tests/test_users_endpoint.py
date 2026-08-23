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


def _headers(tenant_id, user_sub) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": user_sub,
        "X-User-Email": f"{user_sub}@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_list_users_includes_jit_provisioned_callers(tenant):
    with TestClient(app) as client:
        # Each authenticated call JIT-provisions its own user row.
        client.get("/api/v1/me", headers=_headers(tenant, "sub-a"))
        client.get("/api/v1/me", headers=_headers(tenant, "sub-b"))

        response = client.get("/api/v1/users", headers=_headers(tenant, "sub-a"))

    assert response.status_code == 200
    emails = {u["email"] for u in response.json()["data"]}
    assert emails == {"sub-a@example.test", "sub-b@example.test"}


def test_users_are_tenant_scoped(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            client.get("/api/v1/me", headers=_headers(tenant, "sub-a"))
            client.get("/api/v1/me", headers=_headers(other_tenant_id, "sub-other"))

            response = client.get("/api/v1/users", headers=_headers(tenant, "sub-a"))

        emails = {u["email"] for u in response.json()["data"]}
        assert emails == {"sub-a@example.test"}
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
