"""app/workers/conversions.py — ARCHITECTURE.md §7d,
PHASE_4B_CONVERSIONS_PLAN.md §8 acceptance criteria. Calls
_send_conversion_event directly (async), not the Celery task wrapper,
matching test_workflow_rule_engine.py's existing convention. Needs both
Postgres and mock-integrations live, matching test_google_sync.py's
skip-cleanly-if-unreachable convention for the same reason (this
exercises a real outbound HTTP call, not a mocked transport).
"""

import os
import uuid

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workers.conversions import _send_conversion_event

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


def _counselor_headers(tenant_id) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": "sub-counselor",
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def scenario():
    """A tenant with a course, a contact (email+phone set — needed since
    the conversion payload hashes them), and a deal — created through the
    real API, matching test_deals_endpoint.py's scenario fixture."""
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Conversion Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={
                "full_name": "Conversion Contact",
                "lead_source": "meta",
                "email": "lead@example.test",
                "phone": "+15551234567",
            },
            headers=_counselor_headers(tenant_id),
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id)},
            headers=_counselor_headers(tenant_id),
        ).json()["data"]

    yield {
        "tenant_id": tenant_id,
        "course_id": course_id,
        "contact_id": contact["id"],
        "deal_id": deal["id"],
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "conversion_events",
            "activities",
            "deals",
            "contacts",
            "lead_source_connections",
            "courses",
            "pipeline_stages",
            "users",
        ):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _connect_meta(tenant_id, conversion_target_id="pixel-123"):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/lead-source-connections",
            json={
                "source": "meta",
                "external_account_id": f"page-{uuid.uuid4()}",
                "access_token": "secret-meta-token",
            },
            headers=_admin_headers(tenant_id),
        ).json()["data"]
        client.patch(
            f"/api/v1/lead-source-connections/{created['id']}",
            json={"conversion_target_id": conversion_target_id},
            headers=_admin_headers(tenant_id),
        )
    return created["id"]


def _conversion_event_row(tenant_id, deal_id, platform):
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT status, attempts, last_error FROM conversion_events "
            "WHERE tenant_id = %s AND deal_id = %s AND platform = %s",
            (tenant_id, deal_id, platform),
        )
        row = cur.fetchone()
        cur.execute("RESET app.tenant_id")
    return row


async def test_successful_send_records_sent(scenario):
    _connect_meta(scenario["tenant_id"])

    await _send_conversion_event(scenario["tenant_id"], uuid.UUID(scenario["deal_id"]), "meta")

    row = _conversion_event_row(scenario["tenant_id"], scenario["deal_id"], "meta")
    assert row is not None
    status, attempts, last_error = row
    assert status == "sent"
    assert attempts == 1
    assert last_error is None


async def test_undecryptable_token_retries_three_times_then_fails(scenario):
    """Forces a real failure through legitimate means — a corrupted
    access_token_encrypted value that pgp_sym_decrypt genuinely can't
    decrypt — rather than monkeypatching the platform call, matching
    test_workflow_rule_engine.py's test_failing_action_creates_exactly_
    one_failure_escalation's approach of finding a real failure
    condition instead of a mocked one."""
    connection_id = _connect_meta(scenario["tenant_id"])
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE lead_source_connections SET access_token_encrypted = %s WHERE id = %s",
            (b"\x00not-valid-pgp-data", connection_id),
        )

    await _send_conversion_event(scenario["tenant_id"], uuid.UUID(scenario["deal_id"]), "meta")

    row = _conversion_event_row(scenario["tenant_id"], scenario["deal_id"], "meta")
    assert row is not None
    status, attempts, last_error = row
    assert status == "failed"
    assert attempts == 3
    assert last_error


async def test_no_active_connection_records_failed_without_retry(scenario):
    # No lead_source_connections row for "google" at all.
    await _send_conversion_event(scenario["tenant_id"], uuid.UUID(scenario["deal_id"]), "google")

    row = _conversion_event_row(scenario["tenant_id"], scenario["deal_id"], "google")
    assert row is not None
    status, attempts, last_error = row
    assert status == "failed"
    assert attempts == 1  # no retry for a static missing-config state
    assert "no active connection" in last_error


async def test_duplicate_send_for_already_sent_pair_is_a_noop(scenario):
    _connect_meta(scenario["tenant_id"])
    deal_id = uuid.UUID(scenario["deal_id"])

    await _send_conversion_event(scenario["tenant_id"], deal_id, "meta")
    first_row = _conversion_event_row(scenario["tenant_id"], scenario["deal_id"], "meta")

    await _send_conversion_event(scenario["tenant_id"], deal_id, "meta")
    second_row = _conversion_event_row(scenario["tenant_id"], scenario["deal_id"], "meta")

    assert first_row == second_row  # unchanged — _already_sent short-circuited


async def test_tenant_b_deal_never_uses_tenant_a_connection(scenario):
    """Multi-tenancy check — PHASE_4B_CONVERSIONS_PLAN.md §8. Tenant A
    has a configured meta connection; tenant B does not. A (buggy or
    malicious) call for tenant B's own deal must still fail as
    'unconfigured' rather than somehow finding tenant A's connection."""
    _connect_meta(scenario["tenant_id"])

    other_tenant_id = uuid.uuid4()
    other_course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (other_course_id, other_tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")
    try:
        with TestClient(app) as client:
            other_contact = client.post(
                "/api/v1/contacts",
                json={"full_name": "Other Tenant Contact", "lead_source": "meta"},
                headers=_counselor_headers(other_tenant_id),
            ).json()["data"]
            other_deal = client.post(
                f"/api/v1/contacts/{other_contact['id']}/deals",
                json={"course_id": str(other_course_id)},
                headers=_counselor_headers(other_tenant_id),
            ).json()["data"]

        await _send_conversion_event(other_tenant_id, uuid.UUID(other_deal["id"]), "meta")

        row = _conversion_event_row(other_tenant_id, other_deal["id"], "meta")
        assert row is not None
        status, _, last_error = row
        assert status == "failed"
        assert "no active connection" in last_error
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            tables = (
                "conversion_events",
                "deals",
                "contacts",
                "courses",
                "pipeline_stages",
                "users",
            )
            for table in tables:
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
