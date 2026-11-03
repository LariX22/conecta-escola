"""Esquemas Pydantic para turmas, matrículas e atribuições de professores."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ClassroomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    segment: str = Field(min_length=1, max_length=100)
    school_year: int = Field(ge=2000, le=2100)


class ClassroomResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    segment: str
    school_year: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollmentCreateRequest(BaseModel):
    student_id: uuid.UUID


class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TeacherAssignmentCreateRequest(BaseModel):
    teacher_id: uuid.UUID


class TeacherAssignmentResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    classroom_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
