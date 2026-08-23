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


def test_me_jit_provisions_user(tenant):
    headers = {
        "X-Tenant-Id": str(tenant),
        "X-User-Id": "kc-sub-1",
        "X-User-Email": "counselor.a@example.test",
        "X-User-Name": "Asha Rao",
        "X-User-Role": "counselor",
    }
    with TestClient(app) as client:
        response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["user"]["email"] == "counselor.a@example.test"
    assert body["data"]["user"]["full_name"] == "Asha Rao"
    assert body["data"]["user"]["role"] == "counselor"
    assert body["data"]["tenant"]["id"] == str(tenant)
    assert body["meta"]["request_id"]


def test_me_upsert_is_idempotent_and_refreshes_role(tenant):
    headers = {
        "X-Tenant-Id": str(tenant),
        "X-User-Id": "kc-sub-2",
        "X-User-Email": "b@example.test",
        "X-User-Role": "counselor",
    }
    with TestClient(app) as client:
        first = client.get("/api/v1/me", headers=headers)
        headers["X-User-Role"] = "manager"
        second = client.get("/api/v1/me", headers=headers)

    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]
    assert first.json()["data"]["user"]["role"] == "counselor"
    assert second.json()["data"]["user"]["role"] == "manager"


def test_me_missing_tenant_id_returns_401_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["meta"]["request_id"]


def test_me_unknown_tenant_returns_401_not_404():
    headers = {
        "X-Tenant-Id": str(uuid.uuid4()),
        "X-User-Id": "kc-sub-3",
        "X-User-Email": "c@example.test",
        "X-User-Role": "counselor",
    }
    with TestClient(app) as client:
        response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
