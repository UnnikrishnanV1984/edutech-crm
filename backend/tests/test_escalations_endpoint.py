"""PHASE_3_PLAN.md §5/§10 acceptance criterion 5 — escalation lifecycle."""

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


def _headers(tenant_id, sub, role) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": sub,
        "X-User-Email": f"{sub}@example.test",
        "X-User-Role": role,
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Escalation Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        staff_headers = _headers(tenant_id, "sub-staff", "counselor")
        other_manager_headers = _headers(tenant_id, "sub-other-manager", "manager")
        admin_headers = _headers(tenant_id, "sub-admin", "admin")

        manager_id = client.get("/api/v1/me", headers=manager_headers).json()["data"]["user"]["id"]
        staff_id = client.get("/api/v1/me", headers=staff_headers).json()["data"]["user"]["id"]
        other_manager_id = client.get("/api/v1/me", headers=other_manager_headers).json()["data"][
            "user"
        ]["id"]
        client.get("/api/v1/me", headers=admin_headers)

        client.patch(
            f"/api/v1/users/{staff_id}", json={"manager_id": manager_id}, headers=admin_headers
        )

        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Escalation Contact", "lead_source": "web", "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]
        deal_id = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id), "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]["id"]

    yield {
        "tenant_id": tenant_id,
        "manager_headers": manager_headers,
        "staff_headers": staff_headers,
        "other_manager_headers": other_manager_headers,
        "other_manager_id": other_manager_id,
        "admin_headers": admin_headers,
        "deal_id": deal_id,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        tables = (
            "audit_logs",
            "escalations",
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _raise(client, headers, deal_id, **overrides) -> dict:
    body = {"deal_id": deal_id, "reason": "stuck"}
    body.update(overrides)
    return client.post("/api/v1/escalations", json=body, headers=headers).json()["data"]


def test_staff_can_raise_escalation_to_their_manager(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
    assert escalation["source"] == "manual"
    assert escalation["status"] == "open"


def test_staff_with_no_manager_gets_409(scenario):
    tenant_id = scenario["tenant_id"]
    orphan_headers = _headers(tenant_id, "sub-orphan-staff", "counselor")
    with TestClient(app) as client:
        client.get("/api/v1/me", headers=orphan_headers)
        response = client.post(
            "/api/v1/escalations",
            json={"deal_id": scenario["deal_id"], "reason": "stuck"},
            headers=orphan_headers,
        )
    assert response.status_code == 409


def test_raise_against_unknown_deal_is_404(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/escalations",
            json={"deal_id": str(uuid.uuid4()), "reason": "stuck"},
            headers=scenario["staff_headers"],
        )
    assert response.status_code == 404


def test_manager_sees_escalation_assigned_to_them(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/escalations", headers=scenario["manager_headers"])
    assert len(response.json()["data"]) == 1


def test_unrelated_manager_does_not_see_it(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/escalations", headers=scenario["other_manager_headers"])
    assert response.json()["data"] == []


def test_list_is_enriched_with_contact_name(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/escalations", headers=scenario["manager_headers"])
    row = response.json()["data"][0]
    assert row["contact_name"] == "Escalation Contact"
    assert row["assigned_to_name"] is not None


def test_status_filter(scenario):
    with TestClient(app) as client:
        first = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        client.patch(
            f"/api/v1/escalations/{first['id']}",
            json={"status": "resolved"},
            headers=scenario["manager_headers"],
        )
        _raise(client, scenario["staff_headers"], scenario["deal_id"], reason="stuck again")

        open_response = client.get(
            "/api/v1/escalations", params={"status": "open"}, headers=scenario["manager_headers"]
        )
        resolved_response = client.get(
            "/api/v1/escalations",
            params={"status": "resolved"},
            headers=scenario["manager_headers"],
        )
    assert len(open_response.json()["data"]) == 1
    assert len(resolved_response.json()["data"]) == 1
    assert open_response.json()["data"][0]["status"] == "open"
    assert resolved_response.json()["data"][0]["status"] == "resolved"


def test_unknown_status_filter_is_rejected(scenario):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/escalations", params={"status": "bogus"}, headers=scenario["manager_headers"]
        )
    assert response.status_code == 400


def test_open_to_resolved_directly_succeeds_and_backfills_acknowledged_at(scenario):
    # REQUIREMENTS.md §4.2: manager resolution should be a single action —
    # OPENFUNNEL_REBRAND_PLAN.md Phase 7e's resolve drawer relies on this.
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved", "resolution_note": "handled directly"},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "resolved"
    assert data["acknowledged_at"] is not None
    assert data["resolved_at"] is not None


def test_resolved_is_terminal(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved"},
            headers=scenario["manager_headers"],
        )
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 400


def test_snooze_requires_snoozed_until(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "snoozed"},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 400


def test_snooze_sets_status_and_snoozed_until(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "snoozed", "snoozed_until": "2099-01-01T00:00:00Z"},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "snoozed"
    assert data["snoozed_until"] is not None


def test_reassign_records_resolution_note(scenario):
    """Regression test — resolution_note used to be silently dropped on a
    reassign-only PATCH (it was nested under `if status is not None`)."""
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={
                "reassign_to": scenario["other_manager_id"],
                "resolution_note": "passing to someone else",
            },
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_note"] == "passing to someone else"
    assert data["was_reopened"] is True
    assert data["status"] == "open"


def test_open_then_acknowledged_then_resolved_succeeds(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        ack = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["manager_headers"],
        )
        resolved = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "resolved", "resolution_note": "sorted"},
            headers=scenario["manager_headers"],
        )
    assert ack.status_code == 200
    assert ack.json()["data"]["status"] == "acknowledged"
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"


def test_staff_cannot_acknowledge(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["staff_headers"],
        )
    assert response.status_code == 403


def test_unrelated_manager_cannot_act_on_it(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"status": "acknowledged"},
            headers=scenario["other_manager_headers"],
        )
    assert response.status_code == 403


def test_summary_open_count(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get("/api/v1/reports/escalations", headers=scenario["manager_headers"])
    assert response.status_code == 200
    assert response.json()["data"]["open"] == 1


def test_summary_scoped_to_assignee_not_visible_to_unrelated_manager(scenario):
    with TestClient(app) as client:
        _raise(client, scenario["staff_headers"], scenario["deal_id"])
        response = client.get(
            "/api/v1/reports/escalations", headers=scenario["other_manager_headers"]
        )
    assert response.json()["data"]["open"] == 0


def test_summary_reopened_counts_a_reassigned_open_escalation(scenario):
    with TestClient(app) as client:
        escalation = _raise(client, scenario["staff_headers"], scenario["deal_id"])
        client.patch(
            f"/api/v1/escalations/{escalation['id']}",
            json={"reassign_to": scenario["other_manager_id"]},
            headers=scenario["manager_headers"],
        )
        response = client.get(
            "/api/v1/reports/escalations", headers=scenario["other_manager_headers"]
        )
    assert response.json()["data"]["reopened"] == 1


def test_summary_avg_resolve_minutes_is_zero_with_no_resolved_escalations(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/escalations", headers=scenario["manager_headers"])
    assert response.json()["data"]["avg_resolve_minutes"] == 0.0


def test_summary_is_403_for_staff(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/escalations", headers=scenario["staff_headers"])
    assert response.status_code == 403
