"""Mismo patrón de tests/captacion/test_write_ahead.py: verifica, para las
dos cadenas transaccionales de Mantenimiento (crear orden con retiro de
vehículo, cerrar orden con habilitación de vehículo), que si la bitácora
falla, el efecto de negocio no queda persistido."""

from pymongo.errors import PyMongoError

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


def _falla_bitacora(monkeypatch, db):
    async def _insert_one_falla(*args, **kwargs):
        raise PyMongoError("Mongo caído")

    monkeypatch.setattr(type(db.bitacora), "insert_one", _insert_one_falla)


async def test_bitacora_caida_impide_creacion_de_orden_con_retiro(client, db, monkeypatch):
    await crear_usuario_activo(db, usuario_id="u-jefe-wa1", telefono="+593951000001", roles=["jefe_mantenimiento"])
    headers = auth_headers("u-jefe-wa1", ["jefe_mantenimiento"])
    await crear_conductor_con_vehiculo(
        db, conductor_id="c-wa1", telefono="+593951000002", vehiculo_id="v-wa1", placa="WAH-M001"
    )

    _falla_bitacora(monkeypatch, db)

    resp = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v-wa1",
            "tipo": "CORRECTIVA",
            "descripcion": "x",
            "km_entrada": 100,
            "taller": "Taller",
            "fecha_programada": "2026-08-01",
            "retirar_vehiculo": True,
        },
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"
    assert await db.ordenes.count_documents({}) == 0
    v = await db.vehiculos.find_one({"_id": "v-wa1"})
    assert v["estado_habilitacion"] == "HABILITADO", "el vehículo no debe quedar retirado si la orden no se creó"


async def test_bitacora_caida_impide_cierre_con_habilitacion(client, db, monkeypatch):
    await crear_usuario_activo(db, usuario_id="u-jefe-wa2", telefono="+593951000003", roles=["jefe_mantenimiento"])
    headers = auth_headers("u-jefe-wa2", ["jefe_mantenimiento"])
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="c-wa2",
        telefono="+593951000004",
        vehiculo_id="v-wa2",
        placa="WAH-M002",
        estado_habilitacion="RETIRADO_DE_SERVICIO",
    )
    await db.ordenes.insert_one(
        {
            "_id": "orden-wa2",
            "vehiculo_id": "v-wa2",
            "tipo": "CORRECTIVA",
            "estado": "EN_TALLER",
            "descripcion": "x",
            "km_entrada": 100,
            "km_salida": None,
            "taller": "Taller",
            "fecha_programada": "2026-08-01",
            "fecha_cierre": None,
            "costo_total": None,
            "orden_madre_id": None,
            "repuestos_estimados": [],
            "repuestos_consumidos": [],
        }
    )

    _falla_bitacora(monkeypatch, db)

    resp = await client.post(
        "/mantenimiento/ordenes/orden-wa2/cierre",
        headers=headers,
        json={"trabajos_realizados": "x", "costo_total": 50, "km_salida": 150, "habilitar_vehiculo": True},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    orden = await db.ordenes.find_one({"_id": "orden-wa2"})
    assert orden["estado"] == "EN_TALLER", "el cierre no debe aplicarse si la bitácora falló"
    v = await db.vehiculos.find_one({"_id": "v-wa2"})
    assert v["estado_habilitacion"] == "RETIRADO_DE_SERVICIO", "el vehículo no debe habilitarse sin el cierre real"
