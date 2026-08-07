from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NombreServicio = Literal["google_maps", "sms", "s3"]


class CredencialCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    alcance: str = Field(default="", max_length=500)


class CredencialCreadaOut(BaseModel):
    id: str
    nombre: str
    # Único momento en que el secreto viaja en claro -- después de esta
    # respuesta, solo existe su hash. Si se pierde, la única opción es
    # revocar y crear una credencial nueva (nunca "recuperar" la anterior).
    secreto: str
    alcance: str
    vigente_desde: datetime


class CredencialOut(BaseModel):
    id: str
    nombre: str
    alcance: str
    vigente_desde: datetime
    vigente_hasta: datetime | None
    revocada: bool
    # Siempre 0 -- no existe ningún endpoint /ext/v1/... que consuma estas
    # credenciales todavía (confirmado, no asumido: ver PLAN_ADMIN_SISTEMA.md).
    # Se expone igual, con este campo, para que la UI lo muestre honesto en
    # vez de omitirlo en silencio.
    usos_registrados: int


class ServicioExternoOut(BaseModel):
    nombre: NombreServicio
    estado: Literal["activo", "no_configurado"]
    key_enmascarada: str | None


class RotarKeyRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=200)
