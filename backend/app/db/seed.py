"""Idempotent local-dev tenant + dev-staff seed.

Only run in development (docker-entrypoint.sh gates this on
ENVIRONMENT=development) — never seed synthetic tenants into a real
deployment.

Two things happen here, in order:
1. Tenants — as crm_migrate (DATABASE_URL): crm_app only has SELECT on
   tenants (see alembic 0002), by design. These UUIDs are fixed, not
   generated, so they pair exactly with the `tenant_id` user attribute
   baked into keycloak/realm-export.json — see keycloak/README.md.
2. Dev staff — pre-provisions `users` rows for that same realm file's
   pinned-id seed identities, via the *same* upsert_user JIT-provisioning
   already uses on every real login (keyed on tenant_id + keycloak_sub),
   so a real login later updates this row rather than duplicating it.
   Needed so app/connectors/ has a real owner to assign seeded leads to
   from the very first `docker compose up`, before anyone has logged in.
"""

import asyncio
import json
import os
import sys
import uuid

import psycopg
from sqlalchemy import text

from app.db.session import get_sessionmaker
from app.services.user_service import upsert_user

if sys.platform == "win32":
    # Same constraint as app/main.py — psycopg3's async mode can't run
    # under ProactorEventLoop, Windows's asyncio default. This module is
    # its own standalone async entrypoint (`python -m app.db.seed`), not
    # imported by main.py, so it needs the same guard independently.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TENANTS = [
    ("a1111111-1111-1111-1111-111111111111", "tenant-a", "Tenant A Academy"),
    ("b2222222-2222-2222-2222-222222222222", "tenant-b", "Tenant B Academy"),
]

DEV_REALM_PATH = os.environ.get("DEV_REALM_PATH", "/app/dev-realm.json")


def seed_tenants() -> None:
    database_url = os.environ["DATABASE_URL"].replace("+psycopg", "")
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        for tenant_id, slug, name in TENANTS:
            cur.execute(
                "INSERT INTO tenants (id, slug, name) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (tenant_id, slug, name),
            )


async def provision_dev_staff(realm_path: str = DEV_REALM_PATH) -> None:
    """Reads the Keycloak realm export's `users` array directly — the
    pinned `id`/`tenant_id`/`email`/name/role are already the single
    source of truth for these dev identities, so this deliberately does
    not duplicate them into a second hardcoded list. Silently does
    nothing if the file isn't mounted (e.g. running outside the backend
    container)."""
    if not os.path.exists(realm_path):
        return
    with open(realm_path, encoding="utf-8") as f:
        realm = json.load(f)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        for user in realm.get("users", []):
            tenant_ids = user.get("attributes", {}).get("tenant_id") or []
            if not tenant_ids or "id" not in user:
                continue
            tenant_id = uuid.UUID(tenant_ids[0])
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            full_name = (
                " ".join(part for part in (user.get("firstName"), user.get("lastName")) if part)
                or None
            )
            role = (user.get("realmRoles") or ["counselor"])[0]
            await upsert_user(
                db=session,
                tenant_id=tenant_id,
                keycloak_sub=user["id"],
                email=user["email"],
                full_name=full_name,
                role=role,
            )


def main() -> None:
    seed_tenants()
    asyncio.run(provision_dev_staff())


if __name__ == "__main__":
    main()
