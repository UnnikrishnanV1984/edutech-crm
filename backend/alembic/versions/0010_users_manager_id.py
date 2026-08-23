"""users.manager_id — RBAC team mapping

Nullable self-referencing composite FK, same shape as every other
(x_id, tenant_id) REFERENCES table (id, tenant_id) pattern in this
schema. A Staff user with no manager_id set has no manager (an admin
must assign one via PATCH /api/v1/users/{id}). This IS the
manager-to-team mapping (REQUIREMENTS.md §5.3) — no separate mapping
table. See PHASE_3_PLAN.md §3.1.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN manager_id UUID NULL")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_manager_id_fkey "
        "FOREIGN KEY (manager_id, tenant_id) REFERENCES users (id, tenant_id)"
    )
    op.execute("CREATE INDEX idx_users_tenant_manager ON users (tenant_id, manager_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_tenant_manager")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_manager_id_fkey")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS manager_id")
