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


def _headers(tenant_id, sub="sub-payment-test") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Payment Test Tenant"),
        )

    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Payment Contact", "lead_source": "web"},
            headers=_headers(tenant_id),
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={},
            headers=_headers(tenant_id),
        ).json()["data"]
        invoice = client.post(
            f"/api/v1/deals/{deal['id']}/invoices",
            json={"invoice_number": "INV-500", "amount": "1000.00"},
            headers=_headers(tenant_id),
        ).json()["data"]

    yield {"tenant_id": tenant_id, "deal_id": deal["id"], "invoice_id": invoice["id"]}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "payments",
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


def test_partial_payment_does_not_mark_invoice_paid(scenario):
    with TestClient(app) as client:
        client.post(
            f"/api/v1/invoices/{scenario['invoice_id']}/payments",
            json={"amount": "400.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        invoice = client.get(
            f"/api/v1/invoices/{scenario['invoice_id']}", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
    assert invoice["status"] == "draft"


def test_payments_summing_to_amount_marks_invoice_paid(scenario):
    with TestClient(app) as client:
        client.post(
            f"/api/v1/invoices/{scenario['invoice_id']}/payments",
            json={"amount": "400.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        client.post(
            f"/api/v1/invoices/{scenario['invoice_id']}/payments",
            json={"amount": "600.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        invoice = client.get(
            f"/api/v1/invoices/{scenario['invoice_id']}", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        payments = client.get(
            f"/api/v1/invoices/{scenario['invoice_id']}/payments",
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
    assert invoice["status"] == "paid"
    assert len(payments) == 2


def test_overpayment_still_marks_invoice_paid(scenario):
    with TestClient(app) as client:
        client.post(
            f"/api/v1/invoices/{scenario['invoice_id']}/payments",
            json={"amount": "1500.00"},
            headers=_headers(scenario["tenant_id"]),
        )
        invoice = client.get(
            f"/api/v1/invoices/{scenario['invoice_id']}", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
    assert invoice["status"] == "paid"


def test_payment_against_another_tenants_invoice_returns_404(scenario):
    """No FK on payments.invoice_id (0024) — this proves the
    service-layer tenant check is what actually enforces isolation."""
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/invoices/{scenario['invoice_id']}/payments",
                json={"amount": "100.00"},
                headers=_headers(other_tenant_id, "sub-other"),
            )
        assert response.status_code == 404
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
