from datetime import datetime

from pydantic import BaseModel


class ArchivoOut(BaseModel):
    id: str
    nombre_original: str
    content_type: str
    tamano_bytes: int
    contexto: str
    propietario_id: str
    ts_creacion: datetime
