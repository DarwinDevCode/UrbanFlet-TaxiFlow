"""PyMongo/mongomock devuelven datetimes naive (BSON no guarda tzinfo); todo
lo que este backend persiste ya está en UTC (regla de arquitectura, línea
122), así que reetiquetar sin convertir es correcto — nunca hay que restar o
sumar horas al leer de vuelta un timestamp guardado por esta misma app."""

from datetime import UTC, datetime


def como_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
