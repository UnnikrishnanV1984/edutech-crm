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
def tenant_and_user():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    yield {"tenant_id": tenant_id, "user_sub": "sub-stage-test"}
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _headers(ctx: dict) -> dict:
    return {
        "X-Tenant-Id": str(ctx["tenant_id"]),
        "X-User-Id": ctx["user_sub"],
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


def test_list_seeds_default_stages_lazily(tenant_and_user):
    with TestClient(app) as client:
        response = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
    assert response.status_code == 200
    stages = response.json()["data"]
    names = [s["name"] for s in stages]
    assert names == [
        "Inquiry",
        "Contacted",
        "Demo scheduled",
        "Demo attended",
        "Application submitted",
        "Fee paid",
        "Enrolled",
        "Dropped",
    ]
    enrolled = next(s for s in stages if s["name"] == "Enrolled")
    dropped = next(s for s in stages if s["name"] == "Dropped")
    assert enrolled["is_won"] is True
    assert dropped["is_lost"] is True


def test_seeding_is_idempotent(tenant_and_user):
    with TestClient(app) as client:
        first = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
        second = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
    assert len(first.json()["data"]) == 8
    assert len(second.json()["data"]) == 8
    assert [s["id"] for s in first.json()["data"]] == [s["id"] for s in second.json()["data"]]


def test_rename_stage(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")

        response = client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "New Inquiry"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "New Inquiry"


def test_rename_to_existing_name_returns_409(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")

        response = client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "Contacted"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_two_tenants_get_independent_default_stages(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            client.patch(
                (
                    "/api/v1/pipeline-stages/"
                    + client.get(
                        "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
                    ).json()["data"][0]["id"]
                ),
                json={"name": "Tenant A Custom Name"},
                headers=_headers(tenant_and_user),
            )
            other_headers = {
                "X-Tenant-Id": str(tenant_id_2),
                "X-User-Id": "sub-other",
                "X-User-Email": "other@example.test",
                "X-User-Role": "counselor",
            }
            other_stages = client.get("/api/v1/pipeline-stages", headers=other_headers).json()[
                "data"
            ]
        assert other_stages[0]["name"] == "Inquiry"
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))
