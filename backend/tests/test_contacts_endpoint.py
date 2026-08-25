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
    user_sub = f"sub-{uuid.uuid4()}"
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id, f"t-{tenant_id}", "Test Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (gen_random_uuid(), %s, %s, %s, 'counselor') RETURNING id",
            (tenant_id, user_sub, "counselor@example.test"),
        )
        user_id = cur.fetchone()[0]
        cur.execute("RESET app.tenant_id")
    yield {"tenant_id": tenant_id, "user_sub": user_sub, "user_id": user_id}
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("DELETE FROM follow_up_flags WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM deals WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM pipeline_stages WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM contacts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


def _headers(ctx: dict) -> dict:
    return {
        "X-Tenant-Id": str(ctx["tenant_id"]),
        "X-User-Id": ctx["user_sub"],
        "X-User-Email": "counselor@example.test",
        "X-User-Role": "counselor",
    }


def test_create_contact_defaults_owner_to_acting_user(tenant_and_user):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/contacts",
            json={"full_name": "Alice", "email": "alice@example.test", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["full_name"] == "Alice"
    assert body["owner_id"] == str(tenant_and_user["user_id"])


def test_duplicate_email_returns_409_with_existing_contact_id(tenant_and_user):
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/contacts",
            json={"full_name": "Bob", "email": "bob@example.test", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        )
        existing_id = first.json()["data"]["id"]

        second = client.post(
            "/api/v1/contacts",
            json={"full_name": "Bob Two", "email": "BOB@example.test", "lead_source": "manual"},
            headers=_headers(tenant_and_user),
        )
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"][0]["existing_contact_id"] == existing_id


def test_duplicate_email_across_tenants_is_allowed(tenant_and_user):
    tenant_id_2 = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant_id_2, f"t-{tenant_id_2}", "Other Tenant"),
        )
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
        cur.execute(
            "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
            "VALUES (gen_random_uuid(), %s, %s, %s, 'counselor') RETURNING id",
            (tenant_id_2, "sub-other", "other@example.test"),
        )
        cur.fetchone()
        cur.execute("RESET app.tenant_id")

    try:
        with TestClient(app) as client:
            client.post(
                "/api/v1/contacts",
                json={"full_name": "Carl", "email": "carl@example.test", "lead_source": "web"},
                headers=_headers(tenant_and_user),
            )
            other_headers = {
                "X-Tenant-Id": str(tenant_id_2),
                "X-User-Id": "sub-other",
                "X-User-Email": "other@example.test",
                "X-User-Role": "counselor",
            }
            response = client.post(
                "/api/v1/contacts",
                json={"full_name": "Carl Two", "email": "carl@example.test", "lead_source": "web"},
                headers=other_headers,
            )
        assert response.status_code == 200
    finally:
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id_2),))
            cur.execute("DELETE FROM contacts WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id_2,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id_2,))


def test_search_and_filter(tenant_and_user):
    with TestClient(app) as client:
        client.post(
            "/api/v1/contacts",
            json={"full_name": "Dana Meta", "email": "dana@example.test", "lead_source": "meta"},
            headers=_headers(tenant_and_user),
        )
        client.post(
            "/api/v1/contacts",
            json={"full_name": "Eve Web", "email": "eve@example.test", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        )

        by_search = client.get(
            "/api/v1/contacts?search=dana", headers=_headers(tenant_and_user)
        )
        by_source = client.get(
            "/api/v1/contacts?lead_source=web", headers=_headers(tenant_and_user)
        )

    assert by_search.status_code == 200
    search_names = [c["full_name"] for c in by_search.json()["data"]]
    assert search_names == ["Dana Meta"]

    assert by_source.status_code == 200
    source_names = [c["full_name"] for c in by_source.json()["data"]]
    assert source_names == ["Eve Web"]
    assert by_source.json()["meta"]["total"] == 1


def test_get_and_patch_contact(tenant_and_user):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/contacts",
            json={"full_name": "Frank", "lead_source": "manual"},
            headers=_headers(tenant_and_user),
        ).json()["data"]

        fetched = client.get(
            f"/api/v1/contacts/{created['id']}", headers=_headers(tenant_and_user)
        )
        assert fetched.status_code == 200
        assert fetched.json()["data"]["full_name"] == "Frank"

        patched = client.patch(
            f"/api/v1/contacts/{created['id']}",
            json={"full_name": "Frank Updated"},
            headers=_headers(tenant_and_user),
        )
        assert patched.status_code == 200
        assert patched.json()["data"]["full_name"] == "Frank Updated"


def test_create_and_patch_contact_territory(tenant_and_user):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/contacts",
            json={"full_name": "Gita", "lead_source": "manual", "territory": "south"},
            headers=_headers(tenant_and_user),
        ).json()["data"]
        assert created["territory"] == "south"

        patched = client.patch(
            f"/api/v1/contacts/{created['id']}",
            json={"territory": "north"},
            headers=_headers(tenant_and_user),
        )
        assert patched.status_code == 200
        assert patched.json()["data"]["territory"] == "north"


