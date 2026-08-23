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


def _headers(tenant_id) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": "sub-course-test",
        "X-User-Email": "counselor@example.test",
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
        cur.execute("DELETE FROM courses WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_create_and_list_courses(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/courses", json={"name": "BSc CS", "code": "CS101"}, headers=_headers(tenant)
        )
        assert created.status_code == 200

        listed = client.get("/api/v1/courses", headers=_headers(tenant))
    assert listed.status_code == 200
    names = [c["name"] for c in listed.json()["data"]]
    assert names == ["BSc CS"]


def test_duplicate_code_returns_409(tenant):
    with TestClient(app) as client:
        client.post(
            "/api/v1/courses", json={"name": "BSc CS", "code": "CS101"}, headers=_headers(tenant)
        )
        second = client.post(
            "/api/v1/courses", json={"name": "Other", "code": "CS101"}, headers=_headers(tenant)
        )
    assert second.status_code == 409
