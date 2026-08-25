"""Configurations "Branding" tab — upload/confirm/fetch round trip and
tenant isolation. Mirrors test_documents_endpoint.py's conventions since
branding assets reuse the same S3/MinIO upload primitives.
"""

import os
import uuid

import boto3
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
        for table in ("tenant_branding", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_branding_is_null_when_unconfigured(tenant):
    with TestClient(app) as client:
        response = client.get("/api/v1/branding", headers=_headers(tenant, "sub-admin", "admin"))
    assert response.status_code == 200
    assert response.json()["data"] == {
        "logo_url": None,
        "header_image_url": None,
        "updated_at": None,
    }


def test_staff_cannot_request_upload_url(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/branding/upload-url",
            json={"asset_type": "logo", "filename": "logo.png", "content_type": "image/png"},
            headers=_headers(tenant, "sub-staff", "counselor"),
        )
    assert response.status_code == 403


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


def test_full_upload_confirm_fetch_round_trip(tenant):
    import httpx

    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        upload_resp = client.post(
            "/api/v1/branding/upload-url",
            json={"asset_type": "logo", "filename": "logo.png", "content_type": "image/png"},
            headers=admin_headers,
        ).json()["data"]

        put_response = httpx.put(
            upload_resp["upload_url"],
            content=b"fake png bytes",
            headers={"Content-Type": "image/png"},
        )
        assert put_response.status_code == 200

        confirm = client.post(
            "/api/v1/branding/confirm",
            json={"asset_type": "logo", "s3_key": upload_resp["s3_key"]},
            headers=admin_headers,
        )
        assert confirm.status_code == 200
        assert confirm.json()["data"]["logo_url"] is not None
        assert confirm.json()["data"]["header_image_url"] is None

        # Any authenticated role, not just admin, can read the applied branding.
        staff_response = client.get(
            "/api/v1/branding", headers=_headers(tenant, "sub-staff", "counselor")
        )
        logo_url = staff_response.json()["data"]["logo_url"]
        fetched = httpx.get(logo_url)
    assert fetched.status_code == 200
    assert fetched.content == b"fake png bytes"


def test_header_image_upload_does_not_clear_logo(tenant):
    import httpx

    with TestClient(app) as client:
        admin_headers = _headers(tenant, "sub-admin", "admin")
        logo_upload = client.post(
            "/api/v1/branding/upload-url",
            json={"asset_type": "logo", "filename": "logo.png", "content_type": "image/png"},
            headers=admin_headers,
        ).json()["data"]
        httpx.put(
            logo_upload["upload_url"],
            content=b"logo bytes",
            headers={"Content-Type": "image/png"},
        )
        client.post(
            "/api/v1/branding/confirm",
            json={"asset_type": "logo", "s3_key": logo_upload["s3_key"]},
            headers=admin_headers,
        )

        header_upload = client.post(
            "/api/v1/branding/upload-url",
            json={"asset_type": "header", "filename": "header.png", "content_type": "image/png"},
            headers=admin_headers,
        ).json()["data"]
        httpx.put(
            header_upload["upload_url"],
            content=b"header bytes",
            headers={"Content-Type": "image/png"},
        )
        confirm = client.post(
            "/api/v1/branding/confirm",
            json={"asset_type": "header", "s3_key": header_upload["s3_key"]},
            headers=admin_headers,
        )
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


def test_other_tenant_sees_no_branding(tenant):
    import httpx

    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Branding Tenant"),
        )
    try:
        with TestClient(app) as client:
            admin_headers = _headers(tenant, "sub-admin", "admin")
            upload_resp = client.post(
                "/api/v1/branding/upload-url",
                json={"asset_type": "logo", "filename": "logo.png", "content_type": "image/png"},
                headers=admin_headers,
            ).json()["data"]
            httpx.put(
                upload_resp["upload_url"], content=b"bytes", headers={"Content-Type": "image/png"}
            )
            client.post(
                "/api/v1/branding/confirm",
                json={"asset_type": "logo", "s3_key": upload_resp["s3_key"]},
                headers=admin_headers,
            )

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
