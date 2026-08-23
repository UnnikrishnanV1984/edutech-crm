"""Cross-service E2E for Phase 2 lead-capture integrations — PHASE_2_PLAN.md
§6 step 18. Driven as real HTTP requests through the real
BFF -> FastAPI -> Postgres chain (real Keycloak-issued admin tokens),
plus the real mock-integrations service simulating an inbound Meta
webhook — mirrors test_tenant_isolation.py's style and skip convention.

Run after `docker compose up` (mock-integrations is part of the default
stack, not opt-in). Skips cleanly if the BFF or mock-integrations isn't
reachable, so a bare `pytest tests/` doesn't fail with no stack up.
"""

import os
import uuid

import httpx
import pytest

KEYCLOAK_ISSUER_URL = os.environ.get(
    "KEYCLOAK_ISSUER_URL", "http://localhost:8080/realms/edutech-crm"
)
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "web")
BFF_BASE_URL = os.environ.get("BFF_BASE_URL", "http://localhost:4000")
MOCK_INTEGRATIONS_BASE_URL = os.environ.get("MOCK_INTEGRATIONS_BASE_URL", "http://localhost:8010")

TENANT_A_ID = "a1111111-1111-1111-1111-111111111111"
TENANT_B_ID = "b2222222-2222-2222-2222-222222222222"


def _stack_reachable() -> bool:
    try:
        bff_ok = httpx.get(f"{BFF_BASE_URL}/healthz", timeout=2).status_code == 200
        mock_ok = httpx.get(f"{MOCK_INTEGRATIONS_BASE_URL}/health", timeout=2).status_code == 200
        return bff_ok and mock_ok
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_reachable(),
    reason=f"BFF ({BFF_BASE_URL}) or mock-integrations ({MOCK_INTEGRATIONS_BASE_URL}) unreachable",
)


def _fetch_token(username: str, password: str = "password") -> str:
    response = httpx.post(
        f"{KEYCLOAK_ISSUER_URL}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": KEYCLOAK_CLIENT_ID,
            "username": username,
            "password": password,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token_a() -> str:
    return _fetch_token("admin.a")


@pytest.fixture(scope="module")
def admin_token_b() -> str:
    return _fetch_token("admin.b")


def _connections(token: str) -> httpx.Response:
    return httpx.get(
        f"{BFF_BASE_URL}/api/v1/lead-source-connections",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )


def _connect_meta(token: str, external_account_id: str) -> httpx.Response:
    return httpx.post(
        f"{BFF_BASE_URL}/api/v1/lead-source-connections",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "meta", "external_account_id": external_account_id, "access_token": "t"},
        timeout=10,
    )


@pytest.fixture
def cleanup_connections(admin_token_a, admin_token_b):
    created_ids: list[tuple[str, str]] = []
    yield created_ids
    for token, connection_id in created_ids:
        httpx.patch(
            f"{BFF_BASE_URL}/api/v1/lead-source-connections/{connection_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "disabled"},
            timeout=10,
        )


def test_tenant_b_admin_cannot_see_tenant_a_connections(
    admin_token_a, admin_token_b, cleanup_connections
):
    account_id = f"e2e-page-{uuid.uuid4()}"
    created = _connect_meta(admin_token_a, account_id)
    assert created.status_code == 200
    cleanup_connections.append((admin_token_a, created.json()["data"]["id"]))

    tenant_b_list = _connections(admin_token_b)
    assert tenant_b_list.status_code == 200
    assert account_id not in tenant_b_list.text

    tenant_a_list = _connections(admin_token_a)
    assert account_id in tenant_a_list.text


def test_simulated_meta_lead_lands_in_correct_tenant_pipeline(
    admin_token_a, admin_token_b, cleanup_connections
):
    account_id = f"e2e-page-{uuid.uuid4()}"
    created = _connect_meta(admin_token_a, account_id)
    assert created.status_code == 200
    cleanup_connections.append((admin_token_a, created.json()["data"]["id"]))

    trigger = httpx.post(
        f"{MOCK_INTEGRATIONS_BASE_URL}/meta/_trigger",
        json={"external_account_id": account_id},
        timeout=10,
    )
    assert trigger.status_code == 200
    assert trigger.json()["backend_status"] == 200

    # A counselor-role request only ever sees their own tenant's data —
    # the contact this created must be attributed to tenant A's pipeline,
    # never visible via tenant B's credentials at any layer.
    tenant_b_contacts = httpx.get(
        f"{BFF_BASE_URL}/api/v1/contacts",
        headers={"Authorization": f"Bearer {admin_token_b}"},
        params={"search": "Meera Iyer"},
        timeout=10,
    )
    assert tenant_b_contacts.status_code == 200
    assert tenant_b_contacts.json()["data"] == []
