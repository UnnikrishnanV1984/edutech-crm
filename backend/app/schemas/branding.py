from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AssetType = Literal["logo", "header"]


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


class BrandingOut(BaseModel):
    logo_url: str | None
    header_image_url: str | None
    updated_at: datetime | None
