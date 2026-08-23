"""Bootstrap roles and extensions

crm_migrate (the connecting/owning role, provisioned by the Postgres
container's POSTGRES_USER) already exists by the time this runs. This
migration creates crm_app — the least-privilege runtime role FastAPI
connects as — and grants it exactly SELECT/INSERT/UPDATE/DELETE, with
default privileges so future migrations' tables are automatically
grantable without repeating this per table.

crm_app is deliberately NOSUPERUSER / NOBYPASSRLS: FORCE ROW LEVEL
SECURITY (see DATABASE_SCHEMA.md §2) is meaningless against a role that
can bypass it. See DEVELOPMENT_PLAN.md §7 acceptance criterion 10.

Revision ID: 0001
Revises:
Create Date: 2026-08-23
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    app_user = os.environ.get("POSTGRES_APP_USER", "crm_app")
    app_password = os.environ["POSTGRES_APP_PASSWORD"]
    db_name = os.environ["POSTGRES_DB"]

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{app_user}') THEN
                CREATE ROLE {app_user}
                    WITH LOGIN PASSWORD {_quote_literal(app_password)}
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )

    op.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {app_user}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {app_user}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app_user}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE ON SEQUENCES TO {app_user}"
    )


def downgrade() -> None:
    app_user = os.environ.get("POSTGRES_APP_USER", "crm_app")
    db_name = os.environ["POSTGRES_DB"]

    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {app_user}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE USAGE ON SEQUENCES FROM {app_user}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {app_user}")
    op.execute(f"REVOKE ALL PRIVILEGES ON DATABASE {db_name} FROM {app_user}")
    op.execute(f"DROP ROLE IF EXISTS {app_user}")
