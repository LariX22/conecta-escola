"""Esquemas Pydantic para comunicados e confirmações de leitura."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    audience: Literal["school", "classrooms"]
    classroom_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    requires_confirmation: bool = False
    # Com fuso horário obrigatório (ex.: 2026-11-10T08:00:00-03:00); omitido = publicar agora.
    publish_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def check_audience(self) -> "AnnouncementCreateRequest":
        if self.audience == "classrooms" and not self.classroom_ids:
            raise ValueError("Informe ao menos uma turma para comunicados de turma.")
        if self.audience == "school" and self.classroom_ids:
            raise ValueError("Comunicados para toda a escola não aceitam turmas.")
        return self


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)

    @model_validator(mode="after")
    def check_has_changes(self) -> "AnnouncementUpdateRequest":
        if self.title is None and self.body is None:
            raise ValueError("Informe ao menos um campo para alterar (title ou body).")
        return self


class AnnouncementResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    title: str
    body: str
    audience: Literal["school", "classrooms"]
    classroom_ids: list[uuid.UUID]
    requires_confirmation: bool
    publish_at: datetime
    status: Literal["scheduled", "published"]
    created_at: datetime
    updated_at: datetime
    # Quando o responsável autenticado confirmou a leitura (nulo para os demais perfis).
    my_read_at: datetime | None = None


class AnnouncementReadResponse(BaseModel):
    announcement_id: uuid.UUID
    user_id: uuid.UUID
    read_at: datetime

    model_config = {"from_attributes": True}


class RecipientReadStatus(BaseModel):
    guardian_id: uuid.UUID
    guardian_name: str
    read_at: datetime | None


class AnnouncementReadReport(BaseModel):
    announcement_id: uuid.UUID
    requires_confirmation: bool
    recipient_count: int
    read_count: int
    pending_count: int
    recipients: list[RecipientReadStatus]
