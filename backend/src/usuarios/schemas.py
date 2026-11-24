from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class CuentaStaffCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    # Ronda de correcciones (agosto 2026): opcional -- si se omite, el
    # servicio genera una contraseña segura automáticamente
    # (`security.generar_password_segura`) en vez de exigir que
    # `admin_sistema` la escriba a mano.
    password: str | None = Field(default=None, min_length=1, max_length=128)
    roles: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _requiere_telefono_o_email(self) -> "CuentaStaffCreate":
        if not self.telefono and not self.email:
            raise ValueError("La cuenta debe tener al menos un teléfono o un correo")
        return self


class UsuarioEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    forzar_cambio_password: bool | None = None


class RolesAsignar(BaseModel):
    roles: list[str] = Field(min_length=1)


class MotivoRequest(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


# Módulo 8.2 (Gobernanza de datos): doble confirmación real, no solo del
# lado del cliente -- el literal exige el texto exacto en el body, Pydantic
# rechaza con 422 cualquier otro valor antes de que el service se ejecute.
class AnonimizarConfirmar(BaseModel):
    confirmacion: Literal["ANONIMIZAR"]


class UsuarioOut(BaseModel):
    id: str
    nombre: str
    telefono: str | None
    email: str | None
    roles: list[str]
    estado: str
    fecha_registro: datetime
    forzar_cambio_password: bool
    motivo_suspension: str | None = None
    motivo_baja: str | None = None
    anonimizado: bool = False
    # Ronda de fotos en historial/usuarios: mismo campo general de
    # `usuarios.foto_url` que ya expone `PerfilOut` (autoservicio) --
    # Administración (Módulo 1, admin_sistema) también puede verla, no es un
    # dato más sensible que el nombre/teléfono que este mismo endpoint ya
    # expone a ese rol.
    foto_url: str | None = None


class UsuarioListOut(BaseModel):
    items: list[UsuarioOut]
    total: int


# Ronda de correcciones (agosto 2026): respuestas de "crear usuario" y
# "restablecer contraseña" -- extienden `UsuarioOut` con la contraseña en
# texto plano, visible SOLO en esta respuesta puntual (nunca se persiste ni
# se puede recuperar después, mismo criterio ya usado por
# `integraciones.CredencialCreadaOut` para el secreto de una credencial
# nueva). `password_generada` es `None` cuando `admin_sistema` mandó una
# contraseña propia en la creación en vez de pedir que se generara.
class UsuarioCreadoOut(UsuarioOut):
    password_generada: str | None = None


class PasswordRestablecidaOut(BaseModel):
    password_generada: str


class AccesoOut(BaseModel):
    ts: datetime
    accion: str
    resultado: str


class SesionOut(BaseModel):
    jti: str
    ip: str | None
    dispositivo: str | None
    ts_inicio: str | None


class MatrizPermisosOut(BaseModel):
    matriz: dict[str, list[str]]
