from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pe1", telefono="+593970200001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def _asignar_viaje(client, db, redis, *, conductor_id, telefono, vehiculo_id, placa, lat=-0.1801, lon=-78.5001):
    """Crea pasajero + conductor, solicita un viaje y lo lleva hasta ASIGNADO
    — punto de partida común para las pruebas de CU-O07."""
    headers_pasajero = await _pasajero_headers(db)
    await crear_conductor_con_vehiculo(
        db,
        conductor_id=conductor_id,
        telefono=telefono,
        vehiculo_id=vehiculo_id,
        placa=placa,
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id=vehiculo_id, lat=lat, lon=lon)
    headers_conductor = auth_headers(conductor_id, ["conductor"])

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": lat, "origen_lon": lon, "origen_direccion": "Origen"},
    )
    assert creado.json()["estado"] == "OFERTADO"

    aceptado = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert aceptado.json()["estado"] == "ASIGNADO"

    return headers_pasajero, headers_conductor, creado.json()["id"]


async def test_flujo_completo_en_camino_llegada_iniciar(client, db, redis):
    _, headers_conductor, viaje_id = await _asignar_viaje(
        client, db, redis, conductor_id="ce1", telefono="+593970200011", vehiculo_id="ve1", placa="EJC0001"
    )

    en_camino = await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    assert en_camino.status_code == 200
    assert en_camino.json()["estado"] == "EN_CAMINO"

    llegue = await client.post("/viajes/conductor/llegue", headers=headers_conductor)
    assert llegue.status_code == 200
    assert llegue.json()["estado"] == "EN_CAMINO"
    assert llegue.json()["ts_llegada_origen"] is not None

    iniciar = await client.post("/viajes/conductor/iniciar", headers=headers_conductor)
    assert iniciar.status_code == 200
    assert iniciar.json()["estado"] == "EN_CURSO"
    assert iniciar.json()["km_recorridos"] == 0.0

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["estado"] == "EN_CURSO"
    assert viaje_db["ts_inicio"] is not None


async def test_iniciar_viaje_lejos_del_origen_devuelve_409(client, db, redis):
    _, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="ce2", telefono="+593970200012", vehiculo_id="ve2", placa="EJC0002"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)

    # Mueve al conductor lejos del origen declarado (> 150 m) antes de "Iniciar viaje".
    await reportar_posicion_en_cache(redis, vehiculo_id="ve2", lat=-0.1801 + 0.01, lon=-78.5001)

    resp = await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    assert resp.status_code == 409
    assert resp.json()["code"] == "FUERA_DE_RANGO_ORIGEN"


async def test_iniciar_viaje_sin_estar_en_camino_devuelve_409(client, db, redis):
    _, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="ce3", telefono="+593970200013", vehiculo_id="ve3", placa="EJC0003"
    )

    resp = await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    assert resp.status_code == 409
    assert resp.json()["code"] == "TRANSICION_INVALIDA"


async def test_reportar_posicion_durante_en_curso_acumula_traza_y_km(client, db, redis):
    _, headers_conductor, viaje_id = await _asignar_viaje(
        client, db, redis, conductor_id="ce4", telefono="+593970200014", vehiculo_id="ve4", placa="EJC0004"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    resp1 = await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": -0.1801,
            "lon": -78.5001,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:00Z",
        },
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": -0.1811,
            "lon": -78.5001,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:05Z",
        },
    )
    assert resp2.status_code == 200

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert len(viaje_db["traza"]) == 2
    assert viaje_db["km_recorridos"] > 0


async def test_cancelar_por_conductor_antes_de_en_curso_redespacha(client, db, redis):
    _, headers_conductor, viaje_id = await _asignar_viaje(
        client, db, redis, conductor_id="ce5", telefono="+593970200015", vehiculo_id="ve5", placa="EJC0005"
    )
    # Segundo conductor disponible para que el redespacho encuentre a alguien.
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="ce6",
        telefono="+593970200016",
        vehiculo_id="ve6",
        placa="EJC0006",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="ve6", lat=-0.1802, lon=-78.5001)

    resp = await client.post(
        "/viajes/conductor/cancelar", headers=headers_conductor, json={"motivo": "vehículo averiado"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "OFERTADO"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["conductor_ofertado_id"] == "ce6"  # se redespachó al otro candidato, no al que canceló
    assert "ce5" in viaje_db["conductores_descartados"]

    conductor_original = await db.usuarios.find_one({"_id": "ce5"})
    assert conductor_original["conductor"]["estado_servicio"] == "DISPONIBLE"


async def test_cancelar_por_conductor_en_curso_no_permitido(client, db, redis):
    _, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="ce7", telefono="+593970200017", vehiculo_id="ve7", placa="EJC0007"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    resp = await client.post("/viajes/conductor/cancelar", headers=headers_conductor, json={"motivo": "x"})

    assert resp.status_code == 409
    assert resp.json()["code"] == "TRANSICION_INVALIDA"
