"""pipeline_stage_templates — global, no tenant_id, no RLS. The `tenants`-
style exception (architect review, not the lead_source_connections-style
one): genuinely global content, not a bootstrapping-order problem. Safe
only because there is no tenant-facing write path to this table, ever —
the API for it (app/api/pipeline_stage_templates.py) is GET-only.
PIPELINE_AND_REVENUE_PLAN.md §4.6.

Also seeds the rows from PIPELINE_AND_REVENUE.md §2.6's table — platform
content, not dev-only fixture data (contrast with app/db/seed.py, which
never runs in production).

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_ROWS = [
    # (name, category, default_sort_order, is_won, is_lost,
    #  is_invoice_stage, is_rework_stage, default_win_probability_pct)
    ("Inquiry / Lead", "Generic", 1, False, False, False, False, 10),
    ("Qualification", "Generic", 2, False, False, False, False, 20),
    ("Demo Scheduled", "EdTech admissions", 3, False, False, False, False, 30),
    ("Proposal Sent", "B2B sales", 4, False, False, False, False, 40),
    ("Invoice Sent", "Generic", 5, False, False, True, False, 60),
    ("Invoice Rework", "Generic", 6, False, False, False, True, 50),
    ("Negotiation", "B2B sales", 7, False, False, False, False, 70),
    ("Payment Received / Enrolled / Won", "Generic", 8, True, False, False, False, 100),
    ("Lost / Dropped", "Generic", 9, False, True, False, False, 0),
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pipeline_stage_templates (
            id                          UUID NOT NULL DEFAULT gen_random_uuid(),
            name                        TEXT NOT NULL,
            category                    TEXT NOT NULL,
            default_sort_order          INTEGER NOT NULL,
            is_won                      BOOLEAN NOT NULL DEFAULT false,
            is_lost                     BOOLEAN NOT NULL DEFAULT false,
            is_invoice_stage            BOOLEAN NOT NULL DEFAULT false,
            is_rework_stage             BOOLEAN NOT NULL DEFAULT false,
            default_win_probability_pct INTEGER NOT NULL DEFAULT 0,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id)
        )
        """
    )
    # No tenant_id, no RLS — deliberate, see this migration's own
    # docstring. No FORCE ROW LEVEL SECURITY, no policy.

    insert_stmt = text(
        "INSERT INTO pipeline_stage_templates "
        "(name, category, default_sort_order, is_won, is_lost, is_invoice_stage, "
        " is_rework_stage, default_win_probability_pct) "
        "VALUES (:name, :category, :sort_order, :is_won, :is_lost, "
        "        :is_invoice_stage, :is_rework_stage, :win_pct)"
    )
    connection = op.get_bind()
    for (
        name,
        category,
        sort_order,
        is_won,
        is_lost,
        is_invoice_stage,
        is_rework_stage,
        win_pct,
    ) in _SEED_ROWS:
        connection.execute(
            insert_stmt,
            {
                "name": name,
                "category": category,
                "sort_order": sort_order,
                "is_won": is_won,
                "is_lost": is_lost,
                "is_invoice_stage": is_invoice_stage,
                "is_rework_stage": is_rework_stage,
                "win_pct": win_pct,
            },
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_stage_templates")
