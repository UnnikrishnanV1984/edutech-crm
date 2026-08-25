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


@pytest.fixture
def tenant_and_user():
    tenant_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
    yield {"tenant_id": tenant_id, "user_sub": "sub-stage-test"}
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        for table in (
            "activities",
            "sla_policies",
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


def _headers(ctx: dict) -> dict:
    return {
        "X-Tenant-Id": str(ctx["tenant_id"]),
        "X-User-Id": ctx["user_sub"],
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


def _admin_headers(ctx: dict) -> dict:
    return {
        "X-Tenant-Id": str(ctx["tenant_id"]),
        "X-User-Id": ctx["user_sub"] + "-admin",
        "X-User-Email": "admin@example.test",
        "X-User-Role": "admin",
    }


def test_list_seeds_default_stages_lazily(tenant_and_user):
    with TestClient(app) as client:
        response = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
    assert response.status_code == 200
    stages = response.json()["data"]
    names = [s["name"] for s in stages]
    assert names == [
        "Inquiry",
        "Contacted",
        "Demo scheduled",
        "Demo attended",
        "Application submitted",
        "Fee paid",
        "Enrolled",
        "Dropped",
    ]
    enrolled = next(s for s in stages if s["name"] == "Enrolled")
    dropped = next(s for s in stages if s["name"] == "Dropped")
    assert enrolled["is_won"] is True
    assert dropped["is_lost"] is True


def test_seeding_also_writes_default_snapshot(tenant_and_user):
    """PIPELINE_CONFIG_RESET_PLAN.md §4.3 — the snapshot is written in the
    same transaction as the initial 8 stages, not a separate step. No
    public API reads this table directly (it's only ever consumed
    internally by reset-to-default), so this checks the DB row directly."""
    with TestClient(app) as client:
        client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false)", (str(tenant_and_user["tenant_id"]),)
        )
        cur.execute(
            "SELECT name, sort_order, is_won, is_lost FROM pipeline_stage_default_snapshots "
            "WHERE tenant_id = %s ORDER BY sort_order",
            (tenant_and_user["tenant_id"],),
        )
        rows = cur.fetchall()
        cur.execute("RESET app.tenant_id")
    assert [r[0] for r in rows] == [
        "Inquiry",
        "Contacted",
        "Demo scheduled",
        "Demo attended",
        "Application submitted",
        "Fee paid",
        "Enrolled",
        "Dropped",
    ]
    assert rows[6] == ("Enrolled", 7, True, False)
    assert rows[7] == ("Dropped", 8, False, True)


def test_seeding_is_idempotent(tenant_and_user):
    with TestClient(app) as client:
        first = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
        second = client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))
    assert len(first.json()["data"]) == 8
    assert len(second.json()["data"]) == 8
    assert [s["id"] for s in first.json()["data"]] == [s["id"] for s in second.json()["data"]]


