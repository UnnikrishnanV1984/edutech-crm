from typing import Any


def data_envelope(data: Any, request_id: str, extra_meta: dict | None = None) -> dict:
    meta = {"request_id": request_id, **(extra_meta or {})}
    return {"data": data, "meta": meta}


def collection_envelope(
    items: list,
    request_id: str,
    page: int,
    page_size: int,
    total: int,
) -> dict:
    return {
        "data": items,
        "meta": {
            "request_id": request_id,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }


def error_envelope(
    code: str,
    message: str,
    request_id: str,
    details: list[dict] | None = None,
) -> dict:
    error: dict = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error, "meta": {"request_id": request_id}}
