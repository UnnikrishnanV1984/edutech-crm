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


def _headers(tenant_id, sub="sub-invoice-test", role="counselor") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Invoice Test Tenant"),
        )

    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Invoice Contact", "lead_source": "web"},
            headers=_headers(tenant_id),
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"value": "1000.00"},
            headers=_headers(tenant_id),
        ).json()["data"]

    yield {"tenant_id": tenant_id, "deal_id": deal["id"]}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "invoices",
            "audit_logs",
            "activities",
            "deals",
            "contacts",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "users",
        ):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_create_and_list_invoices(scenario):
    with TestClient(app) as client:
        created = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        listed = client.get(
            f"/api/v1/deals/{scenario['deal_id']}/invoices", headers=_headers(scenario["tenant_id"])
        )
    assert created.status_code == 200
    assert created.json()["data"]["status"] == "draft"
    assert listed.json()["data"][0]["invoice_number"] == "INV-001"


def test_duplicate_invoice_number_returns_409(scenario):
    with TestClient(app) as client:
        client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        second = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "500.00"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert second.status_code == 409


def test_draft_to_sent_sets_issued_at(scenario):
    with TestClient(app) as client:
        invoice = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        assert invoice["issued_at"] is None

        sent = client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "sent"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert sent.status_code == 200
    assert sent.json()["data"]["status"] == "sent"
    assert sent.json()["data"]["issued_at"] is not None


def test_client_cannot_set_status_to_paid(scenario):
    """PIPELINE_AND_REVENUE_PLAN.md §8 — paid is system-only."""
    with TestClient(app) as client:
        invoice = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "paid"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 422 or response.status_code == 400


def test_client_cannot_set_status_to_rework_requested(scenario):
    with TestClient(app) as client:
        invoice = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "rework_requested"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 422 or response.status_code == 400


def test_draft_to_paid_transition_is_rejected_even_via_allowed_value(scenario):
    """Belt and suspenders: 'sent' is a client-settable value, but
    draft -> sent -> (only) then can it go anywhere; jumping straight to
    an invalid target for the state machine (not just an invalid value)
    is still rejected."""
    with TestClient(app) as client:
        invoice = client.post(
            f"/api/v1/deals/{scenario['deal_id']}/invoices",
            json={"invoice_number": "INV-001", "amount": "1000.00"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "sent"},
            headers=_headers(scenario["tenant_id"]),
        )
        client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "cancelled"},
            headers=_headers(scenario["tenant_id"]),
        )
        # cancelled is terminal — sent is not a valid next value from here.
        response = client.patch(
            f"/api/v1/invoices/{invoice['id']}",
            json={"status": "sent"},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invoice_not_visible_across_tenants(scenario):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            invoice = client.post(
                f"/api/v1/deals/{scenario['deal_id']}/invoices",
                json={"invoice_number": "INV-001", "amount": "1000.00"},
                headers=_headers(scenario["tenant_id"]),
            ).json()["data"]
            response = client.get(
                f"/api/v1/invoices/{invoice['id']}", headers=_headers(other_tenant_id, "sub-other")
            )
        assert response.status_code == 404
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
