"""Esquemas Pydantic para alunos e vínculos com responsáveis."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class StudentCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    birth_date: date | None = None


class StudentUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    birth_date: date | None = None
    is_active: bool | None = None


class StudentResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    full_name: str
    birth_date: date | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardianLinkCreateRequest(BaseModel):
    guardian_id: uuid.UUID
    relationship_label: str = Field(min_length=2, max_length=50)


class GuardianLinkResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    guardian_id: uuid.UUID
    relationship_label: str
    created_at: datetime

    model_config = {"from_attributes": True}
