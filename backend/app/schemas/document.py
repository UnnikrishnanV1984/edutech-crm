import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str


class DocumentCreate(BaseModel):
    deal_id: uuid.UUID | None = None
    filename: str
    content_type: str
    size_bytes: int
    s3_key: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    deal_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: uuid.UUID
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    download_url: str
