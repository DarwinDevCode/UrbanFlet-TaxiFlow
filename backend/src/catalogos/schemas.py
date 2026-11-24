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
    # Ronda 1 (Ola 1.2): enlace a Google Maps -- texto validado como URL, sin
    # lat/lon ni mapa en esta ronda (evita llevar una librería de mapas a
    # web-interno, que hoy no monta ninguna, por un campo secundario -- ver
    # PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md §3.1).
    url_maps: str | None = Field(default=None, max_length=500)
    activo: bool = True


class TallerEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=300)
    telefono: str | None = Field(default=None, max_length=20)
    url_maps: str | None = Field(default=None, max_length=500)
    activo: bool | None = None


class TallerOut(BaseModel):
    id: str
    nombre: str
    direccion: str
    telefono: str
    url_maps: str | None = None
    activo: bool


# Ronda 1 (Ola 1.5): catálogos de marca/color de vehículo -- evidencia real
# de la auditoría (81 vehículos: 6 marcas y 7 colores concentran casi todo,
# con basura tipo "X"/"123"/"Z" en el resto). Consumidos por el formulario
# de postulación de web-conductor, que es PÚBLICO (sin sesión) -- por eso
# viven en catálogos propios en vez de sumarse a `motivos_cancelacion`, y
# por eso su lectura en el router es pública de verdad (sin Depends de
# actor), a diferencia de tipos_documento/motivos/talleres arriba.
class MarcaVehiculoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    activo: bool = True


class MarcaVehiculoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    activo: bool | None = None


class MarcaVehiculoOut(BaseModel):
    id: str
    nombre: str
    activo: bool


class ColorVehiculoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    activo: bool = True


class ColorVehiculoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    activo: bool | None = None


class ColorVehiculoOut(BaseModel):
    id: str
    nombre: str
    activo: bool


# Ola 3 de PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md (§3.2) -- catálogo de
# repuestos, antes aplazado por falta de evidencia de repetición ("solo 3
# entradas humanas reales"), decisión ya tomada de avanzar igual. A
# diferencia de lo que proponía ese documento (que recomendaba NO incluir
# precio en el maestro, para no confundirlo con el costo real de compra),
# esta ronda sí lo incluye a pedido explícito: `precio_referencial` es solo
# un punto de partida sugerido -- `costo_unitario` en la línea de la orden
# (mantenimiento/schemas.py::RepuestoInput) sigue siendo el precio real,
# editable sin restricción, nunca se sobrescribe con este valor después de
# precargarlo.
CategoriaRepuesto = Literal["Motor", "Frenos", "Eléctrico", "Suspensión", "Neumáticos", "Otro"]
UnidadRepuesto = Literal["unidad", "litro", "juego"]


class RepuestoCatalogoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    categoria: CategoriaRepuesto = "Otro"
    precio_referencial: float = Field(ge=0)
    unidad: UnidadRepuesto = "unidad"
    activo: bool = True


class RepuestoCatalogoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    categoria: CategoriaRepuesto | None = None
    precio_referencial: float | None = Field(default=None, ge=0)
    unidad: UnidadRepuesto | None = None
    activo: bool | None = None


class RepuestoCatalogoOut(BaseModel):
    id: str
    nombre: str
    categoria: CategoriaRepuesto
    precio_referencial: float
    unidad: UnidadRepuesto
    activo: bool
