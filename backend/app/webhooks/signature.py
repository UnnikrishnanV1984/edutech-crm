"""Shared HMAC-SHA256 verification for Meta-platform webhooks (Meta Lead
Ads and WhatsApp Cloud API both sign with X-Hub-Signature-256 the same
way — PHASE_2_PLAN.md §3). Verified before any DB/tenant-resolution work
in every caller."""

import hashlib
import hmac


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    provided = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
