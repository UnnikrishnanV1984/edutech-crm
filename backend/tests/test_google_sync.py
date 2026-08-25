"""Google Ads Lead Form pull sync — PHASE_2_PLAN.md §4.3/§8. Admin
triggers POST .../{id}/sync (no scheduler exists yet, an explicit
boundary — see google_sync_service.py's docstring). Connecting with no
access_token_encrypted and a bogus refresh token exercises the
OAuth-refresh branch against the mock, not just the happy "token still
valid" path.
"""

import os
import uuid

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
MOCK_BASE_URL = os.environ.get("GOOGLE_ADS_API_BASE_URL", "").rsplit("/google", 1)[0]


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
            (tid, f"t-{tid}", "Google Sync Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'counselor')",
            (counselor_id, tid, f"sub-{counselor_id}", "counselor@example.test"),
        )
        cur.execute(
            "INSERT INTO courses (tenant_id, name, code) VALUES (%s, %s, %s), (%s, %s, %s)",
            (tid, "Data Science", "DS-202", tid, "Web Bootcamp", "WEB-BOOT"),
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


def test_sync_pulls_leads_via_oauth_refresh(tenant_with_counselor_and_courses):
    tenant_id = tenant_with_counselor_and_courses
    with TestClient(app) as client:
        # No token_expires_at supplied -> treated as expired -> exercises
        # the refresh branch against the mock's /oauth/token.
        connect_response = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "google",
                "external_account_id": f"customer-{uuid.uuid4()}",
                "access_token": "initial-access-token",
                "refresh_token": "mock-refresh-token",
            },
            headers=_admin_headers(tenant_id),
        )
        assert connect_response.status_code == 200
        connection_id = connect_response.json()["data"]["id"]

        sync_response = client.post(
            f"/api/v1/lead-source-connections/{connection_id}/sync",
            headers=_admin_headers(tenant_id),
        )
    assert sync_response.status_code == 200
    assert sync_response.json()["data"]["ingested"] == 2


def test_rerunning_sync_does_not_duplicate(tenant_with_counselor_and_courses):
    tenant_id = tenant_with_counselor_and_courses
    with TestClient(app) as client:
        connect_response = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "google",
                "external_account_id": f"customer-{uuid.uuid4()}",
                "access_token": "initial-access-token",
                "refresh_token": "mock-refresh-token",
            },
            headers=_admin_headers(tenant_id),
        )
        connection_id = connect_response.json()["data"]["id"]

        first = client.post(
            f"/api/v1/lead-source-connections/{connection_id}/sync",
            headers=_admin_headers(tenant_id),
        )
        second = client.post(
            f"/api/v1/lead-source-connections/{connection_id}/sync",
            headers=_admin_headers(tenant_id),
        )
    assert first.json()["data"]["ingested"] == 2
    assert second.json()["data"]["ingested"] == 0
