from typing import Literal

from pydantic import BaseModel, Field

Etiqueta = Literal["Casa", "Trabajo", "Otro"]


class DireccionCreate(BaseModel):
    etiqueta: Etiqueta
    direccion: str = Field(min_length=1, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DireccionOut(BaseModel):
    id: str
    etiqueta: Etiqueta
    direccion: str
    lat: float
    lon: float
