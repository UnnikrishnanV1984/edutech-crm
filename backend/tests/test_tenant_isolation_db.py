"""Direct-to-Postgres tenant isolation tests — no HTTP layer involved.

Proves the innermost of the three defence-in-depth layers described in
DEVELOPMENT_PLAN.md §5: even if the BFF and the FastAPI dependency both
somehow forwarded the wrong tenant, RLS on `users` still holds the line.

Requires a real Postgres reachable via DATABASE_URL (crm_migrate, used
only to seed) and DATABASE_APP_URL (crm_app, used for every assertion).
Skipped if either is unset or unreachable — CI's backend job provides a
Postgres service container and runs the 0001/0002 migrations first; a
bare local `pytest` run without a DB simply skips this file.
"""

import os
import uuid

import psycopg
import pytest

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
def seeded_tenants():
    """Two tenants, one user each, seeded per-tenant per plan §3.4 —
    FORCE ROW LEVEL SECURITY applies to the table owner too, so even the
    migrate role must set app.tenant_id before inserting that tenant's
    rows rather than inserting cross-tenant in one shot."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s), (%s, %s, %s)",
                (tenant_a, f"a-{tenant_a}", "Tenant A", tenant_b, f"b-{tenant_b}", "Tenant B"),
            )
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_a),))
            cur.execute(
                "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
                "VALUES (%s, %s, %s, %s, 'counselor')",
                (user_a, tenant_a, "sub-a", "a@example.test"),
            )
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_b),))
            cur.execute(
                "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
                "VALUES (%s, %s, %s, %s, 'counselor')",
                (user_b, tenant_b, "sub-b", "b@example.test"),
            )
            cur.execute("RESET app.tenant_id")

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b, "user_a": user_a, "user_b": user_b}

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_a),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_a,))
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_b),))
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_b,))
            cur.execute("RESET app.tenant_id")
            cur.execute("DELETE FROM tenants WHERE id IN (%s, %s)", (tenant_a, tenant_b))


def test_crm_app_has_no_superuser_or_bypassrls():
    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'crm_app'")
        rolsuper, rolbypassrls = cur.fetchone()
    assert rolsuper is False
    assert rolbypassrls is False


def test_query_without_tenant_context_raises():
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.UndefinedObject):
            cur.execute("SELECT count(*) FROM users")


def test_select_scoped_to_tenant(seeded_tenants):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false)", (str(seeded_tenants["tenant_a"]),)
        )
        cur.execute("SELECT id FROM users")
        rows = {row[0] for row in cur.fetchall()}
    assert rows == {seeded_tenants["user_a"]}


def test_update_does_not_touch_other_tenant(seeded_tenants):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false)", (str(seeded_tenants["tenant_a"]),)
        )
        cur.execute(
            "UPDATE users SET full_name = 'x' WHERE tenant_id = %s", (seeded_tenants["tenant_b"],)
        )
        assert cur.rowcount == 0

    with psycopg.connect(MIGRATE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false)", (str(seeded_tenants["tenant_b"]),)
        )
        cur.execute("SELECT full_name FROM users WHERE id = %s", (seeded_tenants["user_b"],))
        assert cur.fetchone()[0] is None


def test_insert_cross_tenant_rejected_by_check(seeded_tenants):
    with psycopg.connect(APP_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false)", (str(seeded_tenants["tenant_a"]),)
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO users (id, tenant_id, keycloak_sub, email, role) "
                "VALUES (%s, %s, %s, %s, 'counselor')",
                (uuid.uuid4(), seeded_tenants["tenant_b"], "sub-x", "x@example.test"),
            )
