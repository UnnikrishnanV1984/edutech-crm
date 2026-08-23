"""Idempotent local-dev tenant seed.

Only run in development (docker-entrypoint.sh gates this on
ENVIRONMENT=development) — never seed synthetic tenants into a real
deployment. Runs as crm_migrate (DATABASE_URL): crm_app only has SELECT
on tenants (see alembic 0002), by design.

These UUIDs are fixed, not generated, so they pair exactly with the
`tenant_id` user attribute baked into keycloak/realm-export.json — see
keycloak/README.md for why. Only tenants are seeded here; users are
JIT-provisioned on first login (DEVELOPMENT_PLAN.md §4.4), so there is
nothing else to seed.
"""

import os

import psycopg

TENANTS = [
    ("a1111111-1111-1111-1111-111111111111", "tenant-a", "Tenant A Academy"),
    ("b2222222-2222-2222-2222-222222222222", "tenant-b", "Tenant B Academy"),
]


def main() -> None:
    database_url = os.environ["DATABASE_URL"].replace("+psycopg", "")
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        for tenant_id, slug, name in TENANTS:
            cur.execute(
                "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (tenant_id, slug, name),
            )


if __name__ == "__main__":
    main()
