import os
import uuid
from datetime import date, timedelta

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
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Follow-up Flag Test Tenant"),
        )

    with TestClient(app) as client:
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        other_manager_headers = _headers(tenant_id, "sub-other-manager", "manager")
        staff_headers = _headers(tenant_id, "sub-staff", "counselor")
        admin_headers = _headers(tenant_id, "sub-admin", "admin")

        contact_id = client.post(
            "/api/v1/contacts",
            json={"full_name": "Follow-up Contact", "lead_source": "web"},
            headers=manager_headers,
        ).json()["data"]["id"]

    yield {
        "tenant_id": tenant_id,
        "manager_headers": manager_headers,
        "other_manager_headers": other_manager_headers,
        "staff_headers": staff_headers,
        "admin_headers": admin_headers,
        "contact_id": contact_id,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("follow_up_flags", "contacts", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_staff_cannot_create_flags(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["staff_headers"],
        )
    assert response.status_code == 403


def test_manager_creates_and_lists_own_flag(scenario):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        listed = client.get("/api/v1/follow-up-flags", headers=scenario["manager_headers"])
    assert created.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_other_manager_does_not_see_it(scenario):
    with TestClient(app) as client:
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        listed = client.get(
            "/api/v1/follow-up-flags", headers=scenario["other_manager_headers"]
        )
    assert listed.json()["data"] == []


def test_admin_sees_all_flags(scenario):
    with TestClient(app) as client:
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        listed = client.get("/api/v1/follow-up-flags", headers=scenario["admin_headers"])
    assert len(listed.json()["data"]) == 1


def test_contact_id_filter_scopes_to_one_contact(scenario):
    with TestClient(app) as client:
        other_contact_id = client.post(
            "/api/v1/contacts",
            json={"full_name": "Other Contact", "lead_source": "web"},
            headers=scenario["manager_headers"],
        ).json()["data"]["id"]
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": other_contact_id,
                "note": "check in on the other one",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        scoped = client.get(
            f"/api/v1/follow-up-flags?contact_id={scenario['contact_id']}",
            headers=scenario["manager_headers"],
        )
    assert scoped.status_code == 200
    assert len(scoped.json()["data"]) == 1
    assert scoped.json()["data"][0]["contact_id"] == scenario["contact_id"]


def test_resolve_flag(scenario):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        ).json()["data"]
        response = client.patch(
            f"/api/v1/follow-up-flags/{created['id']}", headers=scenario["manager_headers"]
        )
    assert response.status_code == 200
    assert response.json()["data"]["resolved_at"] is not None


def test_list_is_enriched_with_contact_and_manager_name(scenario):
    with TestClient(app) as client:
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        listed = client.get("/api/v1/follow-up-flags", headers=scenario["manager_headers"])
    row = listed.json()["data"][0]
    assert row["contact_name"] == "Follow-up Contact"
    assert row["resolved_contact_id"] == scenario["contact_id"]
    assert row["manager_name"] is not None


def test_admin_can_filter_by_manager_id(scenario):
    with TestClient(app) as client:
        client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        )
        manager_id = client.get("/api/v1/me", headers=scenario["manager_headers"]).json()["data"][
            "user"
        ]["id"]
        other_manager_id = client.get(
            "/api/v1/me", headers=scenario["other_manager_headers"]
        ).json()["data"]["user"]["id"]

        scoped_to_manager = client.get(
            "/api/v1/follow-up-flags",
            params={"manager_id": manager_id},
            headers=scenario["admin_headers"],
        )
        scoped_to_other = client.get(
            "/api/v1/follow-up-flags",
            params={"manager_id": other_manager_id},
            headers=scenario["admin_headers"],
        )
    assert len(scoped_to_manager.json()["data"]) == 1
    assert scoped_to_other.json()["data"] == []


def test_manager_cannot_widen_scope_via_manager_id_param(scenario):
    """REQUIREMENTS.md §4.3 — a manager's flag list is strictly their own;
    manager_id is only ever honored for an Admin caller. Passing another
    manager's id neither reveals that manager's flags nor hides the
    caller's own — it's silently ignored, same as every other
    role-scoped endpoint in this app."""
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=7)),
            },
            headers=scenario["manager_headers"],
        ).json()["data"]
        other_manager_id = client.get(
            "/api/v1/me", headers=scenario["other_manager_headers"]
        ).json()["data"]["user"]["id"]
        response = client.get(
            "/api/v1/follow-up-flags",
            params={"manager_id": other_manager_id},
            headers=scenario["manager_headers"],
        )
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == created["id"]


def test_snooze_moves_remind_on_without_resolving(scenario):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=1)),
            },
            headers=scenario["manager_headers"],
        ).json()["data"]
        new_date = str(date.today() + timedelta(days=14))
        response = client.patch(
            f"/api/v1/follow-up-flags/{created['id']}",
            json={"remind_on": new_date},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["remind_on"] == new_date
    assert data["resolved_at"] is None


def test_snooze_rejects_a_past_date(scenario):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=1)),
            },
            headers=scenario["manager_headers"],
        ).json()["data"]
        response = client.patch(
            f"/api/v1/follow-up-flags/{created['id']}",
            json={"remind_on": str(date.today() - timedelta(days=1))},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 400


def test_cannot_snooze_a_resolved_flag(scenario):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/follow-up-flags",
            json={
                "contact_id": scenario["contact_id"],
                "note": "check in",
                "remind_on": str(date.today() + timedelta(days=1)),
            },
            headers=scenario["manager_headers"],
        ).json()["data"]
        client.patch(
            f"/api/v1/follow-up-flags/{created['id']}", headers=scenario["manager_headers"]
        )
        response = client.patch(
            f"/api/v1/follow-up-flags/{created['id']}",
            json={"remind_on": str(date.today() + timedelta(days=14))},
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 400
