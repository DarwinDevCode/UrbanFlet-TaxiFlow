from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _requiere_telefono_o_email(self) -> "RegistroRequest":
        if not self.telefono and not self.email:
            raise ValueError("Debes registrarte con al menos un teléfono o un correo")
        return self


class RegistroResponse(BaseModel):
    usuario_id: str
    telefono: str | None
    estado: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class LoginRequest(BaseModel):
    identificador: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str