def test_list_contacts_includes_latest_deal_stage(tenant_and_user):
    tenant_id = tenant_and_user["tenant_id"]
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/contacts",
            json={"full_name": "Hana", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        ).json()["data"]

        stage_id = uuid.uuid4()
        deal_id = uuid.uuid4()
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
            cur.execute(
                "INSERT INTO pipeline_stages (id, tenant_id, name, sort_order) "
                "VALUES (%s, %s, %s, 1)",
                (stage_id, tenant_id, "Contacted"),
            )
            cur.execute(
                "INSERT INTO deals (id, tenant_id, contact_id, stage_id, owner_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (deal_id, tenant_id, created["id"], stage_id, tenant_and_user["user_id"]),
            )
            cur.execute("RESET app.tenant_id")

        response = client.get("/api/v1/contacts", headers=_headers(tenant_and_user))

    assert response.status_code == 200
    row = next(c for c in response.json()["data"] if c["id"] == created["id"])
    assert row["stage_id"] == str(stage_id)
    assert row["stage_name"] == "Contacted"
    assert row["sla_state"] is None
    assert row["has_open_follow_up"] is False


def test_list_contacts_stage_id_filter(tenant_and_user):
    tenant_id = tenant_and_user["tenant_id"]
    with TestClient(app) as client:
        with_deal = client.post(
            "/api/v1/contacts",
            json={"full_name": "Ivan", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        ).json()["data"]
        client.post(
            "/api/v1/contacts",
            json={"full_name": "Jai No Deal", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        )

        stage_id = uuid.uuid4()
        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
            cur.execute(
                "INSERT INTO pipeline_stages (id, tenant_id, name, sort_order) "
                "VALUES (%s, %s, %s, 1)",
                (stage_id, tenant_id, "New lead"),
            )
            cur.execute(
                "INSERT INTO deals (id, tenant_id, contact_id, stage_id, owner_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (uuid.uuid4(), tenant_id, with_deal["id"], stage_id, tenant_and_user["user_id"]),
            )
            cur.execute("RESET app.tenant_id")

        response = client.get(
            f"/api/v1/contacts?stage_id={stage_id}", headers=_headers(tenant_and_user)
        )

    assert response.status_code == 200
    names = [c["full_name"] for c in response.json()["data"]]
    assert names == ["Ivan"]


def test_list_contacts_has_follow_up_flag_filter(tenant_and_user):
    tenant_id = tenant_and_user["tenant_id"]
    with TestClient(app) as client:
        flagged = client.post(
            "/api/v1/contacts",
            json={"full_name": "Kim Flagged", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        ).json()["data"]
        client.post(
            "/api/v1/contacts",
            json={"full_name": "Leo Unflagged", "lead_source": "web"},
            headers=_headers(tenant_and_user),
        )

        with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
            cur.execute(
                "INSERT INTO follow_up_flags (id, tenant_id, manager_id, contact_id, note, "
                "remind_on) VALUES (%s, %s, %s, %s, %s, '2026-09-01')",
                (uuid.uuid4(), tenant_id, tenant_and_user["user_id"], flagged["id"], "check in"),
            )
            cur.execute("RESET app.tenant_id")

        response = client.get(
            "/api/v1/contacts?has_follow_up_flag=true", headers=_headers(tenant_and_user)
        )

    assert response.status_code == 200
    names = [c["full_name"] for c in response.json()["data"]]
    assert names == ["Kim Flagged"]
    assert response.json()["data"][0]["has_open_follow_up"] is True


def test_get_unknown_contact_returns_404(tenant_and_user):
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/contacts/{uuid.uuid4()}", headers=_headers(tenant_and_user)
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
