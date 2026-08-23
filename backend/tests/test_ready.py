import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")


def _db_reachable() -> bool:
    if not DATABASE_URL:
        return False
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="DATABASE_URL not set or Postgres unreachable"
)


def test_ready_ok():
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
