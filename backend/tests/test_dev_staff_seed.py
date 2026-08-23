"""app/db/seed.py's provision_dev_staff — pre-provisions `users` rows from
a Keycloak realm export file, keyed the same way JIT-provisioning
(upsert_user) is, so a real login later updates the row instead of
duplicating it. See keycloak/README.md and SEED_CONNECTORS_PLAN.md.
"""

import json
import os
import uuid

import psycopg
import pytest

from app.db.seed import provision_dev_staff

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
    not (MIGRATE_URL and APP_URL and _reachable(MIGRATE_URL)),
    reason="DATABASE_URL/DATABASE_APP_URL not set or Postgres unreachable",
)


@pytest.fixture
def tenant_id():
    tid = uuid.uuid4()
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tid, f"t-{tid}", "Dev Staff Seed Test Tenant"),
        )
    yield tid
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        cur.execute("DELETE FROM users WHERE tenant_id = %s", (tid,))
        cur.execute("RESET app.tenant_id")
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))


def _write_realm_file(tmp_path, tenant_id, *, keycloak_id, email, role="counselor"):
    realm = {
        "users": [
            {
                "id": str(keycloak_id),
                "username": "staff.seed.test",
                "email": email,
                "firstName": "Staff",
                "lastName": "Seed",
                "realmRoles": [role],
                "attributes": {"tenant_id": [str(tenant_id)]},
            }
        ]
    }
    path = tmp_path / "dev-realm.json"
    path.write_text(json.dumps(realm))
    return str(path)


def _fetch_user(tenant_id, keycloak_sub):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT id, email, full_name, role FROM users "
            "WHERE tenant_id = %s AND keycloak_sub = %s",
            (str(tenant_id), keycloak_sub),
        )
        return cur.fetchone()


async def test_provisions_a_user_row_from_the_realm_file(tenant_id, tmp_path):
    keycloak_id = uuid.uuid4()
    realm_path = _write_realm_file(
        tmp_path, tenant_id, keycloak_id=keycloak_id, email="staff.seed@example.test"
    )

    await provision_dev_staff(realm_path=realm_path)

    row = _fetch_user(tenant_id, str(keycloak_id))
    assert row is not None
    user_id, email, full_name, role = row
    assert email == "staff.seed@example.test"
    assert full_name == "Staff Seed"
    assert role == "counselor"


async def test_rerunning_updates_in_place_instead_of_duplicating(tenant_id, tmp_path):
    keycloak_id = uuid.uuid4()
    realm_path = _write_realm_file(
        tmp_path, tenant_id, keycloak_id=keycloak_id, email="staff.seed@example.test"
    )

    await provision_dev_staff(realm_path=realm_path)
    first_row = _fetch_user(tenant_id, str(keycloak_id))

    # Simulates a role change in Keycloak between runs, same way a real
    # login re-syncs role via upsert_user.
    updated_path = _write_realm_file(
        tmp_path,
        tenant_id,
        keycloak_id=keycloak_id,
        email="staff.seed@example.test",
        role="manager",
    )
    await provision_dev_staff(realm_path=updated_path)

    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))
        cur.execute(
            "SELECT id, role FROM users WHERE tenant_id = %s AND keycloak_sub = %s",
            (str(tenant_id), str(keycloak_id)),
        )
        rows = cur.fetchall()

    assert len(rows) == 1
    second_id, role = rows[0]
    assert second_id == first_row[0]
    assert role == "manager"


async def test_missing_realm_file_is_a_silent_no_op(tmp_path):
    await provision_dev_staff(realm_path=str(tmp_path / "does-not-exist.json"))
