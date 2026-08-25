"""PHASE_3_PLAN.md §7.3/§10 acceptance criterion 7 — manager-proposed
rules are always forced to pending_approval."""

import os
import uuid
from datetime import UTC, datetime, timedelta

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
def tenant():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Workflow Rules Test Tenant"),
        )
    yield tenant_id
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in ("workflow_rules", "users"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


_ACTIONS = [{"type": "notify_manager", "config": {}}]


def test_staff_cannot_see_or_create_rules(tenant):
    with TestClient(app) as client:
        get_response = client.get(
            "/api/v1/workflow-rules", headers=_headers(tenant, "sub-staff", "counselor")
        )
        post_response = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-staff", "counselor"),
        )
    assert get_response.status_code == 403
    assert post_response.status_code == 403


def test_manager_created_rule_is_forced_pending_approval(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Auto-assign new leads",
                "trigger_type": "lead_created",
                "actions": _ACTIONS,
                "status": "active",  # deliberately claims active — must be overridden
            },
            headers=_headers(tenant, "sub-manager", "manager"),
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending_approval"


def test_admin_created_rule_honors_requested_status(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Auto-assign new leads",
                "trigger_type": "lead_created",
                "actions": _ACTIONS,
                "status": "active",
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_manager_cannot_approve_own_rule(tenant):
    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager", "manager"),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/workflow-rules/{rule['id']}",
            json={"status": "active"},
            headers=_headers(tenant, "sub-manager", "manager"),
        )
    assert response.status_code == 403


def test_admin_approves_pending_rule(tenant):
    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/workflow-rules",
            json={"name": "x", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager", "manager"),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/workflow-rules/{rule['id']}",
            json={"status": "active"},
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "active"
    assert body["approved_by"] is not None


def test_manager_sees_own_proposal_but_not_other_managers_draft(tenant):
    with TestClient(app) as client:
        client.post(
            "/api/v1/workflow-rules",
            json={"name": "mine", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager-a", "manager"),
        )
        client.post(
            "/api/v1/workflow-rules",
            json={"name": "theirs", "trigger_type": "lead_created", "actions": _ACTIONS},
            headers=_headers(tenant, "sub-manager-b", "manager"),
        )
        listed = client.get(
            "/api/v1/workflow-rules", headers=_headers(tenant, "sub-manager-a", "manager")
        )
    names = {r["name"] for r in listed.json()["data"]}
    assert names == {"mine"}


def test_invalid_action_type_is_rejected(tenant):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "x",
                "trigger_type": "lead_created",
                "actions": [{"type": "not_a_real_action"}],
            },
            headers=_headers(tenant, "sub-admin", "admin"),
        )
    assert response.status_code == 400


@pytest.fixture
def scenario():
    """Richer fixture for run-history/test-run — a real contact + deal to
    evaluate conditions against, distinct from the bare `tenant` fixture
    the rest of this file uses."""
    tenant_id = uuid.uuid4()
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Workflow Rules Run History Test Tenant"),
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
        client.get("/api/v1/me", headers=admin_headers)
        client.get("/api/v1/me", headers=manager_headers)

        contact = client.post(
            "/api/v1/contacts",
            json={"full_name": "Rule Test Contact", "lead_source": "web"},
            headers=admin_headers,
        ).json()["data"]
        deal = client.post(
            f"/api/v1/contacts/{contact['id']}/deals",
            json={"course_id": str(course_id)},
            headers=admin_headers,
        ).json()["data"]

    yield {
        "tenant_id": tenant_id,
        "admin_headers": admin_headers,
        "manager_headers": manager_headers,
        "contact_id": contact["id"],
        "deal_id": deal["id"],
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "workflow_runs",
            "workflow_rules",
            "activities",
            "deals",
            "contacts",
            "courses",
            "pipeline_stage_default_snapshots",
            "pipeline_stages",
            "users",
        ):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _insert_run(tenant_id, rule_id, source_type, source_id, status, executed_at) -> None:
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO workflow_runs "
            "(id, tenant_id, workflow_rule_id, trigger_source_type, trigger_source_id, "
            "status, attempt, executed_at) VALUES (%s, %s, %s, %s, %s, %s, 1, %s)",
            (uuid.uuid4(), tenant_id, rule_id, source_type, source_id, status, executed_at),
        )
        cur.execute("RESET app.tenant_id")


