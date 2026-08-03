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


def create_token(
    subject: str, roles: list[str], token_type: TokenType, extra_claims: dict[str, Any] | None = None
) -> str:
    # `roles` viaja en el token solo como referencia informativa/de depuración.
    # CU-O18 A3 exige que la autorización real se resuelva por consulta de perfil
    # en cada petición (ver core/rbac.py), no por lo que diga el token, para que
    # un cambio de rol o una revocación apliquen de inmediato sin esperar expiración.
    settings = get_settings()
    now = datetime.now(UTC)
    if token_type is TokenType.ACCESS:
        expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    else:
        expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "type": token_type.value,
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
