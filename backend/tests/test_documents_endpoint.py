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


def _headers(tenant_id, user_sub="sub-doc-pytest") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": user_sub,
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Doc Contact", "lead_source": "web"},
            headers=_headers(tenant_id),
        ).json()["data"]

    yield {"tenant_id": tenant_id, "contact_id": contact["id"]}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM documents WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM contacts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_full_upload_confirm_download_round_trip(scenario):
    import httpx

    with TestClient(app) as client:
        upload_resp = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/documents/upload-url",
            json={"filename": "resume.pdf", "content_type": "application/pdf"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]

        put_response = httpx.put(
            upload_resp["upload_url"],
            content=b"real file bytes",
            headers={"Content-Type": "application/pdf"},
        )
        assert put_response.status_code == 200

        confirm = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/documents",
            json={
                "filename": "resume.pdf",
                "content_type": "application/pdf",
                "size_bytes": 16,
                "s3_key": upload_resp["s3_key"],
            },
            headers=_headers(scenario["tenant_id"]),
        )
        assert confirm.status_code == 200
        document_id = confirm.json()["data"]["id"]

        download_resp = client.get(
            f"/api/v1/documents/{document_id}/download-url",
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]

        fetched = httpx.get(download_resp["download_url"])
    assert fetched.status_code == 200
    assert fetched.content == b"real file bytes"


def test_confirm_rejects_s3_key_outside_tenant_contact_prefix(scenario):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/documents",
            json={
                "filename": "evil.pdf",
                "content_type": "application/pdf",
                "size_bytes": 10,
                "s3_key": "b2222222-2222-2222-2222-222222222222/other/tampered.pdf",
            },
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_url_for_unknown_contact_returns_404(scenario):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/contacts/{uuid.uuid4()}/documents/upload-url",
            json={"filename": "resume.pdf", "content_type": "application/pdf"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 404


def test_list_documents_for_contact(scenario):
    with TestClient(app) as client:
        upload_resp = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/documents/upload-url",
            json={"filename": "notes.txt", "content_type": "text/plain"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/documents",
            json={
                "filename": "notes.txt",
                "content_type": "text/plain",
                "size_bytes": 5,
                "s3_key": upload_resp["s3_key"],
            },
            headers=_headers(scenario["tenant_id"]),
        )
        listed = client.get(
            f"/api/v1/contacts/{scenario['contact_id']}/documents",
            headers=_headers(scenario["tenant_id"]),
        )
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1
    assert listed.json()["data"][0]["filename"] == "notes.txt"


def test_other_tenant_cannot_get_download_url_for_this_document(scenario):
    """PHASE_1_PLAN.md §8 criterion 8 — a tenant-B request for tenant-A's
    document id gets 404, never a valid presigned URL."""
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            upload_resp = client.post(
                f"/api/v1/contacts/{scenario['contact_id']}/documents/upload-url",
                json={"filename": "secret.pdf", "content_type": "application/pdf"},
                headers=_headers(scenario["tenant_id"]),
            ).json()["data"]
            document = client.post(
                f"/api/v1/contacts/{scenario['contact_id']}/documents",
                json={
                    "filename": "secret.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 5,
                    "s3_key": upload_resp["s3_key"],
                },
                headers=_headers(scenario["tenant_id"]),
            ).json()["data"]

            response = client.get(
                f"/api/v1/documents/{document['id']}/download-url",
                headers=_headers(other_tenant_id, "sub-other-tenant-doc-test"),
            )
        assert response.status_code == 404
        assert "download_url" not in response.json().get("data", {})
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
