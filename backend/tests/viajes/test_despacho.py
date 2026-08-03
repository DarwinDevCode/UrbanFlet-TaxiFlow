from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pd1", telefono="+593970100001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def _sembrar_conductor(
    db, redis, *, conductor_id, telefono, vehiculo_id, placa, lat=-0.1801, lon=-78.5001, estado_servicio="DISPONIBLE"
):
    await crear_conductor_con_vehiculo(
        db,
        conductor_id=conductor_id,
        telefono=telefono,
        vehiculo_id=vehiculo_id,
        placa=placa,
        estado_servicio=estado_servicio,
    )
    await reportar_posicion_en_cache(redis, vehiculo_id=vehiculo_id, lat=lat, lon=lon)


async def test_sin_candidatos_en_ningun_radio_pasa_a_sin_conductor(client, db, redis):
    headers = await _pasajero_headers(db)

    resp = await client.post(
        "/viajes", headers=headers, json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    )

    assert resp.status_code == 201
    assert resp.json()["estado"] == "SIN_CONDUCTOR"


async def test_candidato_dentro_de_300m_recibe_oferta(client, db, redis):
    headers = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd1", telefono="+593970100011", vehiculo_id="vd1", placa="PBD0001"
    )

    resp = await client.post(
        "/viajes", headers=headers, json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "OFERTADO"

    oferta = await db.ofertas.find_one({"viaje_id": body["id"], "conductor_id": "cd1"})
    assert oferta is not None
    assert oferta["resultado"] is None
    assert oferta["radio_m"] == 300


async def test_candidato_solo_dentro_de_1000m_amplia_radio(client, db, redis):
    headers = await _pasajero_headers(db)
    # ~0.008 grados de latitud ≈ 890 m — fuera de 300/600, dentro de 1000.
    await _sembrar_conductor(
        db,
        redis,
        conductor_id="cd2",
        telefono="+593970100012",
        vehiculo_id="vd2",
        placa="PBD0002",
        lat=-0.18 + 0.008,
        lon=-78.5,
    )

    resp = await client.post(
        "/viajes", headers=headers, json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "OFERTADO"
    viaje_db = await db.viajes.find_one({"_id": body["id"]})
    assert viaje_db["radio_actual_m"] == 1000


async def test_conductor_con_documentacion_vencida_no_es_candidato(client, db, redis):
    headers = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd3", telefono="+593970100013", vehiculo_id="vd3", placa="PBD0003"
    )
    await db.usuarios.update_one({"_id": "cd3"}, {"$set": {"conductor.cumplimiento_ok": False}})

    resp = await client.post(
        "/viajes", headers=headers, json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    )

    assert resp.json()["estado"] == "SIN_CONDUCTOR"


async def test_conductor_acepta_oferta_transiciona_a_asignado(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd4", telefono="+593970100014", vehiculo_id="vd4", placa="PBD0004"
    )
    headers_conductor = auth_headers("cd4", ["conductor"])

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    assert creado.json()["estado"] == "OFERTADO"

    oferta_vista = await client.get("/viajes/oferta-actual", headers=headers_conductor)
    assert oferta_vista.status_code == 200
    assert oferta_vista.json()["viaje_id"] == creado.json()["id"]

    resp = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert resp.status_code == 200
    assert resp.json()["estado"] == "ASIGNADO"

    viaje_db = await db.viajes.find_one({"_id": creado.json()["id"]})
    assert viaje_db["conductor_id"] == "cd4"
    assert viaje_db["vehiculo_id"] == "vd4"
    assert viaje_db["vehiculo_placa"] == "PBD0004"

    conductor_db = await db.usuarios.find_one({"_id": "cd4"})
    assert conductor_db["conductor"]["estado_servicio"] == "OCUPADO"

    activo_conductor = await client.get("/viajes/conductor/activo", headers=headers_conductor)
    assert activo_conductor.status_code == 200
    assert activo_conductor.json()["id"] == creado.json()["id"]
    assert activo_conductor.json()["origen_direccion"] == "Origen"

    oferta_db = await db.ofertas.find_one({"viaje_id": creado.json()["id"], "conductor_id": "cd4"})
    assert oferta_db["resultado"] == "ACEPTADA"


async def test_doble_aceptacion_la_segunda_recibe_offer_no_longer_available(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd5", telefono="+593970100015", vehiculo_id="vd5", placa="PBD0005"
    )
    headers_conductor = auth_headers("cd5", ["conductor"])

    await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )

    primera = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert primera.status_code == 200

    segunda = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert segunda.status_code == 404
    assert segunda.json()["code"] == "SIN_OFERTA_ACTIVA"


