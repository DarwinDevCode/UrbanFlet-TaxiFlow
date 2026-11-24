"""CU-O04 A4 — cancelación temprana del pasajero (SOLICITADO/OFERTADO), sobre
SU PROPIO viaje activo — POST /viajes/activo/cancelar no toma un viaje_id de
la URL a propósito, para no ambigüar ownership y para no chocar en el ruteo
con /viajes/conductor/cancelar (service_ejecucion, un endpoint distinto).

No cubre CU-O07 A2 (cancelar con conductor ya en camino / ASIGNADO en
adelante) a propósito — ver corte de alcance en viajes/service.py.
"""

from datetime import UTC, datetime

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pc1", telefono="+593960300001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def test_cancelar_viaje_solicitado_exitoso(client, db):
    # Sin ningún conductor disponible el despacho agota todos los radios de
    # inmediato y el viaje queda SIN_CONDUCTOR (no cancelable, no ACTIVO) —
    # para probar el estado SOLICITADO puro se inserta el documento
    # directamente, sin pasar por /viajes (que dispara el despacho).
    headers = await _pasajero_headers(db)
    viaje_id = "viaje-solicitado-directo"
    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pc1",
            "estado": "SOLICITADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "ts_solicitud": datetime.now(UTC),
            "conductor_id": None,
            "vehiculo_id": None,
            "tarifa_estimada": None,
            "tarifa_final": None,
            "motivo_cancelacion": None,
            "actor_cancelacion": None,
        }
    )

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers, json={"motivo": "Cancelado por el pasajero"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "CANCELADO"
    assert resp.json()["motivo_cancelacion"] == "Cancelado por el pasajero"
    assert resp.json()["id"] == viaje_id

    activo = await client.get("/viajes/activo", headers=headers)
    assert activo.status_code == 200
    assert activo.json() is None

    evento = await db.bitacora.find_one({"entidad_id": viaje_id, "accion": "VIAJE_CANCELADO_PASAJERO"})
    assert evento is not None


async def test_cancelar_viaje_ofertado_exitoso(client, db, redis):
    headers = await _pasajero_headers(db, usuario_id="pc2", telefono="+593960300002")
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="cc2",
        telefono="+593970300002",
        vehiculo_id="vc2",
        placa="PBA0102",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="vc2", lat=-0.1801, lon=-78.5001)

    creado = await client.post(
        "/viajes",
        headers=headers,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    assert creado.json()["estado"] == "OFERTADO"
    viaje_id = creado.json()["id"]

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers, json={"motivo": "Cancelado por el pasajero"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "CANCELADO"
    assert resp.json()["id"] == viaje_id


async def test_cancelar_viaje_asignado_rechazado(client, db, redis):
    headers = await _pasajero_headers(db, usuario_id="pc3", telefono="+593960300003")
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="cc3",
        telefono="+593970300003",
        vehiculo_id="vc3",
        placa="PBA0103",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="vc3", lat=-0.1801, lon=-78.5001)
    headers_conductor = auth_headers("cc3", ["conductor"])

    creado = await client.post(
        "/viajes",
        headers=headers,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    viaje_id = creado.json()["id"]
    aceptado = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert aceptado.json()["estado"] == "ASIGNADO"

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers, json={"motivo": "Cancelado por el pasajero"}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "VIAJE_NO_CANCELABLE"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["estado"] == "ASIGNADO"


async def test_cancelar_sin_viaje_activo_devuelve_404(client, db):
    headers = await _pasajero_headers(db, usuario_id="pc4", telefono="+593960300004")

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers, json={"motivo": "Cancelado por el pasajero"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "SIN_VIAJE_ACTIVO"


async def test_cancelar_no_afecta_viaje_de_otro_pasajero(client, db, redis):
    """Ownership implícito: /viajes/activo/cancelar solo puede afectar el
    viaje activo DEL ACTOR AUTENTICADO — nunca toma un id ajeno."""
    headers_a = await _pasajero_headers(db, usuario_id="pc5", telefono="+593960300005")
    headers_b = await _pasajero_headers(db, usuario_id="pc6", telefono="+593960300006")

    creado = await client.post(
        "/viajes",
        headers=headers_a,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    viaje_id = creado.json()["id"]

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers_b, json={"motivo": "Cancelado por el pasajero"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "SIN_VIAJE_ACTIVO"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["estado"] != "CANCELADO"
