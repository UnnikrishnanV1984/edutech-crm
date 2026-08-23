"""WhatsApp Cloud API webhook pipeline — mirrors test_webhooks_meta.py's
structure/rigor (PHASE_2_PLAN.md §4.2/§8), reusing the shared HMAC
verification helper rather than duplicating its own test of that logic.
"""

import os
import uuid

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
MOCK_BASE_URL = os.environ.get("WHATSAPP_API_BASE_URL", "").rsplit("/whatsapp", 1)[0]


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
def tenant_with_counselor_and_courses():
    tid = uuid.uuid4()
    counselor_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tid, f"t-{tid}", "WhatsApp Webhook Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'counselor')",
            (counselor_id, tid, f"sub-{counselor_id}", "counselor@example.test"),
        )
        cur.execute(
            "INSERT INTO courses (tenant_id, name, code) VALUES (%s, %s, %s), (%s, %s, %s)",
            (tid, "MBA Finance", "MBA-FIN", tid, "Web Bootcamp", "WEB-BOOT"),
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


def _connect_whatsapp(client: TestClient, tenant_id, phone_number_id: str):
    return client.post(
        "/api/v1/lead-source-connections",
        json={
            "source": "whatsapp",
            "external_account_id": phone_number_id,
            "access_token": "fake-token",
        },
        headers=_admin_headers(tenant_id),
    )


def _contact_count(tenant_id, full_name: str) -> int:
    with psycopg.connect(
        os.environ.get("DATABASE_APP_URL", "").replace("+psycopg", ""), autocommit=True
    ) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("SELECT count(*) FROM contacts WHERE full_name = %s", (full_name,))
        return cur.fetchone()[0]


def test_triggered_whatsapp_message_lands_as_contact(tenant_with_counselor_and_courses):
    tenant_id = tenant_with_counselor_and_courses
    phone_number_id = f"phone-{uuid.uuid4()}"
    with TestClient(app) as client:
        connect_response = _connect_whatsapp(client, tenant_id, phone_number_id)
    assert connect_response.status_code == 200

    trigger_response = httpx.post(
        f"{MOCK_BASE_URL}/whatsapp/_trigger", json={"external_account_id": phone_number_id}
    )
    assert trigger_response.status_code == 200
    assert trigger_response.json()["backend_status"] == 200
    assert _contact_count(tenant_id, "Rohan Kulkarni") == 1


def test_redelivering_same_message_is_a_no_op(tenant_with_counselor_and_courses):
    tenant_id = tenant_with_counselor_and_courses
    phone_number_id = f"phone-{uuid.uuid4()}"
    with TestClient(app) as client:
        _connect_whatsapp(client, tenant_id, phone_number_id)

    first = httpx.post(
        f"{MOCK_BASE_URL}/whatsapp/_trigger",
        json={"external_account_id": phone_number_id, "wa_id": "919876522002"},
    )
    second = httpx.post(
        f"{MOCK_BASE_URL}/whatsapp/_trigger",
        json={"external_account_id": phone_number_id, "wa_id": "919876522002"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert _contact_count(tenant_id, "Tanya Chawla") == 1


def test_unsigned_webhook_is_rejected(tenant_with_counselor_and_courses):
    with TestClient(app) as client:
        response = client.post("/webhooks/whatsapp", json={"entry": []})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_message_with_no_course_selection_still_creates_contact(
    tenant_with_counselor_and_courses,
):
    tenant_id = tenant_with_counselor_and_courses
    phone_number_id = f"phone-{uuid.uuid4()}"
    with TestClient(app) as client:
        _connect_whatsapp(client, tenant_id, phone_number_id)

    # Third fixture record (Imran Qureshi) has course_code=null.
    response = httpx.post(
        f"{MOCK_BASE_URL}/whatsapp/_trigger",
        json={"external_account_id": phone_number_id, "wa_id": "919876522003"},
    )
    assert response.status_code == 200
    assert response.json()["backend_status"] == 200
    assert _contact_count(tenant_id, "Imran Qureshi") == 1
