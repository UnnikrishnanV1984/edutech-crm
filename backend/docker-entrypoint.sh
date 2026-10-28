#!/bin/sh
set -e

alembic upgrade head

# Never seed synthetic tenants or sample lead data outside local dev.
if [ "$ENVIRONMENT" = "development" ]; then
    python -m app.db.seed
    python -m app.connectors.seed_runner
    python -m app.db.seed_ops_data
    python -m app.db.seed_volume
fi

exec "$@"
