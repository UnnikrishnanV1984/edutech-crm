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


def _headers(tenant_id, sub="sub-account-test") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
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
        cur.execute("DELETE FROM accounts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_create_defaults_owner_to_acting_user(tenant):
    with TestClient(app) as client:
        me = client.get("/api/v1/me", headers=_headers(tenant)).json()["data"]["user"]
        created = client.post(
            "/api/v1/accounts", json={"name": "Acme Corp"}, headers=_headers(tenant)
        )
    assert created.status_code == 200
    assert created.json()["data"]["owner_id"] == me["id"]


def test_list_is_tenant_scoped(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            client.post("/api/v1/accounts", json={"name": "Acme Corp"}, headers=_headers(tenant))
            client.post(
                "/api/v1/accounts",
                json={"name": "Other Co"},
                headers=_headers(other_tenant_id, "sub-other"),
            )
            listed = client.get("/api/v1/accounts", headers=_headers(tenant))
        names = [a["name"] for a in listed.json()["data"]]
        assert names == ["Acme Corp"]
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM accounts WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
