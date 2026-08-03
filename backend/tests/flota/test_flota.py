from datetime import UTC, datetime

from tests.utils import (
    auth_headers,
    crear_conductor_con_vehiculo,
    crear_usuario_activo,
    reportar_posicion_en_cache,
)


async def _conductor_con_vehiculo(db, n: int, **overrides):
    return await crear_conductor_con_vehiculo(
        db, conductor_id=f"c{n}", telefono=f"+59395400000{n}", vehiculo_id=f"v{n}", placa=f"FLT-000{n}", **overrides
    )


async def test_iniciar_turno_bloqueado_por_bandera_cumplimiento(client, db):
    await _conductor_con_vehiculo(db, 1, cumplimiento_ok_conductor=False)
    headers = auth_headers("c1", ["conductor"])

    resp = await client.post("/flota/turno/iniciar", headers=headers)

    assert resp.status_code == 409
    assert resp.json()["code"] == "TURNO_BLOQUEADO"
    assert "conductor" in resp.json()["message"]


async def test_iniciar_turno_bloqueado_por_vehiculo_retirado(client, db):
    await _conductor_con_vehiculo(db, 2, estado_habilitacion="RETIRADO_DE_SERVICIO")
    headers = auth_headers("c2", ["conductor"])

    resp = await client.post("/flota/turno/iniciar", headers=headers)

    assert resp.status_code == 409
    assert "mantenimiento" in resp.json()["message"]


