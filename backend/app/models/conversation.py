"""Modelos de conversas privadas e mensagens.

Uma conversa direta (1:1) liga dois usuários da mesma escola. Cada
participante tem um registro em `ConversationParticipant` com o instante
até o qual leu a conversa (`last_read_at`). Com isso dá para calcular as
mensagens não lidas e o indicador "lida" sem criar uma linha por mensagem,
e o modelo já fica pronto para conversas em grupo no futuro.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutils import utc_now
from app.db.session import Base
from app.db.types import GUID


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("direct_key", name="uq_conversation_direct_key"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    # "<menor id>:<maior id>" nas conversas diretas: garante uma única conversa por par de usuários.
    direct_key: Mapped[str | None] = mapped_column(String(73), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participants: Mapped[list["ConversationParticipant"]] = relationship(
        "ConversationParticipant", cascade="all, delete-orphan", lazy="selectin"
    )


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nulo = nunca abriu a conversa; mensagens criadas até este instante contam como lidas.
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", lazy="joined")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Definido em Python (UTC, microssegundos) para ordenar e comparar com `last_read_at` de forma consistente.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
