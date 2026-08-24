"""Phase 1 tenant-isolation E2E — direct-ID-guess attempts against the new
resources (contacts, deals, tasks) from the wrong tenant, driven as real
HTTP requests through the live BFF -> FastAPI -> Postgres chain. Extends
test_tenant_isolation.py's pattern (PHASE_1_PLAN.md §7 step 22) rather than
duplicating its token-fetching setup — see that file for why criterion 9
and the unrecognized-role case are covered at the BFF unit-test level
instead of here.

Documents are deliberately NOT covered in this file: the compose stack's
minio service is opt-in (`docker compose --profile storage up`, per
ARCHITECTURE.md §5) and CI's compose-isolation job doesn't start it, so a
document-upload test here would just fail on missing infrastructure, not
prove anything. Document tenant-scoping (the s3_key prefix check, and RLS
on the documents table itself) is already covered directly at the backend
pytest level (test_documents_endpoint.py), gated on real MinIO
reachability the same way this file is gated on the BFF.
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_contact_as_a(token_a: str) -> str:
    # This test module runs against the live BFF/FastAPI/Postgres chain
    # (see module docstring) and has no teardown, so each run's contacts
    # are real, permanent rows in the local dev DB. A unique suffix per
    # call keeps repeated local runs from being indistinguishable from
    # each other in the dev UI — it does not delete anything itself; run
    # `docker compose exec db psql ...` (or equivalent) periodically if
    # accumulated test data needs clearing.
    response = httpx.post(
        f"{BFF_BASE_URL}/api/v1/contacts",
        json={
            "full_name": f"Isolation Test Contact {uuid.uuid4().hex[:8]}",
            "lead_source": "manual",
        },
        headers=_headers(token_a),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def _create_course_as_a(token_a: str) -> str:
    response = httpx.post(
        f"{BFF_BASE_URL}/api/v1/courses",
        json={"name": "Isolation Test Course", "code": f"ISO-{uuid.uuid4().hex[:8]}"},
        headers=_headers(token_a),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def _create_deal_as_a(token_a: str, contact_id: str, course_id: str) -> str:
    response = httpx.post(
        f"{BFF_BASE_URL}/api/v1/contacts/{contact_id}/deals",
        json={"course_id": course_id},
        headers=_headers(token_a),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def _create_task_as_a(token_a: str, contact_id: str) -> str:
    response = httpx.post(
        f"{BFF_BASE_URL}/api/v1/tasks",
        json={"contact_id": contact_id, "title": "Isolation test task"},
        headers=_headers(token_a),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]["id"]


def test_tenant_b_gets_404_guessing_tenant_a_contact_id(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    response = httpx.get(
        f"{BFF_BASE_URL}/api/v1/contacts/{contact_id}", headers=_headers(token_b), timeout=10
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_tenant_b_cannot_patch_tenant_a_contact(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    response = httpx.patch(
        f"{BFF_BASE_URL}/api/v1/contacts/{contact_id}",
        json={"full_name": "Hijacked"},
        headers=_headers(token_b),
        timeout=10,
    )
    assert response.status_code == 404


def test_tenant_b_contacts_list_never_includes_tenant_a_ids(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    response = httpx.get(
        f"{BFF_BASE_URL}/api/v1/contacts?page_size=100", headers=_headers(token_b), timeout=10
    )
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()["data"]]
    assert contact_id not in ids


def test_tenant_b_gets_404_guessing_tenant_a_deal_id(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    course_id = _create_course_as_a(token_a)
    deal_id = _create_deal_as_a(token_a, contact_id, course_id)

    response = httpx.get(
        f"{BFF_BASE_URL}/api/v1/deals/{deal_id}", headers=_headers(token_b), timeout=10
    )
    assert response.status_code == 404


def test_tenant_b_cannot_change_tenant_a_deal_stage(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    course_id = _create_course_as_a(token_a)
    deal_id = _create_deal_as_a(token_a, contact_id, course_id)

    stages_b = httpx.get(
        f"{BFF_BASE_URL}/api/v1/pipeline-stages", headers=_headers(token_b), timeout=10
    ).json()["data"]

    response = httpx.patch(
        f"{BFF_BASE_URL}/api/v1/deals/{deal_id}",
        json={"stage_id": stages_b[1]["id"]},  # a tenant-B stage id, wrong deal
        headers=_headers(token_b),
        timeout=10,
    )
    assert response.status_code == 404


def test_tenant_b_gets_404_guessing_tenant_a_task_id(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    task_id = _create_task_as_a(token_a, contact_id)

    response = httpx.get(
        f"{BFF_BASE_URL}/api/v1/tasks/{task_id}", headers=_headers(token_b), timeout=10
    )
    assert response.status_code == 404


def test_tenant_b_cannot_complete_tenant_a_task(token_a: str, token_b: str):
    contact_id = _create_contact_as_a(token_a)
    task_id = _create_task_as_a(token_a, contact_id)

    response = httpx.patch(
        f"{BFF_BASE_URL}/api/v1/tasks/{task_id}",
        json={"status": "done"},
        headers=_headers(token_b),
        timeout=10,
    )
    assert response.status_code == 404

    # Confirm it's still open when read back by its own tenant.
    check = httpx.get(
        f"{BFF_BASE_URL}/api/v1/tasks/{task_id}", headers=_headers(token_a), timeout=10
    )
    assert check.json()["data"]["status"] == "open"


def test_pipeline_stages_are_independent_per_tenant(token_a: str, token_b: str):
    """A tenant-B stage id is a real, valid stage — just not for tenant A's
    deals (test_tenant_b_cannot_change_tenant_a_deal_stage above already
    proves that). This proves the reverse isn't true either: tenant A
    can't see or rename a tenant-B stage by guessing its id."""
    stages_b = httpx.get(
        f"{BFF_BASE_URL}/api/v1/pipeline-stages", headers=_headers(token_b), timeout=10
    ).json()["data"]
    stage_b_id = stages_b[0]["id"]

    response = httpx.patch(
        f"{BFF_BASE_URL}/api/v1/pipeline-stages/{stage_b_id}",
        json={"name": "Hijacked"},
        headers=_headers(token_a),
        timeout=10,
    )
    assert response.status_code == 404
