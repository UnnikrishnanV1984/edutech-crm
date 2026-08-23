"""End-to-end tenant-isolation test against a running `docker compose up`
stack — the exit criteria from DEVELOPMENT_PLAN.md §7, driven as real HTTP
requests through the real BFF -> FastAPI -> Postgres chain, not mocked.

Run after `docker compose up` (CI's isolation job does this; locally,
`docker compose up -d` then `pytest tests/` from the repo root). Skips
automatically if the BFF isn't reachable, so it doesn't break a bare
`pytest` run with no stack up.

Criterion 9 (token missing tenant_id -> 401) and the "unrecognized role"
case are deliberately NOT re-tested here — they require minting a token
with a controlled, non-standard claim set, which bff/src/__tests__/
auth.test.ts already covers directly against a local JWKS. This suite
covers what only a real Keycloak-issued token can prove: real claim
mapping, real signature verification, and the real header-stripping path
end to end.
"""

import os

import httpx
import pytest

KEYCLOAK_ISSUER_URL = os.environ.get(
    "KEYCLOAK_ISSUER_URL", "http://localhost:8080/realms/edutech-crm"
)
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "web")
BFF_BASE_URL = os.environ.get("BFF_BASE_URL", "http://localhost:4000")

TENANT_A_ID = "a1111111-1111-1111-1111-111111111111"
TENANT_B_ID = "b2222222-2222-2222-2222-222222222222"


def _stack_reachable() -> bool:
    try:
        r = httpx.get(f"{BFF_BASE_URL}/healthz", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_reachable(),
    reason=f"BFF not reachable at {BFF_BASE_URL} — bring up `docker compose up` first",
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
def token_a() -> str:
    return _fetch_token("counselor.a")


@pytest.fixture(scope="module")
def token_b() -> str:
    return _fetch_token("counselor.b")


def _me(token: str, extra_headers: dict | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(extra_headers or {})
    return httpx.get(f"{BFF_BASE_URL}/api/v1/me", headers=headers, timeout=10)


def test_valid_token_tenant_a_returns_tenant_a_data(token_a: str):
    response = _me(token_a)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["tenant"]["id"] == TENANT_A_ID
    assert body["data"]["user"]["email"] == "counselor.a@example.test"
    assert body["meta"]["request_id"]


def test_valid_token_tenant_b_returns_tenant_b_data_never_tenant_a(token_b: str):
    response = _me(token_b)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["tenant"]["id"] == TENANT_B_ID
    assert body["data"]["user"]["email"] == "counselor.b@example.test"
    # A logged-in user in tenant B must never see a field belonging to A.
    raw = response.text
    assert TENANT_A_ID not in raw
    assert "counselor.a@example.test" not in raw


def test_forged_tenant_and_role_headers_are_ignored(token_a: str):
    """DEVELOPMENT_PLAN.md §7 criterion 6 — a hand-forged X-Tenant-Id
    riding along with a genuine tenant-A token must not change the
    result. Proves the BFF strips/overrides client-supplied copies
    rather than blindly forwarding them (CLAUDE.md rule 7)."""
    response = _me(
        token_a,
        extra_headers={
            "X-Tenant-Id": TENANT_B_ID,
            "X-User-Role": "admin",
            "X-User-Id": "attacker-controlled-id",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["tenant"]["id"] == TENANT_A_ID
    assert body["data"]["user"]["role"] == "counselor"


def test_missing_token_returns_401_envelope():
    response = httpx.get(f"{BFF_BASE_URL}/api/v1/me", timeout=10)
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["meta"]["request_id"]


def test_tampered_signature_returns_401(token_a: str):
    """A structurally well-formed token whose signature no longer
    verifies (DEVELOPMENT_PLAN.md §7 criterion 8's spirit — a token not
    actually issued by our Keycloak's key) must be rejected."""
    header, payload, signature = token_a.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered_token = f"{header}.{payload}.{tampered_signature}"

    response = _me(tampered_token)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
