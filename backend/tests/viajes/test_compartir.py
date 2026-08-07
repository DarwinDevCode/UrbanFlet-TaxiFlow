from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pc1", telefono="+593970300001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def _asignar_viaje(client, db, redis, *, conductor_id, telefono, vehiculo_id, placa, lat=-0.1801, lon=-78.5001):
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


async def test_generar_token_compartir_viaje_en_camino(client, db, redis):
    headers_pasajero, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="cc1", telefono="+593970300011", vehiculo_id="vc1", placa="CMP0001"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)

    resp = await client.post("/viajes/activo/compartir", headers=headers_pasajero)

    assert resp.status_code == 200
    token = resp.json()["token"]
    assert len(token) > 30

    publico = await client.get(f"/publico/viajes-compartidos/{token}")
    assert publico.status_code == 200
    body = publico.json()
    assert body["estado"] == "EN_CAMINO"
    assert body["vehiculo_placa"] == "CMP0001"
    assert body["posicion"] is not None


async def test_generar_token_compartir_es_idempotente_mientras_siga_vigente(client, db, redis):
    headers_pasajero, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="cc2", telefono="+593970300012", vehiculo_id="vc2", placa="CMP0002"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)

    primero = await client.post("/viajes/activo/compartir", headers=headers_pasajero)
    segundo = await client.post("/viajes/activo/compartir", headers=headers_pasajero)

    assert primero.json()["token"] == segundo.json()["token"]


async def test_generar_token_compartir_sin_viaje_activo_devuelve_409(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)

    resp = await client.post("/viajes/activo/compartir", headers=headers_pasajero)

    assert resp.status_code == 404
    assert resp.json()["code"] == "SIN_VIAJE_ACTIVO"


async def test_token_invalido_devuelve_404_generico(client, db, redis):
    resp = await client.get("/publico/viajes-compartidos/token-que-no-existe")

    assert resp.status_code == 404
    assert resp.json()["code"] == "VIAJE_COMPARTIDO_NO_ENCONTRADO"


async def test_token_se_limpia_al_finalizar_viaje(client, db, redis):
    headers_pasajero, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="cc3", telefono="+593970300013", vehiculo_id="vc3", placa="CMP0003"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    compartir = await client.post("/viajes/activo/compartir", headers=headers_pasajero)
    token = compartir.json()["token"]

    await client.post("/viajes/conductor/llegue", headers=headers_conductor)
    await client.post("/viajes/conductor/iniciar", headers=headers_conductor)
    await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    publico = await client.get(f"/publico/viajes-compartidos/{token}")
    assert publico.status_code == 404


async def test_token_se_limpia_al_cancelar_por_conductor(client, db, redis):
    headers_pasajero, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="cc4", telefono="+593970300014", vehiculo_id="vc4", placa="CMP0004"
    )
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="cc5",
        telefono="+593970300015",
        vehiculo_id="vc5",
        placa="CMP0005",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="vc5", lat=-0.1802, lon=-78.5001)

    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    compartir = await client.post("/viajes/activo/compartir", headers=headers_pasajero)
    token = compartir.json()["token"]

    resp = await client.post(
        "/viajes/conductor/cancelar", headers=headers_conductor, json={"motivo": "vehículo averiado"}
    )
    assert resp.status_code == 200

    publico = await client.get(f"/publico/viajes-compartidos/{token}")
    assert publico.status_code == 404


async def test_rate_limit_bloquea_tras_umbral_de_fallos(client, db, redis):
    for _ in range(20):
        resp = await client.get("/publico/viajes-compartidos/token-invalido")
        assert resp.status_code == 404

    bloqueado = await client.get("/publico/viajes-compartidos/token-invalido")
    assert bloqueado.status_code == 429
    assert bloqueado.json()["code"] == "TOO_MANY_SHARE_ATTEMPTS"


async def test_consulta_valida_no_incrementa_contador_de_fallos(client, db, redis):
    headers_pasajero, headers_conductor, _ = await _asignar_viaje(
        client, db, redis, conductor_id="cc6", telefono="+593970300016", vehiculo_id="vc6", placa="CMP0006"
    )
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    compartir = await client.post("/viajes/activo/compartir", headers=headers_pasajero)
    token = compartir.json()["token"]

    for _ in range(25):
        resp = await client.get(f"/publico/viajes-compartidos/{token}")
        assert resp.status_code == 200
