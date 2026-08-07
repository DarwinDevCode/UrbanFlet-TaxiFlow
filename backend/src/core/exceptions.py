class DomainError(Exception):
    """Error de negocio con código estable para el cliente, distinto de un 500 genérico."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuditWriteError(DomainError):
    """La bitácora no pudo escribirse: por CU-O17, la operación de negocio que la
    origina debe fallar (write-ahead). Nunca se atrapa en silencio en un módulo
    de dominio — debe propagar hasta abortar la transacción de negocio."""

    def __init__(self, message: str = "No se pudo registrar el evento de auditoría") -> None:
        super().__init__(code="AUDIT_WRITE_FAILED", message=message, status_code=503)


class InsufficientRoleError(DomainError):
    def __init__(self, message: str = "El rol del actor no tiene permiso para esta operación") -> None:
        super().__init__(code="INSUFFICIENT_ROLE", message=message, status_code=403)


class SessionSuspendedError(DomainError):
    def __init__(self, message: str = "Sesión suspendida por intentos de acceso denegados repetidos") -> None:
        super().__init__(code="SESSION_SUSPENDED", message=message, status_code=403)


class InvalidCredentialsError(DomainError):
    def __init__(self, message: str = "Credenciales inválidas") -> None:
        super().__init__(code="INVALID_CREDENTIALS", message=message, status_code=401)


class TooManyLoginAttemptsError(DomainError):
    def __init__(self, message: str = "Demasiados intentos fallidos; la cuenta quedó bloqueada temporalmente") -> None:
        super().__init__(code="TOO_MANY_LOGIN_ATTEMPTS", message=message, status_code=429)


class WeakPasswordError(DomainError):
    def __init__(self, longitud_minima: int) -> None:
        super().__init__(
            code="WEAK_PASSWORD",
            message=f"La contraseña debe tener al menos {longitud_minima} caracteres (política vigente)",
            status_code=422,
        )


class IdempotencyConflictError(DomainError):
    def __init__(self, message: str = "La Idempotency-Key ya fue usada con un cuerpo de petición distinto") -> None:
        super().__init__(code="IDEMPOTENCY_KEY_CONFLICT", message=message, status_code=409)
