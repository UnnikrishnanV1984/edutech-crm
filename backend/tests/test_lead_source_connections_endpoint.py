"""PHASE_2_PLAN.md §4.1/§8 — admin-only connection management. Covers:
require_admin rejecting non-admin roles (acceptance criterion 7), the
global-uniqueness 409 not leaking which tenant holds it (criterion 8),
and that list/get never return another tenant's connection — the one
dedicated test this table needs since it has no RLS to catch a missing
filter for it (criterion 6, DATABASE_SCHEMA.md §1's exemption note).
"""

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


def _headers(tenant_id, role: str = "admin", sub: str = "sub-admin") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


def _cleanup(tenant_id) -> None:
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM lead_source_connections WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    yield tenant_id
    _cleanup(tenant_id)


def test_counselor_gets_403_admin_succeeds(tenant):
    with TestClient(app) as client:
        denied = client.get(
            "/api/v1/lead-source-connections", headers=_headers(tenant, "counselor")
        )
        allowed = client.get(
            "/api/v1/lead-source-connections", headers=_headers(tenant, "admin")
        )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"
    assert allowed.status_code == 200


def test_create_and_list_meta_connection(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "meta",
                "external_account_id": f"page-{uuid.uuid4()}",
                "access_token": "secret-token",
            },
            headers=_headers(tenant),
        )
        assert created.status_code == 200
        body = created.json()["data"]
        assert body["source"] == "meta"
        assert "access_token" not in body
        assert "access_token_encrypted" not in body

        listed = client.get("/api/v1/lead-source-connections", headers=_headers(tenant))
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_web_connection_generates_embed_key(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/lead-source-connections", json={"source": "web"}, headers=_headers(tenant)
        )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["source"] == "web"
    assert body["external_account_id"]


def test_duplicate_external_account_returns_409_without_leaking_tenant(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        account_id = f"page-{uuid.uuid4()}"
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/lead-source-connections",
                json={"source": "meta", "external_account_id": account_id, "access_token": "t1"},
                headers=_headers(tenant),
            )
            assert first.status_code == 200

            second = client.post(
                "/api/v1/lead-source-connections",
                json={"source": "meta", "external_account_id": account_id, "access_token": "t2"},
                headers=_headers(other_tenant_id),
            )
        assert second.status_code == 409
        message = second.json()["error"]["message"].lower()
        assert str(tenant) not in message
        assert str(other_tenant_id) not in message
    finally:
        _cleanup(other_tenant_id)


def test_disconnect_flips_status_not_delete(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "meta",
                "external_account_id": f"page-{uuid.uuid4()}",
                "access_token": "t",
            },
            headers=_headers(tenant),
        )
        connection_id = created.json()["data"]["id"]

        patched = client.patch(
            f"/api/v1/lead-source-connections/{connection_id}",
            json={"status": "disabled"},
            headers=_headers(tenant),
        )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "disabled"


def test_connections_are_tenant_scoped(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            client.post(
                "/api/v1/lead-source-connections",
                json={
                    "source": "meta",
                    "external_account_id": f"page-{uuid.uuid4()}",
                    "access_token": "t",
                },
                headers=_headers(tenant),
            )
            other_created = client.post(
                "/api/v1/lead-source-connections",
                json={
                    "source": "meta",
                    "external_account_id": f"page-{uuid.uuid4()}",
                    "access_token": "t",
                },
                headers=_headers(other_tenant_id),
            ).json()["data"]

            listed = client.get(
                "/api/v1/lead-source-connections", headers=_headers(other_tenant_id)
            )
            assert [c["id"] for c in listed.json()["data"]] == [other_created["id"]]

            cross_tenant_patch = client.patch(
                f"/api/v1/lead-source-connections/{other_created['id']}",
                json={"status": "disabled"},
                headers=_headers(tenant),
            )
        # No single-GET route exists, so tenant scoping on a single
        # connection is proven via PATCH instead — a tenant-A admin
        # cannot even find tenant-B's connection to act on it.
        assert cross_tenant_patch.status_code == 404
    finally:
        _cleanup(other_tenant_id)


def test_sync_rejects_non_google_source(tenant):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "meta",
                "external_account_id": f"page-{uuid.uuid4()}",
                "access_token": "t",
            },
            headers=_headers(tenant),
        )
        connection_id = created.json()["data"]["id"]

        response = client.post(
            f"/api/v1/lead-source-connections/{connection_id}/sync", headers=_headers(tenant)
        )
    assert response.status_code == 400
