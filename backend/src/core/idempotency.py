"""Middleware de `Idempotency-Key` — NFR de arquitectura_software.md línea 118:
"toda operación crítica acepta una clave de idempotencia (Idempotency-Key) —
creación de viaje, registro de pago, respuesta a oferta".

No es un middleware global obligatorio: solo actúa quien envía el header. Si
la misma clave se reenvía con el mismo cuerpo, se responde con la respuesta
ya emitida (replay) sin volver a ejecutar el efecto de negocio. Si se reenvía
con un cuerpo distinto, se rechaza con 409 — evita que un cliente reutilice
por error la clave de otra operación.
"""

import hashlib
import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.core.config import get_settings
from src.core.db_redis import get_redis

_HEADER = "Idempotency-Key"
_METHODS_WITH_EFFECT = {"POST", "PUT", "PATCH"}


def _cache_key(path: str, idem_key: str) -> str:
    return f"idempotency:{path}:{idem_key}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        idem_key = request.headers.get(_HEADER)
        if idem_key is None or request.method not in _METHODS_WITH_EFFECT:
            return await call_next(request)

        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()
        redis = get_redis()
        cache_key = _cache_key(request.url.path, idem_key)

        cached = await redis.get(cache_key)
        if cached is not None:
            stored = json.loads(cached)
            if stored["body_hash"] != body_hash:
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "IDEMPOTENCY_KEY_CONFLICT",
                        "message": "La Idempotency-Key ya fue usada con un cuerpo de petición distinto",
                    },
                )
            return JSONResponse(status_code=stored["status_code"], content=stored["body"])

        response = await call_next(request)

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        settings = get_settings()
        try:
            parsed_body = json.loads(response_body) if response_body else None
        except json.JSONDecodeError:
            parsed_body = None

        if parsed_body is not None:
            await redis.set(
                cache_key,
                json.dumps({"body_hash": body_hash, "status_code": response.status_code, "body": parsed_body}),
                ex=settings.idempotency_key_ttl_seconds,
            )

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
