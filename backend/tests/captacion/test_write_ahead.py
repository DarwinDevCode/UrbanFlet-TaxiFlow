"""Verifica, operación por operación crítica de Captación, que el evento de
auditoría se escribe ANTES del efecto de negocio — el mismo patrón que
tests/core/test_write_ahead.py, pero para CU-O01/O02/O03. No se asume que la
corrección aplicada en auth/rbac (Fase 0) se propague sola a un módulo nuevo:
cada punto de escritura crítico se prueba por separado, tumbando la bitácora
y confirmando que el efecto correspondiente no queda persistido.
"""

from pymongo.errors import PyMongoError

from tests.utils import auth_headers, crear_usuario_activo

_VEHICULO = {"placa": "WAH-0001", "marca": "Kia", "modelo": "Rio", "anio": 2019, "color": "Gris", "capacidad": 4}


def _falla_bitacora(monkeypatch, db):
    async def _insert_one_falla(*args, **kwargs):
        raise PyMongoError("Mongo caído")

    monkeypatch.setattr(type(db.bitacora), "insert_one", _insert_one_falla)


async def test_bitacora_caida_impide_registro_de_pasajero(client, db, monkeypatch):
    _falla_bitacora(monkeypatch, db)

    resp = await client.post(
        "/captacion/pasajeros/registro",
        json={
            "nombre": "Nunca Pasajero",
            "telefono": "+593930000001",
            "password": "clave-larga-123",
            "version_consentimiento": "v1",
        },
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"
    assert await db.usuarios.find_one({"telefono": "+593930000001"}) is None


async def test_bitacora_caida_impide_creacion_de_solicitud(client, db, monkeypatch):
    _falla_bitacora(monkeypatch, db)

    resp = await client.post(
        "/captacion/solicitudes",
        json={
            "nombre": "Nunca Postulante",
            "telefono": "+593930000002",
            "password": "clave-larga-123",
            "cedula": "9998887770",
            "licencia_numero": "LIC-999",
            "vehiculo": _VEHICULO,
            "documentos": [],
            "enviar": True,
        },
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"
    assert await db.usuarios.find_one({"telefono": "+593930000002"}) is None
    assert await db.solicitudes.find_one({"cedula": "9998887770"}) is None


async def test_bitacora_caida_impide_decision_de_solicitud(client, db, monkeypatch):
    await crear_usuario_activo(db, usuario_id="u-admin-wa", telefono="+593930000003", roles=["admin_captacion"])
    headers = auth_headers("u-admin-wa", ["admin_captacion"])

    creada = await client.post(
        "/captacion/solicitudes",
        json={
            "nombre": "Postulante Rechazo",
            "telefono": "+593930000004",
            "password": "clave-larga-123",
            "cedula": "9998887771",
            "licencia_numero": "LIC-998",
            "vehiculo": {**_VEHICULO, "placa": "WAH-0002"},
            "documentos": [],
            "enviar": True,
        },
    )
    solicitud_id = creada.json()["id"]

    _falla_bitacora(monkeypatch, db)

    resp = await client.post(
        f"/captacion/solicitudes/{solicitud_id}/decision",
        json={"decision": "RECHAZADA", "motivo": "Documentación incompleta"},
        headers=headers,
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    solicitud = await db.solicitudes.find_one({"_id": solicitud_id})
    assert solicitud["estado"] == "ENVIADA", "la decisión no debe aplicarse si la bitácora falló (write-ahead)"


async def test_bitacora_caida_impide_habilitacion_de_vehiculo_aunque_la_decision_ya_se_escribiera(
    client, db, monkeypatch
):
    """Caso más fino: la auditoría de la DECISIÓN logra escribirse, pero la
    auditoría específica de HABILITACIÓN DE VEHÍCULO (un evento distinto,
    también exigido por el catálogo de CU-O17) falla.

    Este test corre contra `mongomock`, que no implementa sesiones — así que
    `with_transaction` (core/db_transaction.py) hace su fallback sin sesión y
    el resultado sigue siendo el estado parcial de antes: la solicitud queda
    APROBADA pero el vehículo y el rol de conductor no se crean. Es el
    comportamiento esperado del *fallback*, no una garantía de atomicidad —
    esa garantía real, contra un Mongo con replica set de verdad, la prueba
    tests/core/test_db_transaction_integration.py (mongomock no tiene
    rollback real que demostrar)."""
    await crear_usuario_activo(db, usuario_id="u-admin-wa2", telefono="+593930000005", roles=["admin_captacion"])
    headers = auth_headers("u-admin-wa2", ["admin_captacion"])

    creada = await client.post(
        "/captacion/solicitudes",
        json={
            "nombre": "Postulante Aprobacion Parcial",
            "telefono": "+593930000006",
            "password": "clave-larga-123",
            "cedula": "9998887772",
            "licencia_numero": "LIC-997",
            "vehiculo": {**_VEHICULO, "placa": "WAH-0003"},
            "documentos": [],
            "enviar": True,
        },
    )
    solicitud_id = creada.json()["id"]
    usuario_id = creada.json()["usuario_id"]

    original_insert_one = type(db.bitacora).insert_one
    llamadas = {"n": 0}

    async def _falla_desde_la_segunda_llamada(self, *args, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return await original_insert_one(self, *args, **kwargs)
        raise PyMongoError("Mongo caído en la segunda escritura de auditoría")

    monkeypatch.setattr(type(db.bitacora), "insert_one", _falla_desde_la_segunda_llamada)

    resp = await client.post(
        f"/captacion/solicitudes/{solicitud_id}/decision", json={"decision": "APROBADA"}, headers=headers
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    # La decisión (primer evento) sí se aplicó; la habilitación del vehículo
    # (segundo evento) no — exactamente lo que el gateo por-operación predice.
    solicitud = await db.solicitudes.find_one({"_id": solicitud_id})
    assert solicitud["estado"] == "APROBADA"

    assert await db.vehiculos.find_one({"placa": "WAH-0003"}) is None
    usuario = await db.usuarios.find_one({"_id": usuario_id})
    assert "conductor" not in usuario["roles"]
