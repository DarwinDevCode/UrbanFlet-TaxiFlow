from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    # La longitud mínima real la exige el servicio contra la política de
    # autenticación vigente (Módulo 1.3, admin_sistema) -- este min_length=1
    # es solo "no vacío", no la regla de negocio.
    password: str = Field(min_length=1, max_length=128)

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
    # Módulo 1.1/1.3 (admin_sistema): un administrador forzó el cambio de
    # contraseña (edición de cuenta) o la política exige renovación
    # periódica para roles de alto privilegio y ya venció -- el frontend
    # debe bloquear la navegación normal hasta que se llame a
    # POST /auth/cambiar-password.
    debe_cambiar_password: bool = False


class LoginRequest(BaseModel):
    identificador: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class CambiarPasswordRequest(BaseModel):
    password_actual: str = Field(min_length=1)
    password_nueva: str = Field(min_length=1, max_length=128)
