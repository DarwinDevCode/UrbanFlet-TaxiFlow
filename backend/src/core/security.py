import secrets
from datetime import datetime, timedelta, UTC
from enum import StrEnum
from typing import Any

import jwt
from passlib.context import CryptContext

from src.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


# Ronda de correcciones (agosto 2026): generador reusable para "crear usuario"
# y "restablecer contraseña" (Módulo 1 de admin_sistema) -- una sola
# implementación, no una copia por endpoint. Alfabeto sin ambigüedad visual
# (sin `0/O/1/l/I`) para que se pueda comunicar/transcribir a mano sin
# errores; se fuerza al menos una letra y un dígito con `secrets.choice`
# sobre cada grupo por separado (no basta con un alfabeto mixto -- una
# muestra aleatoria podría salir sin dígitos), y el resto se completa y
# mezcla con `secrets.SystemRandom` (mismo generador criptográfico que
# `secrets.token_urlsafe`, no `random`).
_ALFABETO_LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"
_ALFABETO_DIGITOS = "23456789"


def generar_password_segura(longitud: int = 14) -> str:
    if longitud < 2:
        raise ValueError("longitud debe permitir al menos una letra y un dígito")
    aleatorio = secrets.SystemRandom()
    caracteres = [aleatorio.choice(_ALFABETO_LETRAS), aleatorio.choice(_ALFABETO_DIGITOS)]
    resto = _ALFABETO_LETRAS + _ALFABETO_DIGITOS
    caracteres += [aleatorio.choice(resto) for _ in range(longitud - 2)]
    aleatorio.shuffle(caracteres)
    return "".join(caracteres)


def create_token(
    subject: str,
    roles: list[str],
    token_type: TokenType,
    extra_claims: dict[str, Any] | None = None,
    jti: str | None = None,
    access_ttl_minutos: int | None = None,
    refresh_ttl_dias: int | None = None,
) -> str:
    # `roles` viaja en el token solo como referencia informativa/de depuración.
    # CU-O18 A3 exige que la autorización real se resuelva por consulta de perfil
    # en cada petición (ver core/rbac.py), no por lo que diga el token, para que
    # un cambio de rol o una revocación apliquen de inmediato sin esperar expiración.
    #
    # Módulo 6.2 de admin_sistema: `access_ttl_minutos`/`refresh_ttl_dias` son
    # el TTL configurado en `seguridad.service` (política de seguridad, con
    # caché de 30s) -- si no se pasan (p. ej. contextos que no tocan Mongo),
    # cae a los valores fijos de `Settings`, que son el mismo default de la
    # política cuando nunca se publicó una versión.
    settings = get_settings()
    now = datetime.now(UTC)
    if token_type is TokenType.ACCESS:
        minutos = access_ttl_minutos if access_ttl_minutos is not None else settings.jwt_access_token_expire_minutes
        expires_at = now + timedelta(minutes=minutos)
    else:
        dias = refresh_ttl_dias if refresh_ttl_dias is not None else settings.jwt_refresh_token_expire_days
        expires_at = now + timedelta(days=dias)

    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "type": token_type.value,
        "iat": now,
        "exp": expires_at,
        "jti": jti or secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