async def test_conductor_rechaza_oferta_pasa_al_siguiente_candidato(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd6", telefono="+593970100016", vehiculo_id="vd6", placa="PBD0006", lat=-0.1801
    )
    await _sembrar_conductor(
        db, redis, conductor_id="cd7", telefono="+593970100017", vehiculo_id="vd7", placa="PBD0007", lat=-0.1802
    )
    headers_cd6 = auth_headers("cd6", ["conductor"])
    headers_cd7 = auth_headers("cd7", ["conductor"])

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    viaje_id = creado.json()["id"]
    ofertado_a = (await db.viajes.find_one({"_id": viaje_id}))["conductor_ofertado_id"]
    assert ofertado_a == "cd6"  # cd6 está más cerca del origen

    rechazo = await client.post("/viajes/oferta/responder", headers=headers_cd6, json={"aceptar": False})
    assert rechazo.status_code == 200
    assert rechazo.json()["estado"] == "OFERTADO"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["conductor_ofertado_id"] == "cd7"

    oferta_cd6 = await db.ofertas.find_one({"viaje_id": viaje_id, "conductor_id": "cd6"})
    assert oferta_cd6["resultado"] == "RECHAZADA"

    # cd7 sigue pudiendo aceptar la oferta que le llegó.
    acepta = await client.post("/viajes/oferta/responder", headers=headers_cd7, json={"aceptar": True})
    assert acepta.status_code == 200
    assert acepta.json()["estado"] == "ASIGNADO"


async def test_oferta_expirada_avanza_al_siguiente_candidato_en_el_siguiente_poll(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cd8", telefono="+593970100018", vehiculo_id="vd8", placa="PBD0008"
    )
    await _sembrar_conductor(
        db, redis, conductor_id="cd9", telefono="+593970100019", vehiculo_id="vd9", placa="PBD0009", lat=-0.1802
    )

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )
    viaje_id = creado.json()["id"]
    assert (await db.viajes.find_one({"_id": viaje_id}))["conductor_ofertado_id"] == "cd8"

    # Simula que expiró: retrocede ts_oferta_emitida más allá de los 20s.
    await db.viajes.update_one(
        {"_id": viaje_id}, {"$set": {"ts_oferta_emitida": datetime.now(UTC) - timedelta(seconds=25)}}
    )

    resp = await client.get("/viajes/activo", headers=headers_pasajero)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "OFERTADO"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["conductor_ofertado_id"] == "cd9"

    oferta_cd8 = await db.ofertas.find_one({"viaje_id": viaje_id, "conductor_id": "cd8"})
    assert oferta_cd8["resultado"] == "EXPIRADA"


async def test_si_falla_la_auditoria_al_aceptar_no_se_aplica_ningun_efecto(client, db, redis, monkeypatch):
    """Write-ahead (CU-O17): la auditoría de la transición a ASIGNADO se
    escribe ANTES que cualquier efecto de negocio (viaje, oferta, conductor).
    Con mongomock (sin sesión real) esto ya basta para que, si la auditoría
    falla, no se aplique nada — porque el efecto ni siquiera se intenta
    todavía en ese punto del código. La garantía de rollback real para un
    fallo A MITAD de la cadena (no al principio) se prueba aparte, contra
    Mongo real, en test_despacho_write_ahead_integration.py — igual que el
    caso equivalente de Captación (Fase 1)."""
    headers_pasajero = await _pasajero_headers(db)
    await _sembrar_conductor(
        db, redis, conductor_id="cdX", telefono="+593970100099", vehiculo_id="vdX", placa="PBDX001"
    )
    headers_conductor = auth_headers("cdX", ["conductor"])

    await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"},
    )

    from pymongo.errors import PyMongoError

    collection_cls = type(db.bitacora)
    original_insert_one = collection_cls.insert_one

    async def fallar_bitacora(self, *args, **kwargs):
        if self.name == "bitacora":
            raise PyMongoError("Mongo caído (simulado)")
        return await original_insert_one(self, *args, **kwargs)

    monkeypatch.setattr(collection_cls, "insert_one", fallar_bitacora)

    resp = await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    monkeypatch.setattr(collection_cls, "insert_one", original_insert_one)

    viaje_db = await db.viajes.find_one({"conductor_ofertado_id": "cdX"})
    assert viaje_db["estado"] == "OFERTADO"  # no quedó a medio camino en ASIGNADO

    conductor_db = await db.usuarios.find_one({"_id": "cdX"})
    assert conductor_db["conductor"]["estado_servicio"] == "DISPONIBLE"  # no quedó en OCUPADO
