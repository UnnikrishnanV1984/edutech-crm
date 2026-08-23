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


def _headers(tenant_id) -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": "sub-activity-test",
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    yield {"tenant_id": tenant_id, "course_id": course_id}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM activities WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM deals WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM contacts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM courses WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_stage_change_writes_exactly_one_activity(scenario):
    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Alice", "lead_source": "web"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        contacted_id = next(s["id"] for s in stages if s["name"] == "Contacted")

        client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"stage_id": contacted_id},
            headers=_headers(scenario["tenant_id"]),
        )

        activities = client.get(
            f"/api/v1/contacts/{contact['id']}/activities", headers=_headers(scenario["tenant_id"])
        )

    assert activities.status_code == 200
    items = activities.json()["data"]
    assert len(items) == 1
    assert items[0]["type"] == "deal_stage_changed"
    assert items[0]["deal_id"] == deal["id"]
    assert items[0]["payload"]["old_stage_id"] == deal["stage_id"]
    assert items[0]["payload"]["new_stage_id"] == contacted_id


def test_patching_deal_without_stage_change_writes_no_activity(scenario):
    with TestClient(app) as client:
        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Bob", "lead_source": "web"},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]

        # Re-set the same stage_id — no actual transition.
        client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"stage_id": deal["stage_id"]},
            headers=_headers(scenario["tenant_id"]),
        )

        activities = client.get(
            f"/api/v1/contacts/{contact['id']}/activities", headers=_headers(scenario["tenant_id"])
        )
    assert activities.json()["data"] == []


def test_activities_endpoint_for_unknown_contact_returns_404(scenario):
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/contacts/{uuid.uuid4()}/activities", headers=_headers(scenario["tenant_id"])
        )
    assert response.status_code == 404
