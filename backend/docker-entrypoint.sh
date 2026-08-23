#!/bin/sh
set -e

alembic upgrade head

# Never seed synthetic tenants outside local dev.
if [ "$ENVIRONMENT" = "development" ]; then
    python -m app.db.seed
fi

exec "$@"