def test_run_history_lists_runs_newest_first_with_rule_name(scenario):
    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Notify on stage change",
                "trigger_type": "stage_changed",
                "actions": _ACTIONS,
            },
            headers=scenario["admin_headers"],
        ).json()["data"]
        now = datetime.now(UTC)
        _insert_run(scenario["tenant_id"], rule["id"], "deal", scenario["deal_id"], "success", now)
        _insert_run(
            scenario["tenant_id"],
            rule["id"],
            "deal",
            scenario["deal_id"],
            "failed",
            now - timedelta(minutes=5),
        )
        response = client.get("/api/v1/workflow-rules/runs", headers=scenario["admin_headers"])
    body = response.json()
    assert response.status_code == 200
    assert body["meta"]["total"] == 2
    assert [r["status"] for r in body["data"]] == ["success", "failed"]
    assert all(r["rule_name"] == "Notify on stage change" for r in body["data"])


def test_run_history_filters_by_rule_id(scenario):
    with TestClient(app) as client:
        rule_a = client.post(
            "/api/v1/workflow-rules",
            json={"name": "Rule A", "trigger_type": "stage_changed", "actions": _ACTIONS},
            headers=scenario["admin_headers"],
        ).json()["data"]
        rule_b = client.post(
            "/api/v1/workflow-rules",
            json={"name": "Rule B", "trigger_type": "stage_changed", "actions": _ACTIONS},
            headers=scenario["admin_headers"],
        ).json()["data"]
        now = datetime.now(UTC)
        _insert_run(
            scenario["tenant_id"], rule_a["id"], "deal", scenario["deal_id"], "success", now
        )
        _insert_run(
            scenario["tenant_id"], rule_b["id"], "deal", scenario["deal_id"], "success", now
        )
        response = client.get(
            "/api/v1/workflow-rules/runs",
            params={"rule_id": rule_a["id"]},
            headers=scenario["admin_headers"],
        )
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["rule_name"] == "Rule A"


def test_run_history_hides_other_managers_draft_rule_runs(scenario):
    with TestClient(app) as client:
        other_manager_headers = _headers(scenario["tenant_id"], "sub-other-manager", "manager")
        client.get("/api/v1/me", headers=other_manager_headers)
        draft_rule = client.post(
            "/api/v1/workflow-rules",
            json={
                "name": "Someone else's draft",
                "trigger_type": "stage_changed",
                "actions": _ACTIONS,
            },
            headers=other_manager_headers,
        ).json()["data"]
        _insert_run(
            scenario["tenant_id"],
            draft_rule["id"],
            "deal",
            scenario["deal_id"],
            "success",
            datetime.now(UTC),
        )
        response = client.get(
            "/api/v1/workflow-rules/runs", headers=scenario["manager_headers"]
        )
    assert response.json()["data"] == []


def test_test_run_matches_a_contact_by_lead_source(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules/test-run",
            json={
                "trigger_type": "lead_created",
                "conditions": [{"field": "lead_source", "op": "eq", "value": "web"}],
            },
            headers=scenario["admin_headers"],
        )
    body = response.json()["data"]
    assert response.status_code == 200
    assert body["candidates_checked"] >= 1
    matched_ids = {m["id"] for m in body["matched"]}
    assert scenario["contact_id"] in matched_ids


def test_test_run_excludes_non_matching_contact(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules/test-run",
            json={
                "trigger_type": "lead_created",
                "conditions": [{"field": "lead_source", "op": "eq", "value": "whatsapp"}],
            },
            headers=scenario["admin_headers"],
        )
    body = response.json()["data"]
    matched_ids = {m["id"] for m in body["matched"]}
    assert scenario["contact_id"] not in matched_ids


def test_test_run_does_not_create_a_workflow_run_row(scenario):
    """Genuinely read-only — a dry run must never write to workflow_runs."""
    with TestClient(app) as client:
        client.post(
            "/api/v1/workflow-rules/test-run",
            json={"trigger_type": "lead_created", "conditions": []},
            headers=scenario["admin_headers"],
        )
        history = client.get("/api/v1/workflow-rules/runs", headers=scenario["admin_headers"])
    assert history.json()["data"] == []


def test_test_run_rejects_unknown_trigger_type(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules/test-run",
            json={"trigger_type": "not_a_real_trigger", "conditions": []},
            headers=scenario["admin_headers"],
        )
    assert response.status_code == 400


def test_manager_can_test_run_without_saving_a_rule(scenario):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow-rules/test-run",
            json={
                "trigger_type": "lead_created",
                "conditions": [{"field": "lead_source", "op": "eq", "value": "web"}],
            },
            headers=scenario["manager_headers"],
        )
    assert response.status_code == 200
