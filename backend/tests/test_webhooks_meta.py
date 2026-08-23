"""Meta Lead Ads webhook pipeline — PHASE_2_PLAN.md §4.2/§8. Exercises
the mock-integrations service for real (self-signed payloads, no
logic-bypassing mocks, matching this repo's existing rigor), so it needs
both Postgres and a reachable mock-integrations, and skips cleanly
otherwise — same convention as test_ingestion_service.py's
Postgres/Redis skip.
"""

import os
import uuid

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
MOCK_BASE_URL = os.environ.get("META_GRAPH_API_BASE_URL", "").rsplit("/meta", 1)[0]


def _pg_reachable(url: str) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


def _mock_reachable() -> bool:
    if not MOCK_BASE_URL:
        return False
    try:
        return httpx.get(f"{MOCK_BASE_URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not (_pg_reachable(MIGRATE_URL) and _mock_reachable()),
    reason="DATABASE_URL/Postgres or mock-integrations unreachable",
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
            (tid, f"t-{tid}", "Meta Webhook Test Tenant"),
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
            "pipeline_stages",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))


def _connect_meta(client: TestClient, tenant_id, page_id: str):
    return client.post(
        "/api/v1/lead-source-connections",
        json={"source": "meta", "external_account_id": page_id, "access_token": "fake-token"},
        headers=_admin_headers(tenant_id),
    )


def _contact_count(tenant_id, full_name: str) -> int:
    with psycopg.connect(
        os.environ.get("DATABASE_APP_URL", "").replace("+psycopg", ""), autocommit=True
    ) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT count(*) FROM contacts WHERE full_name = %s", (full_name,)
        )
        return cur.fetchone()[0]


def test_unknown_account_is_ignored_without_a_404(tenant_with_counselor_and_course):
    """Mock always delivers 200 once signed; backend must silently ignore
    an account it doesn't recognize rather than leaking whether it
    exists (PHASE_2_PLAN.md §4.2)."""
    response = httpx.post(
        f"{MOCK_BASE_URL}/meta/_trigger", json={"external_account_id": f"unknown-{uuid.uuid4()}"}
    )
    assert response.status_code == 200
    assert response.json()["backend_status"] == 200


def test_triggered_meta_lead_lands_as_contact_deal_activity(tenant_with_counselor_and_course):
    tenant_id = tenant_with_counselor_and_course
    page_id = f"page-{uuid.uuid4()}"
    with TestClient(app) as client:
        connect_response = _connect_meta(client, tenant_id, page_id)
    assert connect_response.status_code == 200

    trigger_response = httpx.post(
        f"{MOCK_BASE_URL}/meta/_trigger", json={"external_account_id": page_id}
    )
    assert trigger_response.status_code == 200
    assert trigger_response.json()["backend_status"] == 200
    assert _contact_count(tenant_id, "Meera Iyer") == 1


def test_redelivering_same_leadgen_id_is_a_no_op(tenant_with_counselor_and_course):
    tenant_id = tenant_with_counselor_and_course
    page_id = f"page-{uuid.uuid4()}"
    with TestClient(app) as client:
        _connect_meta(client, tenant_id, page_id)

    first = httpx.post(f"{MOCK_BASE_URL}/meta/_trigger", json={"external_account_id": page_id})
    second = httpx.post(f"{MOCK_BASE_URL}/meta/_trigger", json={"external_account_id": page_id})
    assert first.status_code == 200
    assert second.status_code == 200
    assert _contact_count(tenant_id, "Meera Iyer") == 1


def test_unsigned_webhook_is_rejected_before_any_db_work(tenant_with_counselor_and_course):
    with TestClient(app) as client:
        response = client.post("/webhooks/meta", json={"entry": []})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_lead_with_no_course_interest_still_creates_contact(tenant_with_counselor_and_course):
    tenant_id = tenant_with_counselor_and_course
    page_id = f"page-{uuid.uuid4()}"
    with TestClient(app) as client:
        _connect_meta(client, tenant_id, page_id)

    # Third fixture record (990211000000003, Ananya Bose) has no
    # course_interest field — PHASE_2_PLAN.md acceptance criterion 10.
    response = httpx.post(
        f"{MOCK_BASE_URL}/meta/_trigger",
        json={"external_account_id": page_id, "leadgen_id": "990211000000003"},
    )
    assert response.status_code == 200
    assert response.json()["backend_status"] == 200
    assert _contact_count(tenant_id, "Ananya Bose") == 1
