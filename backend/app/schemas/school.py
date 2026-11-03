"""Esquemas Pydantic para escolas (tenants)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SchoolCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class SchoolResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
