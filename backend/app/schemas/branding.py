import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

AssetType = Literal["logo", "header", "favicon", "login_backdrop"]
HeaderBackground = Literal["light", "dark", "accent"]
Typeface = Literal["system", "serif"]

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class BrandingUploadUrlRequest(BaseModel):
    asset_type: AssetType
    filename: str
    content_type: str


class BrandingUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str


class BrandingConfirmRequest(BaseModel):
    asset_type: AssetType
    s3_key: str


class BrandingDraftUpdate(BaseModel):
    """PUT /api/v1/branding/draft — the non-asset fields only. Asset
    fields (logo/header/favicon/login_backdrop) go through upload-url +
    confirm, same as every other file upload in this app."""

    company_display_name: str | None = None
    accent_color: str | None = None
    header_background: HeaderBackground | None = None
    typeface: Typeface | None = None
    custom_domain: str | None = None

    @field_validator("accent_color")
    @classmethod
    def _check_accent_color(cls, value: str | None) -> str | None:
        if value is not None and not _HEX_COLOR.match(value):
            raise ValueError("accent_color must be a 6-digit hex color like #B68235")
        return value


class BrandingDraftOut(BaseModel):
    """The full mutable draft — admin-only. Distinct from BrandingOut
    (the live/published surface): a tenant can have an in-progress draft
    that has never been published, and this endpoint is the only place
    that draft is ever visible."""

    logo_url: str | None
    header_image_url: str | None
    favicon_url: str | None
    login_backdrop_url: str | None
    company_display_name: str | None
    accent_color: str | None
    header_background: HeaderBackground
    typeface: Typeface
    custom_domain: str | None
    updated_at: datetime | None


class BrandingOut(BaseModel):
    """The live/published surface — what the app shell, favicon, etc.
    actually render. Deliberately narrower than BrandingDraftOut:
    login_backdrop and custom_domain have no real live consumer (login
    backdrop only ever appears in the draft-side Login preview tab;
    custom_domain has no routing behavior at all), so they're left out
    here rather than returned and silently ignored by every caller."""

    logo_url: str | None
    header_image_url: str | None
    favicon_url: str | None
    company_display_name: str | None
    accent_color: str | None
    header_background: HeaderBackground
    typeface: Typeface
    updated_at: datetime | None


class BrandingVersionOut(BaseModel):
    id: str
    version_number: int
    published_by_name: str | None
    published_at: datetime
    is_live: bool
