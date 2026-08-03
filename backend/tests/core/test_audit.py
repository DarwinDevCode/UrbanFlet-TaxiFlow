import pytest
from pymongo.errors import PyMongoError

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import AuditWriteError


async def test_write_audit_event_asigna_evento_id_secuencial(db):
    primero = await write_audit_event(
        db,
        actor_id="u1",
        rol="pasajero",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id="v1",
        resultado=ResultadoAuditoria.OK,
    )
    segundo = await write_audit_event(
        db,
        actor_id="u1",
        rol="pasajero",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id="v1",
        resultado=ResultadoAuditoria.OK,
    )

    assert segundo["evento_id"] == primero["evento_id"] + 1
    assert await db.bitacora.count_documents({}) == 2


async def test_write_audit_event_falla_propaga_para_abortar_la_operacion(db, monkeypatch):
    async def _insert_one_falla(*args, **kwargs):
        raise PyMongoError("Mongo caído")

    # Cada acceso a `db.bitacora` devuelve una instancia nueva de Collection;
    # se parchea a nivel de clase para que cualquier acceso quede afectado.
    monkeypatch.setattr(type(db.bitacora), "insert_one", _insert_one_falla)

    with pytest.raises(AuditWriteError):
        await write_audit_event(
            db,
            actor_id="u1",
            rol="pasajero",
            accion=AccionAuditoria.PAGO_REGISTRO,
            entidad="pagos",
            entidad_id="p1",
            resultado=ResultadoAuditoria.OK,
        )
