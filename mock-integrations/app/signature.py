"""Signs simulated webhook deliveries the same way a real Meta-platform
webhook signs them (X-Hub-Signature-256) — backend's verification code
checks against this same value, so the real verification path is
exercised, not bypassed (PHASE_2_PLAN.md §4.4)."""

import hashlib
import hmac


def sign(raw_body: bytes, app_secret: str) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
