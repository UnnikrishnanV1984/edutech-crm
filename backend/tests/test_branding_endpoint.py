"""Configurations "Branding" tab — draft/publish/version model
(BRANDING_FULL_SYSTEM_PLAN.md). Mirrors test_documents_endpoint.py's
conventions since branding assets reuse the same S3/MinIO upload
primitives.
"""

import os
import uuid

import boto3
import httpx
import psycopg
import pytest
from botocore.client import Config
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")


def _db_reachable() -> bool:
    if not MIGRATE_URL:
        return False
    try:
        with psycopg.connect(MIGRATE_URL, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


def _s3_reachable() -> bool:
    endpoint = os.environ.get("S3_ENDPOINT", "")
    if not endpoint:
        return False
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY", ""),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=2,
                read_timeout=2,
                retries={"max_attempts": 0},
            ),
        )
        client.head_bucket(Bucket=os.environ.get("S3_BUCKET", ""))
        return True
    except (EndpointConnectionError, Exception):
        return False


pytestmark = pytest.mark.skipif(
    not (_db_reachable() and _s3_reachable()),
    reason="DATABASE_URL/S3_ENDPOINT not set or Postgres/MinIO unreachable",
)


def _headers(tenant_id, sub, role) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Branding Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("tenant_branding_versions", "tenant_branding", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _upload(client, headers, asset_type, filename, content):
    upload_resp = client.post(
        "/api/v1/branding/upload-url",
        json={"asset_type": asset_type, "filename": filename, "content_type": "image/png"},
        headers=headers,
    ).json()["data"]
    httpx.put(upload_resp["upload_url"], content=content, headers={"Content-Type": "image/png"})
    return client.post(
        "/api/v1/branding/confirm",
        json={"asset_type": asset_type, "s3_key": upload_resp["s3_key"]},
        headers=headers,
    )


# --- Live (published) surface ------------------------------------------


def test_live_branding_is_default_when_never_published(tenant):
    with TestClient(app) as client:
        response = client.get("/api/v1/branding", headers=_headers(tenant, "sub-admin", "admin"))
    assert response.status_code == 200
    assert response.json()["data"] == {
        "logo_url": None,
        "header_image_url": None,
        "favicon_url": None,
        "company_display_name": None,
        "accent_color": None,
        "header_background": "light",
        "typeface": "system",
        "updated_at": None,
    }


def test_draft_edits_do_not_affect_live_until_published(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        _upload(client, admin_headers, "logo", "logo.png", b"logo bytes")
        client.patch(
            "/api/v1/branding/draft",
            json={"company_display_name": "Acme Academy"},
            headers=admin_headers,
        )
        live = client.get("/api/v1/branding", headers=admin_headers)
    assert live.json()["data"]["logo_url"] is None
    assert live.json()["data"]["company_display_name"] is None


def test_publish_makes_the_draft_live(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        _upload(client, admin_headers, "logo", "logo.png", b"logo bytes")
        client.patch(
            "/api/v1/branding/draft",
            json={"company_display_name": "Acme Academy", "accent_color": "#B68235"},
            headers=admin_headers,
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        live = client.get(
            "/api/v1/branding", headers=_headers(tenant, "sub-staff", "counselor")
        ).json()["data"]
        fetched = httpx.get(live["logo_url"])
    assert live["company_display_name"] == "Acme Academy"
    assert live["accent_color"] == "#B68235"
    assert fetched.content == b"logo bytes"


def test_login_backdrop_never_appears_on_the_live_surface(tenant):
    """No real login page exists to apply it to — BrandingOut deliberately
    omits it so nothing silently ignores a field that claims to be live."""
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        _upload(client, admin_headers, "login_backdrop", "backdrop.png", b"backdrop bytes")
        client.post("/api/v1/branding/publish", headers=admin_headers)
        live = client.get("/api/v1/branding", headers=admin_headers).json()["data"]
    assert "login_backdrop_url" not in live


def test_other_tenant_never_sees_this_tenants_live_branding(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Branding Tenant"),
        )
    try:
        with TestClient(app) as client:
            admin_headers = _headers(tenant, "sub-admin", "admin")
            _upload(client, admin_headers, "logo", "logo.png", b"logo bytes")
            client.post("/api/v1/branding/publish", headers=admin_headers)
            other_response = client.get(
                "/api/v1/branding", headers=_headers(other_tenant_id, "sub-other", "admin")
            )
        assert other_response.json()["data"]["logo_url"] is None
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))


# --- Draft ----------------------------------------------------------------


def test_staff_cannot_see_or_edit_the_draft(tenant):
    with TestClient(app) as client:
        staff_headers = _headers(tenant, "sub-staff", "counselor")
        get_resp = client.get("/api/v1/branding/draft", headers=staff_headers)
        put_resp = client.patch(
            "/api/v1/branding/draft", json={"company_display_name": "x"}, headers=staff_headers
        )
    assert get_resp.status_code == 403
    assert put_resp.status_code == 403


def test_draft_auto_vivifies_with_defaults(tenant):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/branding/draft", headers=_headers(tenant, "sub-admin", "admin")
        )
    data = response.json()["data"]
    assert data["header_background"] == "light"
    assert data["typeface"] == "system"
    assert data["logo_url"] is None


def test_put_draft_rejects_invalid_accent_color(tenant):
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/branding/draft",
            json={"accent_color": "not-a-color"},
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400


def test_put_draft_rejects_invalid_header_background(tenant):
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/branding/draft",
            json={"header_background": "rainbow"},
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400


def test_put_draft_rejects_invalid_typeface(tenant):
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/branding/draft",
            json={"typeface": "comic-sans"},
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400


def test_custom_domain_saves_but_is_never_returned_live(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        client.patch(
            "/api/v1/branding/draft",
            json={"custom_domain": "crm.tenant.example"},
            headers=admin_headers,
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        draft = client.get("/api/v1/branding/draft", headers=admin_headers).json()["data"]
        live = client.get("/api/v1/branding", headers=admin_headers).json()["data"]
    assert draft["custom_domain"] == "crm.tenant.example"
    assert "custom_domain" not in live


def test_header_and_logo_upload_do_not_clear_each_other_on_the_draft(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        _upload(client, admin_headers, "logo", "logo.png", b"logo bytes")
        confirm = _upload(client, admin_headers, "header", "header.png", b"header bytes")
    data = confirm.json()["data"]
    assert data["logo_url"] is not None
    assert data["header_image_url"] is not None


def test_confirm_rejects_s3_key_outside_tenant_prefix(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/branding/confirm",
            json={
                "asset_type": "logo",
                "s3_key": "b2222222-2222-2222-2222-222222222222/branding/logo/tampered.png",
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_url_rejects_non_image_content_type(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/branding/upload-url",
            json={
                "asset_type": "logo",
                "filename": "logo.exe",
                "content_type": "application/x-msdownload",
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400


# --- Discard ----------------------------------------------------------


def test_discard_resets_draft_to_latest_published_values(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        client.patch(
            "/api/v1/branding/draft",
            json={"company_display_name": "Published Name"},
            headers=admin_headers,
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        client.patch(
            "/api/v1/branding/draft",
            json={"company_display_name": "Unpublished Edit"},
            headers=admin_headers,
        )
        discarded = client.post("/api/v1/branding/discard", headers=admin_headers)
    assert discarded.json()["data"]["company_display_name"] == "Published Name"


def test_discard_with_no_prior_publish_resets_to_defaults(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        client.patch(
            "/api/v1/branding/draft",
            json={"company_display_name": "Never Published"},
            headers=admin_headers,
        )
        discarded = client.post("/api/v1/branding/discard", headers=admin_headers)
    data = discarded.json()["data"]
    assert data["company_display_name"] is None
    assert data["header_background"] == "light"
    assert data["typeface"] == "system"


# --- Versions / restore ------------------------------------------------


def test_versions_lists_newest_first_with_is_live(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        client.patch(
            "/api/v1/branding/draft", json={"company_display_name": "v1"}, headers=admin_headers
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        client.patch(
            "/api/v1/branding/draft", json={"company_display_name": "v2"}, headers=admin_headers
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        versions = client.get("/api/v1/branding/versions", headers=admin_headers).json()["data"]
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["is_live"] is True
    assert versions[1]["is_live"] is False


def test_restore_populates_draft_without_publishing(tenant):
    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        client.patch(
            "/api/v1/branding/draft", json={"company_display_name": "v1"}, headers=admin_headers
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)
        client.patch(
            "/api/v1/branding/draft", json={"company_display_name": "v2"}, headers=admin_headers
        )
        client.post("/api/v1/branding/publish", headers=admin_headers)

        versions = client.get("/api/v1/branding/versions", headers=admin_headers).json()["data"]
        v1_id = next(v["id"] for v in versions if v["version_number"] == 1)

        restored = client.post(
            f"/api/v1/branding/versions/{v1_id}/restore", headers=admin_headers
        )
        live_after_restore = client.get("/api/v1/branding", headers=admin_headers).json()["data"]
    assert restored.json()["data"]["company_display_name"] == "v1"
    # Still live at v2 — restore populates the draft only, doesn't publish.
    assert live_after_restore["company_display_name"] == "v2"


def test_restore_rejects_a_cross_tenant_version_id(tenant):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Version Tenant"),
        )
    try:
        with TestClient(app) as client:
            other_admin_headers = _headers(other_tenant_id, "sub-other-admin", "admin")
            client.patch(
                "/api/v1/branding/draft",
                json={"company_display_name": "someone else's"},
                headers=other_admin_headers,
            )
            client.post("/api/v1/branding/publish", headers=other_admin_headers)
            other_versions = client.get(
                "/api/v1/branding/versions", headers=other_admin_headers
            ).json()["data"]
            other_version_id = other_versions[0]["id"]

            response = client.post(
                f"/api/v1/branding/versions/{other_version_id}/restore",
                headers=_headers(tenant, "sub-admin", "admin"),
            )
        assert response.status_code == 404
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            for table in ("tenant_branding_versions", "tenant_branding", "users"):
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))


def test_manager_cannot_publish_discard_or_view_versions(tenant):
    with TestClient(app) as client:
        manager_headers = _headers(tenant, "sub-manager", "manager")
        publish_resp = client.post("/api/v1/branding/publish", headers=manager_headers)
        discard_resp = client.post("/api/v1/branding/discard", headers=manager_headers)
        versions_resp = client.get("/api/v1/branding/versions", headers=manager_headers)
    assert publish_resp.status_code == 403
    assert discard_resp.status_code == 403
    assert versions_resp.status_code == 403
