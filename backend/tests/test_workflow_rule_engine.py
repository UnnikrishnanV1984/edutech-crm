"""app/workers/rules.py — PHASE_3_PLAN.md §7/§10 acceptance criteria
6-9. Calls _run_one_rule/_evaluate_event_rules directly (async), not the
Celery task wrappers, matching this repo's existing convention for
testing async worker logic without a running Celery worker.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from app.workers.rules import _evaluate_event_rules, _run_one_rule, _scan_time_based_rules

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


@dataclass
class _Rule:
    """Matches the attributes _run_one_rule reads off a WorkflowRule ORM
    row. workflow_runs.workflow_rule_id is a real composite FK into
    workflow_rules (PHASE_3_PLAN.md §3.8's "no technical obstacle"
    exception), so every rule used here must actually exist in the DB —
    _make_rule below inserts it, this dataclass just carries the id back."""

    id: uuid.UUID
    actions: list[dict[str, Any]]
    conditions: list[dict[str, Any]] = field(default_factory=list)
    created_by: uuid.UUID | None = None


def _make_rule(
    tenant_id,
    created_by,
    actions,
    conditions=None,
    trigger_type="lead_created",
    status="active",
) -> _Rule:
    rule_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO workflow_rules "
            "(id, tenant_id, name, trigger_type, actions, conditions, status, created_by) "
            "VALUES (%s, %s, 'test rule', %s, %s::jsonb, %s::jsonb, %s, %s)",
            (
                rule_id,
                tenant_id,
                trigger_type,
                json.dumps(actions),
                json.dumps(conditions or []),
                status,
                created_by,
            ),
        )
        cur.execute("RESET app.tenant_id")
    return _Rule(id=rule_id, actions=actions, conditions=conditions or [], created_by=created_by)


@pytest.fixture
def scenario():
    tenant_id = uuid.uuid4()
    manager_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    course_id = uuid.uuid4()
    stage1_id = uuid.uuid4()
    stage2_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    deal_id = uuid.uuid4()

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Workflow Engine Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (%s, %s, %s, %s, 'manager')",
            (manager_id, tenant_id, f"sub-{manager_id}", "manager@example.test"),
        )
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role, manager_id) "
            "VALUES (%s, %s, %s, %s, 'counselor', %s)",
            (staff_id, tenant_id, f"sub-{staff_id}", "staff@example.test", manager_id),
        )
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, tenant_id, "BSc CS", "CS101"),
        )
        cur.execute(
            "INSERT INTO pipeline_stages (id, tenant_id, name, sort_order) VALUES "
            "(%s, %s, 'Inquiry', 1), (%s, %s, 'Contacted', 2)",
            (stage1_id, tenant_id, stage2_id, tenant_id),
        )
        cur.execute(
            "INSERT INTO contacts (id, tenant_id, full_name, lead_source, owner_id) "
            "VALUES (%s, %s, %s, 'web', %s)",
            (contact_id, tenant_id, "Engine Test Contact", staff_id),
        )
        cur.execute(
            "INSERT INTO deals (id, tenant_id, contact_id, course_id, stage_id, owner_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (deal_id, tenant_id, contact_id, course_id, stage1_id, staff_id),
        )
        cur.execute("RESET app.tenant_id")

    yield {
        "tenant_id": tenant_id,
        "manager_id": manager_id,
        "staff_id": staff_id,
        "contact_id": contact_id,
        "deal_id": deal_id,
        "stage1_id": stage1_id,
        "stage2_id": stage2_id,
    }

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        tables = (
            "escalations",
            "workflow_runs",
            "workflow_rules",
            "activities",
            "tasks",
            "deals",
            "contacts",
            "pipeline_stages",
            "courses",
            "users",
        )
        for table in tables:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _query(tenant_id, sql, params=()):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(sql, params)
        return cur.fetchall()


async def test_assign_round_robin_action(scenario):
    rule = _make_rule(
        scenario["tenant_id"], scenario["staff_id"], [{"type": "assign_round_robin"}]
    )
    await _run_one_rule(scenario["tenant_id"], rule, "contact", scenario["contact_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT owner_id FROM contacts WHERE id = %s",
        (scenario["contact_id"],),
    )
    assert str(rows[0][0]) == str(scenario["staff_id"])  # only counselor in this tenant


async def test_assign_by_territory_matches_contact_territory(scenario):
    # A second counselor in "north", distinct from the fixture's
    # untagged staff_id — the match must prefer them over falling back
    # to round-robin.
    north_counselor_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role, territory) "
            "VALUES (%s, %s, %s, %s, 'counselor', 'north')",
            (
                north_counselor_id,
                scenario["tenant_id"],
                f"sub-{north_counselor_id}",
                "north@example.test",
            ),
        )
        cur.execute(
            "UPDATE contacts SET territory = 'north' WHERE id = %s", (scenario["contact_id"],)
        )
        cur.execute("RESET app.tenant_id")

    rule = _make_rule(
        scenario["tenant_id"], scenario["staff_id"], [{"type": "assign_by_territory"}]
    )
    await _run_one_rule(scenario["tenant_id"], rule, "contact", scenario["contact_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT owner_id FROM contacts WHERE id = %s",
        (scenario["contact_id"],),
    )
    assert str(rows[0][0]) == str(north_counselor_id)


async def test_assign_by_territory_falls_back_to_round_robin_with_no_match(scenario):
    # Fixture's contact/staff have no territory set at all — the only
    # counselor in the tenant, reached via the round-robin fallback.
    rule = _make_rule(
        scenario["tenant_id"], scenario["staff_id"], [{"type": "assign_by_territory"}]
    )
    await _run_one_rule(scenario["tenant_id"], rule, "contact", scenario["contact_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT owner_id FROM contacts WHERE id = %s",
        (scenario["contact_id"],),
    )
    assert str(rows[0][0]) == str(scenario["staff_id"])


async def test_assign_by_territory_never_matches_another_tenants_counselor(scenario):
    other_tenant_id = uuid.uuid4()
    other_counselor_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (other_tenant_id, f"t-{other_tenant_id}", "Other Territory Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role, territory) "
            "VALUES (%s, %s, %s, %s, 'counselor', 'north')",
            (
                other_counselor_id,
                other_tenant_id,
                f"sub-{other_counselor_id}",
                "other-north@example.test",
            ),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "UPDATE contacts SET territory = 'north' WHERE id = %s", (scenario["contact_id"],)
        )
        cur.execute("RESET app.tenant_id")

    try:
        # No "north" counselor in scenario["tenant_id"] itself — must
        # fall back to round-robin within this tenant, never reach
        # across into other_tenant_id's matching counselor.
        rule = _make_rule(
            scenario["tenant_id"], scenario["staff_id"], [{"type": "assign_by_territory"}]
        )
        await _run_one_rule(scenario["tenant_id"], rule, "contact", scenario["contact_id"])
        rows = _query(
            scenario["tenant_id"],
            "SELECT owner_id FROM contacts WHERE id = %s",
            (scenario["contact_id"],),
        )
        assert str(rows[0][0]) == str(scenario["staff_id"])
        assert str(rows[0][0]) != str(other_counselor_id)
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(other_tenant_id),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (other_tenant_id,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant_id,))


async def test_create_task_action(scenario):
    rule = _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "create_task", "config": {"title": "Call the lead", "due_in_minutes": 30}}],
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"], "SELECT title, assignee_id FROM tasks WHERE contact_id = %s",
        (scenario["contact_id"],),
    )
    assert len(rows) == 1
    assert rows[0][0] == "Call the lead"
    assert str(rows[0][1]) == str(scenario["staff_id"])


async def test_change_stage_action(scenario):
    rule = _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "change_stage", "config": {"to_stage_id": str(scenario["stage2_id"])}}],
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"], "SELECT stage_id FROM deals WHERE id = %s", (scenario["deal_id"],)
    )
    assert str(rows[0][0]) == str(scenario["stage2_id"])
    activity_rows = _query(
        scenario["tenant_id"],
        "SELECT type FROM activities WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert "deal_stage_changed" in [r[0] for r in activity_rows]


async def test_notify_manager_action(scenario):
    rule = _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "notify_manager", "config": {"message": "heads up"}}],
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT type FROM activities WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert "workflow_notification" in [r[0] for r in rows]


async def test_raise_escalation_action(scenario):
    rule = _make_rule(scenario["tenant_id"], scenario["staff_id"], [{"type": "raise_escalation"}])
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT source, assigned_to FROM escalations WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert len(rows) == 1
    assert rows[0][0] == "rule_triggered"
    assert str(rows[0][1]) == str(scenario["manager_id"])


async def test_send_message_action_records_skipped_unavailable(scenario):
    rule = _make_rule(
        scenario["tenant_id"], scenario["staff_id"], [{"type": "send_message", "config": {}}]
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT status FROM workflow_runs WHERE workflow_rule_id = %s",
        (rule.id,),
    )
    assert rows[0][0] == "skipped_unavailable"


async def test_rerun_is_a_no_op(scenario):
    rule = _make_rule(
        scenario["tenant_id"], scenario["staff_id"], [{"type": "notify_manager", "config": {}}]
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT count(*) FROM activities WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert rows[0][0] == 1


async def test_conditions_that_do_not_match_skip_the_rule(scenario):
    rule = _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "notify_manager", "config": {}}],
        conditions=[{"field": "stage_id", "op": "eq", "value": str(uuid.uuid4())}],
    )
    await _run_one_rule(scenario["tenant_id"], rule, "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT count(*) FROM activities WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert rows[0][0] == 0


async def test_failing_action_creates_exactly_one_failure_escalation(scenario):
    # change_stage against a contact-sourced trigger always raises
    # (requires a deal) — exercises the retry-then-escalate path.
    rule = _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "change_stage", "config": {"to_stage_id": str(scenario["stage2_id"])}}],
    )
    await _run_one_rule(scenario["tenant_id"], rule, "contact", scenario["contact_id"])
    run_rows = _query(
        scenario["tenant_id"],
        "SELECT status, attempt FROM workflow_runs WHERE workflow_rule_id = %s",
        (rule.id,),
    )
    assert len(run_rows) == 1
    assert run_rows[0][0] == "failed"
    assert run_rows[0][1] == 3

    escalation_rows = _query(
        scenario["tenant_id"],
        "SELECT source, assigned_to FROM escalations WHERE source = 'workflow_failure'",
    )
    assert len(escalation_rows) == 1
    assert str(escalation_rows[0][1]) == str(scenario["manager_id"])  # staff's manager


async def test_evaluate_event_rules_runs_only_active_rules_of_matching_trigger(scenario):
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "INSERT INTO workflow_rules "
            "(tenant_id, name, trigger_type, actions, status, created_by) "
            "VALUES (%s, 'active rule', 'stage_changed', %s, 'active', %s), "
            "(%s, 'draft rule', 'stage_changed', %s, 'draft', %s)",
            (
                scenario["tenant_id"],
                '[{"type": "notify_manager", "config": {}}]',
                scenario["staff_id"],
                scenario["tenant_id"],
                '[{"type": "notify_manager", "config": {}}]',
                scenario["staff_id"],
            ),
        )
        cur.execute("RESET app.tenant_id")

    await _evaluate_event_rules(scenario["tenant_id"], "stage_changed", "deal", scenario["deal_id"])
    rows = _query(
        scenario["tenant_id"],
        "SELECT count(*) FROM activities WHERE deal_id = %s",
        (scenario["deal_id"],),
    )
    assert rows[0][0] == 1  # only the active rule fired, not the draft one


async def test_scan_time_based_rules_fires_on_a_seeded_past_timestamp(scenario):
    """PHASE_3_PLAN.md §10 acceptance criterion 6 — proven with a seeded
    past stage_changed_at, not a real 24-hour wait."""
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "UPDATE deals SET stage_changed_at = %s WHERE id = %s",
            (datetime.now(UTC) - timedelta(hours=25), scenario["deal_id"]),
        )
        cur.execute("RESET app.tenant_id")

    _make_rule(
        scenario["tenant_id"],
        scenario["staff_id"],
        [{"type": "raise_escalation"}],
        trigger_type="elapsed_time",
    )
    # trigger_config defaults to {} via _make_rule's INSERT — patch in
    # the elapsed-time threshold this test actually needs.
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(scenario["tenant_id"]),))
        cur.execute(
            "UPDATE workflow_rules SET trigger_config = %s::jsonb "
            "WHERE tenant_id = %s AND trigger_type = 'elapsed_time'",
            (json.dumps({"since": "stage_entered_at", "minutes": 1440}), scenario["tenant_id"]),
        )
        cur.execute("RESET app.tenant_id")

    await _scan_time_based_rules(scenario["tenant_id"])

    escalation_rows = _query(
        scenario["tenant_id"],
        "SELECT source, deal_id FROM escalations WHERE source = 'rule_triggered'",
    )
    assert len(escalation_rows) == 1
    assert str(escalation_rows[0][1]) == str(scenario["deal_id"])