async def test_iniciar_turno_exitoso_con_banderas_verdes(client, db):
    await _conductor_con_vehiculo(db, 3)
    headers = auth_headers("c3", ["conductor"])

    resp = await client.post("/flota/turno/iniciar", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["estado_servicio"] == "DISPONIBLE"
    usuario = await db.usuarios.find_one({"_id": "c3"})
    assert usuario["conductor"]["estado_servicio"] == "DISPONIBLE"


async def test_terminar_turno_vuelve_a_fuera_de_linea(client, db):
    await _conductor_con_vehiculo(db, 4, estado_servicio="DISPONIBLE")
    headers = auth_headers("c4", ["conductor"])

    resp = await client.post("/flota/turno/terminar", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["estado_servicio"] == "FUERA_DE_LINEA"


async def test_terminar_turno_bloqueado_con_viaje_activo(client, db):
    await _conductor_con_vehiculo(db, 8, estado_servicio="OCUPADO")
    await db.viajes.insert_one(
        {"_id": "viaje-activo-c8", "conductor_id": "c8", "estado": "EN_CAMINO", "pasajero_id": "p1"}
    )
    headers = auth_headers("c8", ["conductor"])

    resp = await client.post("/flota/turno/terminar", headers=headers)

    assert resp.status_code == 409
    assert resp.json()["code"] == "TURNO_CON_VIAJE_ACTIVO"
    usuario = await db.usuarios.find_one({"_id": "c8"})
    assert usuario["conductor"]["estado_servicio"] == "OCUPADO"


async def test_reportar_posicion_sin_turno_activo_devuelve_409(client, db):
    await _conductor_con_vehiculo(db, 5)
    headers = auth_headers("c5", ["conductor"])

    resp = await client.post(
        "/flota/posiciones",
        headers=headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "TURNO_NO_INICIADO"


async def test_reportar_posicion_aceptada_actualiza_cache(client, db, redis):
    await _conductor_con_vehiculo(db, 6, estado_servicio="DISPONIBLE")
    headers = auth_headers("c6", ["conductor"])

    resp = await client.post(
        "/flota/posiciones",
        headers=headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    assert resp.status_code == 200
    assert resp.json()["aceptada"] is True
    cache = await redis.hgetall("pos:v6")
    assert float(cache["lat"]) == -0.2

    posiciones = await db.posiciones.count_documents({"vehiculo_id": "v6"})
    assert posiciones == 1


async def test_reportar_posicion_con_salto_imposible_se_descarta(client, db, redis):
    await _conductor_con_vehiculo(db, 7, estado_servicio="DISPONIBLE")
    headers = auth_headers("c7", ["conductor"])

    primera = await client.post(
        "/flota/posiciones",
        headers=headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )
    assert primera.json()["aceptada"] is True

    lejos = await client.post(
        "/flota/posiciones",
        headers=headers,
        json={"lat": 10.0, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    assert lejos.status_code == 200
    assert lejos.json()["aceptada"] is False

    cache = await redis.hgetall("pos:v7")
    assert float(cache["lat"]) == -0.2  # se conserva la posición anterior

    evento = await db.bitacora.find_one({"entidad_id": "v7", "accion": "POSIBLE_GPS_SPOOFING"})
    assert evento is not None


async def test_reportar_posicion_precision_baja_se_marca(client, db):
    await _conductor_con_vehiculo(db, 8, estado_servicio="DISPONIBLE")
    headers = auth_headers("c8", ["conductor"])

    resp = await client.post(
        "/flota/posiciones",
        headers=headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 80, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    assert resp.status_code == 200
    assert resp.json()["precision_baja"] is True


async def test_tablero_flota_requiere_coordinador(client, db):
    resp = await client.get("/flota/tablero")
    assert resp.status_code == 401


async def test_tablero_flota_lista_vehiculos_en_servicio(client, db):
    await crear_usuario_activo(db, usuario_id="u-coord", telefono="+593954000099", roles=["coordinador_flota"])
    headers = auth_headers("u-coord", ["coordinador_flota"])
    await _conductor_con_vehiculo(db, 9, estado_servicio="DISPONIBLE")
    conductor_headers = auth_headers("c9", ["conductor"])
    await client.post(
        "/flota/posiciones",
        headers=conductor_headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    resp = await client.get("/flota/tablero", headers=headers)

    assert resp.status_code == 200
    vehiculos = resp.json()
    assert len(vehiculos) == 1
    assert vehiculos[0]["vehiculo_id"] == "v9"
    assert vehiculos[0]["sin_senal"] is False


async def test_cercanos_requiere_autenticacion(client, db):
    resp = await client.get("/flota/cercanos", params={"lat": -0.18, "lon": -78.5})
    assert resp.status_code == 401


async def test_cercanos_devuelve_posiciones_anonimizadas_dentro_del_radio(client, db, redis):
    await crear_usuario_activo(db, usuario_id="u-pasajero-cercanos", telefono="+593954000199", roles=["pasajero"])
    headers = auth_headers("u-pasajero-cercanos", ["pasajero"])

    await _conductor_con_vehiculo(db, 10, estado_servicio="DISPONIBLE")
    await reportar_posicion_en_cache(redis, vehiculo_id="v10", lat=-0.1801, lon=-78.5001)  # ~a pocos metros

    await _conductor_con_vehiculo(db, 11, estado_servicio="DISPONIBLE")
    await reportar_posicion_en_cache(redis, vehiculo_id="v11", lat=-1.0, lon=-79.0)  # muy lejos

    await _conductor_con_vehiculo(db, 12, estado_servicio="OCUPADO")
    await reportar_posicion_en_cache(redis, vehiculo_id="v12", lat=-0.1802, lon=-78.5002)  # cerca pero no DISPONIBLE

    resp = await client.get("/flota/cercanos", headers=headers, params={"lat": -0.18, "lon": -78.5, "radio_m": 300})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"lat", "lon"}
    assert abs(body[0]["lat"] - (-0.1801)) < 1e-6


async def test_posicion_conductor_requiere_autenticacion(client, db):
    resp = await client.get("/flota/posicion/c13")
    assert resp.status_code == 401


async def test_posicion_conductor_el_propio_conductor_puede_verla(client, db, redis):
    await _conductor_con_vehiculo(db, 13, estado_servicio="OCUPADO")
    await reportar_posicion_en_cache(redis, vehiculo_id="v13", lat=-0.19, lon=-78.51)
    headers = auth_headers("c13", ["conductor"])

    resp = await client.get("/flota/posicion/c13", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["lat"] - (-0.19)) < 1e-6
    assert abs(body["lon"] - (-78.51)) < 1e-6
    assert "ts_servidor" in body


async def test_posicion_conductor_pasajero_con_viaje_asignado_puede_verla(client, db, redis):
    await _conductor_con_vehiculo(db, 14, estado_servicio="OCUPADO")
    await reportar_posicion_en_cache(redis, vehiculo_id="v14", lat=-0.2, lon=-78.52)
    await crear_usuario_activo(db, usuario_id="p-asignado", telefono="+593954000201", roles=["pasajero"])
    await db.viajes.insert_one(
        {
            "_id": "viaje-asignado-c14",
            "conductor_id": "c14",
            "pasajero_id": "p-asignado",
            "estado": "ASIGNADO",
        }
    )
    headers = auth_headers("p-asignado", ["pasajero"])

    resp = await client.get("/flota/posicion/c14", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["lat"] - (-0.2)) < 1e-6


async def test_posicion_conductor_pasajero_sin_viaje_asignado_es_rechazado(client, db, redis):
    await _conductor_con_vehiculo(db, 15, estado_servicio="OCUPADO")
    await reportar_posicion_en_cache(redis, vehiculo_id="v15", lat=-0.2, lon=-78.52)
    await crear_usuario_activo(db, usuario_id="p-no-asignado", telefono="+593954000202", roles=["pasajero"])
    headers = auth_headers("p-no-asignado", ["pasajero"])

    resp = await client.get("/flota/posicion/c15", headers=headers)

    assert resp.status_code == 403
    assert resp.json()["code"] == "POSICION_CONDUCTOR_NO_AUTORIZADA"


async def test_posicion_conductor_viaje_no_activo_es_rechazado(client, db, redis):
    await _conductor_con_vehiculo(db, 16, estado_servicio="FUERA_DE_LINEA")
    await reportar_posicion_en_cache(redis, vehiculo_id="v16", lat=-0.2, lon=-78.52)
    await crear_usuario_activo(db, usuario_id="p-finalizado", telefono="+593954000203", roles=["pasajero"])
    await db.viajes.insert_one(
        {
            "_id": "viaje-finalizado-c16",
            "conductor_id": "c16",
            "pasajero_id": "p-finalizado",
            "estado": "FINALIZADO",
        }
    )
    headers = auth_headers("p-finalizado", ["pasajero"])

    resp = await client.get("/flota/posicion/c16", headers=headers)

    assert resp.status_code == 403


async def test_posicion_conductor_sin_posicion_reportada_devuelve_404(client, db):
    await _conductor_con_vehiculo(db, 17, estado_servicio="OCUPADO")
    headers = auth_headers("c17", ["conductor"])

    resp = await client.get("/flota/posicion/c17", headers=headers)

    assert resp.status_code == 404
    assert resp.json()["code"] == "POSICION_CONDUCTOR_NO_DISPONIBLE"
