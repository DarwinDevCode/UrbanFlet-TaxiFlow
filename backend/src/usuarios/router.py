from datetime import datetime, UTC

import secrets

from fastapi import APIRouter, Depends, Header, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.config import get_settings
from src.core.db_mongo import get_database
from src.core.exceptions import DomainError
from src.core.rbac import Actor, require_roles
from src.usuarios import permisos_matriz, schemas, service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

# Módulo 1 (IAM) es de alto privilegio -- exclusivo de admin_sistema, sin
# roles combinados (nota de seguridad de la spec, distinta de la mayoría de
# los demás routers del proyecto que sí comparten acceso entre 2-3 roles).
_admin_sistema = require_roles("admin_sistema")


class TokenInternoInvalidoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="TOKEN_INTERNO_INVALIDO", message="Token interno inválido", status_code=401)


async def _verificar_token_interno(x_internal_token: str | None = Header(default=None)) -> None:
    """Mismo mecanismo que ya usa `viajes/router_trips.py` para el disparo de
    viajes programados desde Airflow -- no se inventa un segundo esquema de
    autenticación máquina-a-máquina."""
    esperado = get_settings().internal_api_token
    if not x_internal_token or not secrets.compare_digest(x_internal_token, esperado):
        raise TokenInternoInvalidoError()

# Hallazgo real (Módulo de usabilidad, punto #5, 2026-08-07): al construir
# el buscador de usuarios de `UserPicker`, una búsqueda por texto real
# reventó este endpoint con `KeyError: 'fecha_registro'` -- 5 cuentas de
# demo/QA (incluida `staff-verificacion`) fueron insertadas directo en
# Mongo en sesiones anteriores sin ese campo, antes de que
# `crear_cuenta_staff` lo hiciera obligatorio. Ya se backfillearon esas 5
# cuentas (ver `backend/scripts/backfill_fecha_registro.py`), pero este
# fallback queda como defensa real contra cualquier documento futuro en la
# misma situación -- no debe volver a tumbar el listado completo.
_FECHA_REGISTRO_DESCONOCIDA = datetime(2020, 1, 1, tzinfo=UTC)


def _to_out(u: dict) -> schemas.UsuarioOut:
    return schemas.UsuarioOut(
        id=u["_id"],
        nombre=u["nombre"],
        telefono=u.get("telefono"),
        email=u.get("email"),
        roles=u.get("roles", []),
        estado=u["estado"],
        fecha_registro=u.get("fecha_registro", _FECHA_REGISTRO_DESCONOCIDA),
        forzar_cambio_password=bool(u.get("forzar_cambio_password")),
        motivo_suspension=u.get("motivo_suspension"),
        motivo_baja=u.get("motivo_baja"),
        anonimizado=bool(u.get("anonimizado")),
        foto_url=u.get("foto_url"),
    )


@router.post("", response_model=schemas.UsuarioCreadoOut, status_code=201)
async def crear_cuenta(
    body: schemas.CuentaStaffCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario, password_generada = await service.crear_cuenta_staff(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        nombre=body.nombre,
        telefono=body.telefono,
        email=body.email,
        password=body.password,
        roles=body.roles,
    )
    return schemas.UsuarioCreadoOut(**_to_out(usuario).model_dump(), password_generada=password_generada)


@router.post("/{usuario_id}/restablecer-password", response_model=schemas.PasswordRestablecidaOut)
async def restablecer_password(
    usuario_id: str,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Genera una contraseña nueva para un usuario existente, visible una
    sola vez en esta respuesta. El usuario deberá cambiarla en su próximo
    login (`forzar_cambio_password`), mismo mecanismo ya usado al crear una
    cuenta nueva."""
    password_generada = await service.restablecer_password(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id
    )
    return schemas.PasswordRestablecidaOut(password_generada=password_generada)


@router.get("", response_model=schemas.UsuarioListOut)
async def listar(
    rol: str | None = None,
    estado: str | None = None,
    texto: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await service.listar_usuarios(db, rol=rol, estado=estado, texto=texto, limit=limit, offset=offset)
    return schemas.UsuarioListOut(items=[_to_out(u) for u in items], total=total)


@router.get("/matriz-permisos", response_model=schemas.MatrizPermisosOut)
async def matriz_permisos(actor: Actor = Depends(_admin_sistema)):
    return schemas.MatrizPermisosOut(matriz=permisos_matriz.obtener_matriz())


@router.get("/{usuario_id}", response_model=schemas.UsuarioOut)
async def obtener(
    usuario_id: str, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    usuario = await service.obtener_usuario(db, usuario_id)
    return _to_out(usuario)


@router.patch("/{usuario_id}", response_model=schemas.UsuarioOut)
async def editar(
    usuario_id: str,
    body: schemas.UsuarioEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    usuario = await service.editar_usuario(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id, cambios=cambios
    )
    return _to_out(usuario)


@router.post("/{usuario_id}/roles", response_model=schemas.UsuarioOut)
async def asignar_roles(
    usuario_id: str,
    body: schemas.RolesAsignar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario = await service.asignar_roles(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id, roles=body.roles
    )
    return _to_out(usuario)


@router.post("/{usuario_id}/suspender", response_model=schemas.UsuarioOut)
async def suspender(
    usuario_id: str,
    body: schemas.MotivoRequest,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario = await service.suspender_usuario(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id, motivo=body.motivo
    )
    return _to_out(usuario)


@router.post("/{usuario_id}/reactivar", response_model=schemas.UsuarioOut)
async def reactivar(
    usuario_id: str, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    usuario = await service.reactivar_usuario(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id
    )
    return _to_out(usuario)


@router.post("/{usuario_id}/dar-de-baja", response_model=schemas.UsuarioOut)
async def dar_de_baja(
    usuario_id: str,
    body: schemas.MotivoRequest,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario = await service.dar_de_baja_usuario(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id, motivo=body.motivo
    )
    return _to_out(usuario)


@router.post("/{usuario_id}/anonimizar", response_model=schemas.UsuarioOut)
async def anonimizar(
    usuario_id: str,
    body: schemas.AnonimizarConfirmar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario = await service.anonimizar_usuario(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id
    )
    return _to_out(usuario)


@router.get("/{usuario_id}/accesos", response_model=list[schemas.AccesoOut])
async def accesos(
    usuario_id: str, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    eventos = await service.listar_accesos(db, usuario_id)
    return [schemas.AccesoOut(ts=e["ts"], accion=e["accion"], resultado=e["resultado"]) for e in eventos]


@router.get("/{usuario_id}/sesiones", response_model=list[schemas.SesionOut])
async def sesiones(usuario_id: str, actor: Actor = Depends(_admin_sistema)):
    activas = await service.listar_sesiones(usuario_id)
    return [schemas.SesionOut(**s) for s in activas]


@router.delete("/{usuario_id}/sesiones/{jti}", status_code=204)
async def cerrar_sesion(
    usuario_id: str,
    jti: str,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.revocar_sesion(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), usuario_id=usuario_id, jti=jti
    )


@router.post("/procesar-bajas-vencidas", dependencies=[Depends(_verificar_token_interno)])
async def procesar_bajas_vencidas(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Job diario del autoservicio de baja de cuenta: aplica la baja lógica a
    las cuentas cuyo periodo de gracia de 30 días venció sin cancelarse.

    Máquina-a-máquina (lo llama `dag_procesar_bajas_cuenta` desde Airflow),
    no un usuario -- de ahí el token interno en vez de un gate de rol, mismo
    patrón que `POST /viajes/{id}/disparar-programado`.
    """
    return await service.procesar_bajas_vencidas(db)
