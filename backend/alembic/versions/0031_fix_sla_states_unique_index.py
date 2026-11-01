"""Fix sla_states' broken uniqueness guard.

uq_sla_states_policy_target (migration 0012) is a plain btree unique index
on (tenant_id, sla_policy_id, deal_id, task_id). deal_id/task_id are each
NULL on exactly one side of every row (ck_sla_states_exactly_one_target),
and Postgres unique indexes treat NULL as distinct from NULL — so this
index has never actually rejected a duplicate (tenant, policy, deal) or
(tenant, policy, task) pair.

app/workers/sla.py's periodic upsert relies on this index via
ON CONFLICT (tenant_id, sla_policy_id, deal_id, task_id) to turn each
5-minute recomputation into an update. Since the index never conflicts,
every tick inserted a fresh row instead. Once two duplicate rows existed
for the same key, _upsert_sla_state's own pre-check
(`select(...).scalar_one_or_none()`) started raising MultipleResultsFound
and crashing the task for that tenant on every subsequent run — which
silently stopped all further SLA computation for any tenant that hit it,
confirmed against this environment's worker logs.

Fix: replace the index with one over COALESCE(deal_id, task_id, <sentinel>)
*only for the NULL side* — i.e. index on
(tenant_id, sla_policy_id, COALESCE(deal_id, zero_uuid), COALESCE(task_id,
zero_uuid)), where zero_uuid can never be a real deal_id/task_id, so two
rows now only collide when deal_id AND task_id both genuinely match (or
both are the same NULL-standing-in-for-sentinel). Existing duplicate rows
are deduped first (keep the most recently computed one), since the new
index can't be created over data that already violates it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SENTINEL = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # Keep the most-recently-computed row per real (tenant, policy, deal,
    # task) key, drop the rest — these are the duplicates created by the
    # broken index above, not meaningful history (sla_states is a current-
    # state table, never read as a log).
    op.execute(
        f"""
        DELETE FROM sla_states a USING sla_states b
        WHERE a.tenant_id = b.tenant_id
          AND a.sla_policy_id = b.sla_policy_id
          AND COALESCE(a.deal_id, '{_SENTINEL}') = COALESCE(b.deal_id, '{_SENTINEL}')
          AND COALESCE(a.task_id, '{_SENTINEL}') = COALESCE(b.task_id, '{_SENTINEL}')
          AND (a.computed_at, a.id) < (b.computed_at, b.id)
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_sla_states_policy_target")
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_sla_states_policy_target ON sla_states (
            tenant_id,
            sla_policy_id,
            COALESCE(deal_id, '{_SENTINEL}'),
            COALESCE(task_id, '{_SENTINEL}')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sla_states_policy_target")
    op.execute(
        "CREATE UNIQUE INDEX uq_sla_states_policy_target "
        "ON sla_states (tenant_id, sla_policy_id, deal_id, task_id)"
    )
