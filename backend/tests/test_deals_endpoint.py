import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workers import conversions

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


def _headers(tenant_id, user_sub="sub-deal-test") -> dict:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": user_sub,
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

    with TestClient(app) as client:
        contact_resp = client.post(
            "/api/v1/contacts",
            json={"full_name": "Deal Contact", "lead_source": "web"},
            headers=_headers(tenant_id),
        )
    contact_id = contact_resp.json()["data"]["id"]

    yield {"tenant_id": tenant_id, "course_id": course_id, "contact_id": contact_id}

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


def test_create_deal_defaults_to_first_open_stage(scenario):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        )
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["contact_id"] == scenario["contact_id"]
    assert body["stage_id"] == stages[0]["id"]  # "Inquiry"


def test_create_deal_for_unknown_contact_returns_404(scenario):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/contacts/{uuid.uuid4()}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 404


def test_create_deal_with_unknown_course_returns_400(scenario):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(uuid.uuid4())},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_deal_stage_updates_stage_changed_at(scenario):
    with TestClient(app) as client:
        deal = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        contacted_stage_id = next(s["id"] for s in stages if s["name"] == "Contacted")

        response = client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"stage_id": contacted_stage_id},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["stage_id"] == contacted_stage_id
    assert updated["stage_changed_at"] > deal["stage_changed_at"]


def test_stage_change_to_non_won_stage_does_not_enqueue_conversion_send(scenario, monkeypatch):
    """ARCHITECTURE.md §7d — only an is_won transition should enqueue."""
    calls = []
    monkeypatch.setattr(
        conversions.send_conversion_event, "delay", lambda *a, **k: calls.append((a, k))
    )
    with TestClient(app) as client:
        deal = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        contacted_stage_id = next(s["id"] for s in stages if s["name"] == "Contacted")

        response = client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"stage_id": contacted_stage_id},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 200
    assert calls == []


def test_stage_change_to_won_stage_enqueues_conversion_send_for_both_platforms(
    scenario, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        conversions.send_conversion_event, "delay", lambda *a, **k: calls.append(a)
    )
    with TestClient(app) as client:
        deal = client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        ).json()["data"]
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        enrolled_stage_id = next(s["id"] for s in stages if s["name"] == "Enrolled")

        response = client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"stage_id": enrolled_stage_id},
            headers=_headers(scenario["tenant_id"]),
        )
    assert response.status_code == 200
    platforms = {call[2] for call in calls}
    assert platforms == {"meta", "google"}
    assert all(call[0] == str(scenario["tenant_id"]) for call in calls)
    assert all(call[1] == deal["id"] for call in calls)


def test_list_deals_filters_by_stage(scenario):
    with TestClient(app) as client:
        client.post(
            f"/api/v1/contacts/{scenario['contact_id']}/deals",
            json={"course_id": str(scenario["course_id"])},
            headers=_headers(scenario["tenant_id"]),
        )
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(scenario["tenant_id"])
        ).json()["data"]
        inquiry_id = stages[0]["id"]
        contacted_id = stages[1]["id"]

        by_inquiry = client.get(
            f"/api/v1/deals?stage_id={inquiry_id}", headers=_headers(scenario["tenant_id"])
        )
        by_contacted = client.get(
            f"/api/v1/deals?stage_id={contacted_id}", headers=_headers(scenario["tenant_id"])
        )
    assert by_inquiry.json()["meta"]["total"] == 1
    assert by_contacted.json()["meta"]["total"] == 0
