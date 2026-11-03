"""Esquemas Pydantic para mensagens privadas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ContactResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str


class ConversationCreateRequest(BaseModel):
    recipient_id: uuid.UUID


class MessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A mensagem não pode ficar em branco.")
        return stripped


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime
    # A outra pessoa da conversa já abriu a conversa depois desta mensagem.
    read_by_recipient: bool


class ConversationResponse(BaseModel):
    id: uuid.UUID
    other_user: ContactResponse
    last_message: MessageResponse | None
    unread_count: int
    last_message_at: datetime | None
    created_at: datetime