def test_rename_stage(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")

        response = client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "New Inquiry"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "New Inquiry"


def test_rename_to_existing_name_returns_409(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")

        response = client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "Contacted"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_default_win_probability_is_zero(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
    assert all(s["win_probability_pct"] == 0 for s in stages)


def test_set_win_probability(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        contacted_id = next(s["id"] for s in stages if s["name"] == "Contacted")

        response = client.patch(
            f"/api/v1/pipeline-stages/{contacted_id}",
            json={"win_probability_pct": 30},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    assert response.json()["data"]["win_probability_pct"] == 30


def test_win_probability_out_of_range_is_rejected(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        response = client.patch(
            f"/api/v1/pipeline-stages/{stages[0]['id']}",
            json={"win_probability_pct": 150},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 400


def test_two_tenants_get_independent_default_stages(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
    try:
        with TestClient(app) as client:
            client.patch(
                (
                    "/api/v1/pipeline-stages/"
                    + client.get(
                        "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
                    ).json()["data"][0]["id"]
                ),
                json={"name": "Tenant A Custom Name"},
                headers=_admin_headers(tenant_and_user),
            )
            other_headers = {
                "X-Tenant-Id": str(tenant_id_2),
                "X-User-Id": "sub-other",
                "X-User-Email": "other@example.test",
                "X-User-Role": "counselor",
            }
            other_stages = client.get("/api/v1/pipeline-stages", headers=other_headers).json()[
                "data"
            ]
        assert other_stages[0]["name"] == "Inquiry"
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute(
                "DELETE FROM pipeline_stage_default_snapshots WHERE tenant_id = %s",
                (tenant_id_2,),
            )
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))


# ADMIN_UX_IMPROVEMENTS_PLAN.md Sec7 step 3 — the admin-gate tightening
# and the new create/delete/reorder routes.


def test_counselor_gets_403_patching_stage(tenant_and_user):
    """Deliberate behavior change (ADMIN_UX_IMPROVEMENTS_PLAN.md Sec4.1)
    — PATCH had no role gate before this; a counselor could previously
    rename a stage."""
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        response = client.patch(
            f"/api/v1/pipeline-stages/{stages[0]['id']}",
            json={"name": "Should be rejected"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_stage_requires_admin(tenant_and_user):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/pipeline-stages",
            json={"name": "Trial Class"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 403


def test_create_stage_appends_at_end(tenant_and_user):
    with TestClient(app) as client:
        client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))  # seed
        response = client.post(
            "/api/v1/pipeline-stages",
            json={"name": "Trial Class"},
            headers=_admin_headers(tenant_and_user),
        )
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["name"] == "Trial Class"
    assert body["is_won"] is False
    assert body["is_lost"] is False
    assert stages[-1]["name"] == "Trial Class"
    assert stages[-1]["sort_order"] > stages[-2]["sort_order"]


def test_create_stage_with_invoice_and_rework_flags(tenant_and_user):
    """PIPELINE_AND_REVENUE_PLAN.md §7 task 4 — same creation-only shape
    as is_won/is_lost."""
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/pipeline-stages",
            json={"name": "Invoice Sent", "is_invoice_stage": True},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["is_invoice_stage"] is True
    assert body["is_rework_stage"] is False


def test_patch_stage_cannot_change_invoice_or_rework_flags(tenant_and_user):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/pipeline-stages",
            json={"name": "Invoice Sent", "is_invoice_stage": True},
            headers=_admin_headers(tenant_and_user),
        ).json()["data"]
        response = client.patch(
            f"/api/v1/pipeline-stages/{created['id']}",
            json={"name": "Invoice Sent (renamed)"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["name"] == "Invoice Sent (renamed)"
    assert body["is_invoice_stage"] is True  # unchanged — not a PATCH-able field


def test_create_stage_duplicate_name_returns_409(tenant_and_user):
    with TestClient(app) as client:
        client.get("/api/v1/pipeline-stages", headers=_headers(tenant_and_user))  # seed
        response = client.post(
            "/api/v1/pipeline-stages",
            json={"name": "Inquiry"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 409


def _create_contact_and_deal(client, ctx, stage_id=None):
    contact = client.post(
        "/api/v1/contacts",
        json={"full_name": "Stage Delete Test Contact", "lead_source": "web"},
        headers=_headers(ctx),
    ).json()["data"]
    course_id = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ctx["tenant_id"]),))
        cur.execute(
            "INSERT INTO courses (id, tenant_id, name, code) VALUES (%s, %s, %s, %s)",
            (course_id, ctx["tenant_id"], "Test Course", f"C-{course_id.hex[:6]}"),
        )
        cur.execute("RESET app.tenant_id")
    deal = client.post(
        f"/api/v1/contacts/{contact['id']}/deals",
        json={"course_id": str(course_id), **({"stage_id": stage_id} if stage_id else {})},
        headers=_headers(ctx),
    ).json()["data"]
    return contact, deal


def test_delete_stage_blocked_when_referenced_by_deal(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
        _create_contact_and_deal(client, tenant_and_user)

        response = client.delete(
            f"/api/v1/pipeline-stages/{inquiry_id}", headers=_admin_headers(tenant_and_user)
        )
    assert response.status_code == 409


def test_delete_stage_blocked_when_last_won(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        enrolled_id = next(s["id"] for s in stages if s["name"] == "Enrolled")

        response = client.delete(
            f"/api/v1/pipeline-stages/{enrolled_id}", headers=_admin_headers(tenant_and_user)
        )
    assert response.status_code == 409


def test_delete_stage_succeeds_when_unused(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        fee_paid_id = next(s["id"] for s in stages if s["name"] == "Fee paid")

        response = client.delete(
            f"/api/v1/pipeline-stages/{fee_paid_id}", headers=_admin_headers(tenant_and_user)
        )
        remaining = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
    assert response.status_code == 200
    assert "Fee paid" not in [s["name"] for s in remaining]


def test_reorder_persists_new_order(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        reversed_ids = [s["id"] for s in reversed(stages)]

        response = client.patch(
            "/api/v1/pipeline-stages/reorder",
            json={"stage_ids": reversed_ids},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    assert [s["id"] for s in response.json()["data"]] == reversed_ids


def test_reorder_twice_in_a_row_does_not_collide(tenant_and_user):
    """Exercises the exact collision the naive single-row PATCH approach
    would hit on a second reorder call — ADMIN_UX_IMPROVEMENTS_PLAN.md
    Sec6.3/Sec8."""
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        ids = [s["id"] for s in stages]

        first = client.patch(
            "/api/v1/pipeline-stages/reorder",
            json={"stage_ids": list(reversed(ids))},
            headers=_admin_headers(tenant_and_user),
        )
        second = client.patch(
            "/api/v1/pipeline-stages/reorder",
            json={"stage_ids": ids},
            headers=_admin_headers(tenant_and_user),
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert [s["id"] for s in second.json()["data"]] == ids


def test_reorder_rejects_partial_list(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        partial_ids = [s["id"] for s in stages[:-1]]  # missing the last stage

        response = client.patch(
            "/api/v1/pipeline-stages/reorder",
            json={"stage_ids": partial_ids},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 400
    stages_after = client.get(
        "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
    ).json()["data"]
    assert [s["sort_order"] for s in stages_after] == sorted(
        s["sort_order"] for s in stages_after
    )


def test_reorder_rejects_another_tenants_stage_id(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
    other_ctx = {"tenant_id": tenant_id_2, "user_sub": "sub-other-reorder"}
    try:
        with TestClient(app) as client:
            own_stages = client.get(
                "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
            ).json()["data"]
            other_stages = client.get(
                "/api/v1/pipeline-stages", headers=_headers(other_ctx)
            ).json()["data"]

            # Swap in a foreign stage id in place of one of the caller's own.
            tampered_ids = [s["id"] for s in own_stages[:-1]] + [other_stages[0]["id"]]

            response = client.patch(
                "/api/v1/pipeline-stages/reorder",
                json={"stage_ids": tampered_ids},
                headers=_admin_headers(tenant_and_user),
            )
        assert response.status_code == 400
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute(
                "DELETE FROM pipeline_stage_default_snapshots WHERE tenant_id = %s",
                (tenant_id_2,),
            )
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))


# PIPELINE_CONFIG_RESET_PLAN.md §5.1/§7 task 3 — POST /pipeline-stages/batch.


def test_batch_update_happy_path(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        by_name = {s["name"]: s for s in stages}
        # Keep every existing stage except "Fee paid" (dropped), rename
        # "Contacted" -> "Reached", and add one brand-new stage — full
        # final order given explicitly, new stage last.
        payload = {
            "stages": [
                {"id": by_name["Inquiry"]["id"], "name": "Inquiry"},
                {"id": by_name["Contacted"]["id"], "name": "Reached"},
                {"id": by_name["Demo scheduled"]["id"], "name": "Demo scheduled"},
                {"id": by_name["Demo attended"]["id"], "name": "Demo attended"},
                {"id": by_name["Application submitted"]["id"], "name": "Application submitted"},
                {"id": by_name["Enrolled"]["id"], "name": "Enrolled"},
                {"id": by_name["Dropped"]["id"], "name": "Dropped"},
                {"name": "Proposal Sent"},
            ]
        }
        response = client.post(
            "/api/v1/pipeline-stages/batch", json=payload, headers=_admin_headers(tenant_and_user)
        )
    assert response.status_code == 200
    result = response.json()["data"]
    assert [s["name"] for s in result] == [
        "Inquiry",
        "Reached",
        "Demo scheduled",
        "Demo attended",
        "Application submitted",
        "Enrolled",
        "Dropped",
        "Proposal Sent",
    ]
    assert [s["sort_order"] for s in result] == list(range(1, 9))
    assert "Fee paid" not in [s["name"] for s in result]


def test_batch_update_blocked_delete_rejects_whole_batch(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        by_name = {s["name"]: s for s in stages}
        _create_contact_and_deal(client, tenant_and_user, stage_id=by_name["Inquiry"]["id"])

        # Drops "Inquiry" (in use by the deal above — must block the
        # whole batch) while also renaming "Contacted", which must NOT
        # take effect either.
        payload = {
            "stages": [
                {"id": s["id"], "name": "Renamed" if s["name"] == "Contacted" else s["name"]}
                for s in stages
                if s["name"] != "Inquiry"
            ]
        }
        response = client.post(
            "/api/v1/pipeline-stages/batch", json=payload, headers=_admin_headers(tenant_and_user)
        )
        after = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
    assert response.status_code == 409
    assert "Inquiry" in [s["name"] for s in after]
    assert "Contacted" in [s["name"] for s in after]  # unrelated rename NOT applied
    assert "Renamed" not in [s["name"] for s in after]


def test_batch_update_blocked_by_sla_policy_in_use(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, false)",
                (str(tenant_and_user["tenant_id"]),),
            )
            cur.execute(
                "INSERT INTO sla_policies (tenant_id, name, applies_to, stage_id, target_minutes) "
                "VALUES (%s, 'batch test policy', 'stage_entry', %s, 30)",
                (tenant_and_user["tenant_id"], inquiry_id),
            )
            cur.execute("RESET app.tenant_id")

        payload = {"stages": [s for s in stages if s["name"] != "Inquiry"]}
        response = client.post(
            "/api/v1/pipeline-stages/batch", json=payload, headers=_admin_headers(tenant_and_user)
        )
    assert response.status_code == 409


def test_batch_update_rejects_final_list_without_won_stage(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        payload = {"stages": [s for s in stages if s["name"] != "Enrolled"]}
        response = client.post(
            "/api/v1/pipeline-stages/batch", json=payload, headers=_admin_headers(tenant_and_user)
        )
    assert response.status_code == 400


def test_batch_update_rejects_another_tenants_stage_id(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
    other_ctx = {"tenant_id": tenant_id_2, "user_sub": "sub-other-batch"}
    try:
        with TestClient(app) as client:
            own_stages = client.get(
                "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
            ).json()["data"]
            other_stages = client.get(
                "/api/v1/pipeline-stages", headers=_headers(other_ctx)
            ).json()["data"]
            payload = {
                "stages": [{"id": s["id"], "name": s["name"]} for s in own_stages[:-1]]
                + [{"id": other_stages[0]["id"], "name": other_stages[0]["name"]}]
            }
            response = client.post(
                "/api/v1/pipeline-stages/batch",
                json=payload,
                headers=_admin_headers(tenant_and_user),
            )
        assert response.status_code == 400
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute(
                "DELETE FROM pipeline_stage_default_snapshots WHERE tenant_id = %s",
                (tenant_id_2,),
            )
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))


def test_batch_update_requires_admin(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        response = client.post(
            "/api/v1/pipeline-stages/batch",
            json={"stages": stages},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 403


# PIPELINE_CONFIG_RESET_PLAN.md §5.2/§7 task 4 — POST /pipeline-stages/reset-to-default.


def test_reset_to_default_restores_snapshot_exactly(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
        client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "Renamed Away"},
            headers=_admin_headers(tenant_and_user),
        )
        client.delete(
            f"/api/v1/pipeline-stages/{next(s['id'] for s in stages if s['name'] == 'Fee paid')}",
            headers=_admin_headers(tenant_and_user),
        )

        response = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={"confirm": "RESET TO DEFAULT"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 200
    result = response.json()["data"]
    assert [s["name"] for s in result] == [
        "Inquiry",
        "Contacted",
        "Demo scheduled",
        "Demo attended",
        "Application submitted",
        "Fee paid",
        "Enrolled",
        "Dropped",
    ]
    enrolled = next(s for s in result if s["name"] == "Enrolled")
    dropped = next(s for s in result if s["name"] == "Dropped")
    assert enrolled["is_won"] is True
    assert dropped["is_lost"] is True
    # Fresh rows, not the renamed/deleted ones from before.
    assert inquiry_id != next(s["id"] for s in result if s["name"] == "Inquiry")


def test_reset_to_default_blocked_by_deal_in_use_leaves_config_unchanged(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
        _create_contact_and_deal(client, tenant_and_user, stage_id=inquiry_id)
        client.patch(
            f"/api/v1/pipeline-stages/{inquiry_id}",
            json={"name": "Still In Use"},
            headers=_admin_headers(tenant_and_user),
        )

        response = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={"confirm": "RESET TO DEFAULT"},
            headers=_admin_headers(tenant_and_user),
        )
        after = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
    assert response.status_code == 409
    assert "Still In Use" in [s["name"] for s in after]  # untouched, not partially reset


def test_reset_to_default_blocked_by_sla_policy_in_use(tenant_and_user):
    with TestClient(app) as client:
        stages = client.get(
            "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
        ).json()["data"]
        inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, false)",
                (str(tenant_and_user["tenant_id"]),),
            )
            cur.execute(
                "INSERT INTO sla_policies (tenant_id, name, applies_to, stage_id, target_minutes) "
                "VALUES (%s, 'reset test policy', 'stage_entry', %s, 30)",
                (tenant_and_user["tenant_id"], inquiry_id),
            )
            cur.execute("RESET app.tenant_id")

        response = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={"confirm": "RESET TO DEFAULT"},
            headers=_admin_headers(tenant_and_user),
        )
    assert response.status_code == 409


def test_reset_to_default_rejects_wrong_confirm_phrase(tenant_and_user):
    with TestClient(app) as client:
        wrong = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={"confirm": "reset to default"},
            headers=_admin_headers(tenant_and_user),
        )
        missing = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={},
            headers=_admin_headers(tenant_and_user),
        )
    assert wrong.status_code == 400
    assert missing.status_code == 400


def test_reset_to_default_requires_admin(tenant_and_user):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/pipeline-stages/reset-to-default",
            json={"confirm": "RESET TO DEFAULT"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 403


def test_reset_to_default_is_tenant_isolated(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
    other_ctx = {"tenant_id": tenant_id_2, "user_sub": "sub-other-reset"}
    try:
        with TestClient(app) as client:
            client.get("/api/v1/pipeline-stages", headers=_headers(other_ctx))  # seed
            stages = client.get(
                "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
            ).json()["data"]
            inquiry_id = next(s["id"] for s in stages if s["name"] == "Inquiry")
            client.patch(
                f"/api/v1/pipeline-stages/{inquiry_id}",
                json={"name": "Tenant A Only"},
                headers=_admin_headers(tenant_and_user),
            )

            other_admin = {
                "X-Tenant-Id": str(tenant_id_2),
                "X-User-Id": "sub-other-reset-admin",
                "X-User-Email": "other-admin@example.test",
                "X-User-Role": "admin",
            }
            client.post(
                "/api/v1/pipeline-stages/reset-to-default",
                json={"confirm": "RESET TO DEFAULT"},
                headers=other_admin,
            )

            tenant_a_after = client.get(
                "/api/v1/pipeline-stages", headers=_headers(tenant_and_user)
            ).json()["data"]
        assert "Tenant A Only" in [s["name"] for s in tenant_a_after]
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute(
                "DELETE FROM pipeline_stage_default_snapshots WHERE tenant_id = %s",
                (tenant_id_2,),
            )
            cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))
