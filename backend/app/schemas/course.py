import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CourseCreate(BaseModel):
    name: str
    code: str


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    status: str
    created_at: datetime
    updated_at: datetime
