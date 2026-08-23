"""Header-validation behaviour of get_tenant_context that doesn't need a
real DB — these cases all short-circuit before any query runs."""

import uuid

import pytest

from app.core.errors import ApiError
from app.deps.tenant import get_tenant_context


async def _first(gen):
    return await gen.__anext__()


async def test_missing_tenant_id_raises_401():
    gen = get_tenant_context(x_tenant_id=None, x_user_id="user-1")
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "UNAUTHORIZED"


async def test_malformed_tenant_id_raises_401():
    gen = get_tenant_context(x_tenant_id="not-a-uuid", x_user_id="user-1")
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401


async def test_missing_user_id_raises_401():
    gen = get_tenant_context(x_tenant_id=str(uuid.uuid4()), x_user_id=None)
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401


async def test_missing_user_email_raises_401():
    gen = get_tenant_context(
        x_tenant_id=str(uuid.uuid4()), x_user_id="user-1", x_user_email=None
    )
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401


async def test_missing_user_role_raises_401():
    gen = get_tenant_context(
        x_tenant_id=str(uuid.uuid4()),
        x_user_id="user-1",
        x_user_email="a@example.test",
        x_user_role=None,
    )
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401


async def test_unrecognized_user_role_raises_401():
    gen = get_tenant_context(
        x_tenant_id=str(uuid.uuid4()),
        x_user_id="user-1",
        x_user_email="a@example.test",
        x_user_role="superadmin",
    )
    with pytest.raises(ApiError) as exc_info:
        await _first(gen)
    assert exc_info.value.status_code == 401
