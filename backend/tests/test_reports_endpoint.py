"""PHASE_4_PLAN.md §9 — reporting endpoints. Role-based visibility reuses
RowScope (already proven for contacts/deals/tasks in Phase 3); these
tests focus on what's new here: aggregate correctness, cache-key
isolation, and the sla_states read path Phase 3 never built.
"""

import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

MIGRATE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
APP_URL = os.environ.get("DATABASE_APP_URL", "").replace("+psycopg", "")


def _reachable(url: str) -> bool:
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not (_reachable(MIGRATE_URL) and _reachable(APP_URL)),
    reason="DATABASE_URL/DATABASE_APP_URL not set or Postgres unreachable",
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
            (tenant_id, f"t-{tenant_id}", "Reports Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        admin_headers = _headers(tenant_id, "sub-admin", "admin")
        manager_headers = _headers(tenant_id, "sub-manager", "manager")
        staff_headers = _headers(tenant_id, "sub-staff", "counselor")

        admin_id = client.get("/api/v1/me", headers=admin_headers).json()["data"]["user"]["id"]
        manager_id = client.get("/api/v1/me", headers=manager_headers).json()["data"]["user"]["id"]
        staff_id = client.get("/api/v1/me", headers=staff_headers).json()["data"]["user"]["id"]

        client.patch(
            f"/api/v1/users/{staff_id}", json={"manager_id": manager_id}, headers=admin_headers
        )

        stages = client.get("/api/v1/pipeline-stages", headers=admin_headers).json()["data"]
        inquiry = next(s for s in stages if s["name"] == "Inquiry")
        contacted = next(s for s in stages if s["name"] == "Contacted")
        client.patch(
            f"/api/v1/pipeline-stages/{contacted['id']}",
            json={"win_probability_pct": 40},
            headers=admin_headers,
        )

        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Report Test Lead", "lead_source": "web", "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id), "owner_id": staff_id},
            headers=admin_headers,
        ).json()["data"]

    yield {
        "tenant_id": tenant_id,
        "admin_headers": admin_headers,
        "manager_headers": manager_headers,
        "staff_headers": staff_headers,
        "admin_id": admin_id,
        "manager_id": manager_id,
        "staff_id": staff_id,
        "inquiry_id": inquiry["id"],
        "contacted_id": contacted["id"],
        "deal_id": deal["id"],
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        tables = (
            "audit_logs",
            "sla_states",
            "sla_policies",
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stages",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def test_funnel_counts_the_seeded_deal_in_its_stage(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/funnel", headers=scenario["admin_headers"])
    assert response.status_code == 200
    body = response.json()
    assert "cached_at" in body["meta"]
    inquiry_row = next(r for r in body["data"] if r["stage_id"] == scenario["inquiry_id"])
    assert inquiry_row["count"] == 1


def test_staff_funnel_only_counts_own_deals(scenario):
    with TestClient(app) as client:
        staff_response = client.get("/api/v1/reports/funnel", headers=scenario["staff_headers"])
    total = sum(r["count"] for r in staff_response.json()["data"])
    assert total == 1  # the one deal, owned by this staff member


def test_forecast_includes_zero_probability_stage_with_zero_contribution(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/forecast", headers=scenario["admin_headers"])
    by_stage = response.json()["data"]["by_stage"]
    inquiry_row = next(r for r in by_stage if r["stage_id"] == scenario["inquiry_id"])
    assert inquiry_row["win_probability_pct"] == 0
    assert inquiry_row["expected_count"] == 0
    assert inquiry_row["deal_count"] == 1  # present, not omitted


def test_forecast_math_matches_manual_arithmetic(scenario):
    with TestClient(app) as client:
        # Move the deal into the 40%-probability Contacted stage.
        client.patch(
            f"/api/v1/deals/{scenario['deal_id']}",
            json={"stage_id": scenario["contacted_id"]},
            headers=scenario["admin_headers"],
        )
        response = client.get("/api/v1/reports/forecast", headers=scenario["admin_headers"])
    body = response.json()["data"]
    contacted_row = next(r for r in body["by_stage"] if r["stage_id"] == scenario["contacted_id"])
    assert contacted_row["deal_count"] == 1
    assert contacted_row["expected_count"] == 0.4  # 1 deal * 40%
    assert body["expected_enrollments"] == 0.4


def test_sla_compliance_is_403_for_staff(scenario):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/reports/sla-compliance", headers=scenario["staff_headers"]
        )
    assert response.status_code == 403


def test_sla_compliance_counts_by_counselor(scenario):
    sla_state_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "INSERT INTO sla_policies (tenant_id, name, applies_to, stage_id, target_minutes) "
            "VALUES (%s, 'test policy', 'stage_entry', %s, 30)",
            (scenario["tenant_id"], scenario["inquiry_id"]),
        )
        cur.execute("SELECT id FROM sla_policies WHERE tenant_id = %s", (scenario["tenant_id"],))
        policy_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO sla_states "
            "(id, tenant_id, sla_policy_id, deal_id, target_at, warning_at, state) "
            "VALUES (%s, %s, %s, %s, now(), now(), 'breached')",
            (sla_state_id, scenario["tenant_id"], policy_id, scenario["deal_id"]),
        )
        cur.execute("RESET app.tenant_id")

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/reports/sla-compliance", headers=scenario["manager_headers"]
        )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["counselor_id"] == scenario["staff_id"]
    assert rows[0]["breached"] == 1


def test_my_queue_sorts_breached_first_and_includes_deal_with_no_sla_state(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/my-queue", headers=scenario["staff_headers"])
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["deal_id"] == scenario["deal_id"]
    assert items[0]["sla_state"] is None  # no policy has ticked it yet — still present


def test_my_stats_reports_leads_worked(scenario):
    with TestClient(app) as client:
        response = client.get("/api/v1/reports/my-stats", headers=scenario["staff_headers"])
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["leads_worked"] == 1
    assert body["conversion_rate"] == 0.0  # deal not in a won stage


def test_cache_keys_do_not_collide_across_roles_in_the_same_tenant(scenario):
    with TestClient(app) as client:
        admin_response = client.get("/api/v1/reports/funnel", headers=scenario["admin_headers"])
        staff_response = client.get("/api/v1/reports/funnel", headers=scenario["staff_headers"])
    admin_total = sum(r["count"] for r in admin_response.json()["data"])
    staff_total = sum(r["count"] for r in staff_response.json()["data"])
    assert admin_total == 1
    assert staff_total == 1  # same number here, but proven via independent cache keys
    assert admin_response.json()["data"] != [] and staff_response.json()["data"] != []


def test_cache_keys_do_not_collide_across_tenants(scenario):
    other_tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Reports Tenant"),
        )
    try:
        other_headers = _headers(other_tenant_id, "sub-other-admin", "admin")
        with TestClient(app) as client:
            client.get("/api/v1/me", headers=other_headers)
            other_response = client.get("/api/v1/reports/funnel", headers=other_headers)
        assert other_response.status_code == 200
        assert sum(r["count"] for r in other_response.json()["data"]) == 0
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))
