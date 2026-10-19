"""Esquemas Pydantic para autenticação."""
import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    school_id: uuid.UUID | None = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: str
    school_id: uuid.UUID | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user: Any) -> "UserResponse":
        """Constrói a resposta a partir do modelo ORM `User`.

        Necessário porque `User.role` é um relacionamento (objeto `Role`),
        enquanto a resposta expõe apenas o nome do papel como string.
        """
        return cls(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.name.value,
            school_id=user.school_id,
        )
