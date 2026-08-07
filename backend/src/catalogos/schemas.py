from typing import Literal

from pydantic import BaseModel, Field


class TipoDocumentoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(default="", max_length=500)
    aplica_a: Literal["conductor", "vehiculo", "ambos"] = "ambos"
    activo: bool = True


class TipoDocumentoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = Field(default=None, max_length=500)
    aplica_a: Literal["conductor", "vehiculo", "ambos"] | None = None
    activo: bool | None = None


class TipoDocumentoOut(BaseModel):
    id: str
    nombre: str
    descripcion: str
    aplica_a: Literal["conductor", "vehiculo", "ambos"]
    activo: bool


class MotivoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(default="", max_length=500)
    categoria: Literal["cancelacion", "incidencia"] = "cancelacion"
    activo: bool = True


class MotivoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = Field(default=None, max_length=500)
    categoria: Literal["cancelacion", "incidencia"] | None = None
    activo: bool | None = None


class MotivoOut(BaseModel):
    id: str
    nombre: str
    descripcion: str
    categoria: Literal["cancelacion", "incidencia"]
    activo: bool


# Punto #3 de la ronda de usabilidad de admin_sistema (2026-08-07): mismo
# hallazgo que motivó `tipos_documento`/`motivos_cancelacion` -- `taller`
# en `mantenimiento/schemas.py::OrdenCrearRequest`/`OrdenCerrarRequest` es
# texto libre sin catálogo, pese a que una cooperativa real trabaja con un
# conjunto finito y conocido de talleres asociados.
class TallerCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    direccion: str = Field(default="", max_length=300)
    telefono: str = Field(default="", max_length=20)
    activo: bool = True


class TallerEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=300)
    telefono: str | None = Field(default=None, max_length=20)
    activo: bool | None = None


class TallerOut(BaseModel):
    id: str
    nombre: str
    direccion: str
    telefono: str
    activo: bool
