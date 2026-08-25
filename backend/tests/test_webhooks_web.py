"""Embeddable web-form lead capture — the one fully public, unsigned
route, so its tests cover the rate limit instead of a signature check
(PHASE_2_PLAN.md §6 step 15)."""

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


def _admin_headers(tenant_id) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": "sub-admin",
        "X-User-Email": "admin@example.test",
        "X-User-Role": "admin",
    }


@pytest.fixture
def tenant_with_counselor_and_course():
    tid = uuid.uuid4()
    counselor_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tid, f"t-{tid}", "Web Form Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'counselor')",
            (counselor_id, tid, f"sub-{counselor_id}", "counselor@example.test"),
        )
        cur.execute(
            "INSERT INTO courses (tenant_id, name, code) VALUES (%s, %s, %s)",
            (tid, "MBA Finance", "MBA-FIN"),
        )
    yield tid
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        tables = (
            "activities",
            "deals",
            "contacts",
            "lead_source_connections",
            "courses",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))


def _connect_web(client: TestClient, tenant_id) -> str:
    response = client.post(
        "/api/v1/lead-source-connections",
        json={"source": "web"},
        headers=_admin_headers(tenant_id),
    )
    return response.json()["data"]["external_account_id"]


def test_web_lead_creates_contact(tenant_with_counselor_and_course):
    tenant_id = tenant_with_counselor_and_course
    with TestClient(app) as client:
        embed_key = _connect_web(client, tenant_id)

        response = client.post(
            "/webhooks/web",
            json={
                "embed_key": embed_key,
                "full_name": "Web Test Lead",
                "email": "webtestlead@example.test",
                "course_code": "MBA-FIN",
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "received"


def test_unknown_embed_key_is_404(tenant_with_counselor_and_course):
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/web", json={"embed_key": "does-not-exist", "full_name": "X"}
        )
    assert response.status_code == 404


def test_rate_limit_blocks_after_threshold(tenant_with_counselor_and_course):
    from app.core.config import get_settings

    tenant_id = tenant_with_counselor_and_course
    with TestClient(app) as client:
        embed_key = _connect_web(client, tenant_id)

        limit = get_settings().web_form_rate_limit_per_minute
        statuses = []
        for i in range(limit + 1):
            response = client.post(
                "/webhooks/web",
                json={"embed_key": embed_key, "full_name": f"Lead {i}"},
            )
            statuses.append(response.status_code)
    assert statuses[-1] == 429
    assert all(s == 200 for s in statuses[:-1])
