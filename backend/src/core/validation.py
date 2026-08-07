"""Traduce los errores 422 crudos de Pydantic/FastAPI a un formato legible y
consistente para el cliente -- punto #1 de la ronda de usabilidad de
admin_sistema (2026-08-07): un 422 real llegaba a la interfaz sin ningún
mensaje (`ApiError` caía a `response.statusText`, un genérico "Unprocessable
Entity" en inglés) porque el handler por defecto de FastAPI devuelve
`{"detail": [...]}`, una forma que `apps/shared-ui/src/api/client.ts` nunca
supo interpretar. Este módulo normaliza esa forma a la misma que ya usan los
`DomainError` de negocio (`{"code", "message"}`), sumando un array `errores`
por campo para que el frontend pueda mostrar el mensaje junto al input que
lo causó, no solo en un banner genérico.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Traducciones de los `type` de error más comunes que Pydantic v2 produce.
# `ctx` trae los parámetros del error (ge/le/min_length/etc.) cuando aplica.
_MENSAJES: dict[str, str] = {
    "missing": "Este campo es obligatorio",
    "greater_than_equal": "Debe ser mayor o igual a {ge}",
    "less_than_equal": "Debe ser menor o igual a {le}",
    "greater_than": "Debe ser mayor a {gt}",
    "less_than": "Debe ser menor a {lt}",
    "string_too_short": "Debe tener al menos {min_length} caracteres",
    "string_too_long": "No puede superar los {max_length} caracteres",
    "int_parsing": "Debe ser un número entero",
    "float_parsing": "Debe ser un número",
    "bool_parsing": "Debe ser verdadero o falso",
    "string_type": "Debe ser texto",
    "literal_error": "Valor no permitido — opciones válidas: {expected}",
    "enum": "Valor no permitido — opciones válidas: {expected}",
    "value_error": "Valor inválido",
    "extra_forbidden": "Campo no reconocido",
}


def _traducir(error: dict) -> str:
    tipo = error.get("type", "")
    plantilla = _MENSAJES.get(tipo)
    if plantilla is None:
        return error.get("msg", "Valor inválido")
    try:
        return plantilla.format(**error.get("ctx", {}))
    except (KeyError, IndexError):
        return error.get("msg", "Valor inválido")


def _nombre_campo(loc: tuple) -> str:
    # loc típico: ("body", "umbral_intentos_fallidos") o ("query", "limit").
    # Se descarta el primer segmento (ubicación: body/query/path), el resto
    # es el nombre real del campo tal como lo conoce el formulario.
    partes = [str(p) for p in loc[1:]] or [str(loc[-1])]
    return ".".join(partes)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [{"campo": _nombre_campo(e["loc"]), "mensaje": _traducir(e)} for e in exc.errors()]
    if len(errores) == 1:
        mensaje = f"{errores[0]['campo']}: {errores[0]['mensaje']}"
    else:
        mensaje = "Hay " + str(len(errores)) + " campos con datos inválidos"
    return JSONResponse(status_code=422, content={"code": "VALIDATION_ERROR", "message": mensaje, "errores": errores})
