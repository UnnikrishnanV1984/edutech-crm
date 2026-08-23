"""Pure-logic tests only — the _trigger endpoints additionally need a
reachable backend and are exercised by backend/tests/test_webhooks_*.py
instead, run with both services live (matching this repo's existing
skip-cleanly-if-unreachable convention for cross-service tests)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_get_leadgen_returns_fixture():
    response = client.get("/meta/v18.0/990211000000001")
    assert response.status_code == 200
    assert response.json()["field_data"][0]["values"][0] == "Meera Iyer"


def test_get_leadgen_unknown_id_is_404():
    assert client.get("/meta/v18.0/does-not-exist").status_code == 404


def test_google_leads_requires_bearer_token():
    assert client.get("/google/customers/123/leads").status_code == 401
    response = client.get("/google/customers/123/leads", headers={"Authorization": "Bearer x"})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_google_oauth_token_exchange_returns_tokens():
    response = client.post("/google/oauth/token", json={"refresh_token": "mock-refresh"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"] == "mock-refresh"
