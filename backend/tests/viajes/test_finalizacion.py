from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pf1", telefono="+593970300001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def _admin_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-tarifa-fin", telefono="+593970399999", roles=["admin_plataforma"])
    return auth_headers("admin-tarifa-fin", ["admin_plataforma"])


async def _sembrar_tarifas(client, db):
    headers_admin = await _admin_headers(db)
    for franja, valores in (
        ("DIURNA", {"arrancada": 0.5, "costo_km": 0.35, "costo_min_espera": 0.07, "carrera_minima": 1.5}),
        ("NOCTURNA", {"arrancada": 0.6, "costo_km": 0.4, "costo_min_espera": 0.09, "carrera_minima": 1.75}),
    ):
        await client.post(
            "/parametros/tarifas",
            headers=headers_admin,
            json={**valores, "franja": franja, "vigente_desde": "2020-01-01T00:00:00Z"},
        )


async def _viaje_en_curso(
    client, db, redis, *, conductor_id, telefono, vehiculo_id, placa, con_destino=True, lat=-0.1801, lon=-78.5001
):
    await _sembrar_tarifas(client, db)
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

    payload = {"origen_lat": lat, "origen_lon": lon, "origen_direccion": "Origen"}
    if con_destino:
        payload.update({"destino_lat": lat - 0.01, "destino_lon": lon, "destino_direccion": "Destino"})
    creado = await client.post("/viajes", headers=headers_pasajero, json=payload)
    viaje_id = creado.json()["id"]

    await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": lat - 0.005,
            "lon": lon,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:05Z",
        },
    )

    return headers_pasajero, headers_conductor, viaje_id


async def test_finalizar_viaje_calcula_tarifa_final(client, db, redis):
    _, headers_conductor, _viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf1", telefono="+593970300011", vehiculo_id="vf1", placa="FIN0001"
    )

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "FINALIZADO"
    assert body["tarifa_final"] is not None
    assert body["tarifa_final"] > 0

    conductor_db = await db.usuarios.find_one({"_id": "cf1"})
    assert conductor_db["conductor"]["estado_servicio"] == "DISPONIBLE"


async def test_finalizar_viaje_desglosa_tarifa_con_piso_aplicado(client, db, redis):
    """CU-O08 paso 3: viaje corto (fixture por defecto, ~0.5 km) -- el
    subtotal de los 3 rubros no alcanza la carrera_minima (1.5 DIURNA), así
    que tarifa_final queda en el piso, mayor que el subtotal desglosado."""
    _, headers_conductor, _viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf-desg1", telefono="+593970300021", vehiculo_id="vf-desg1", placa="FIN0021"
    )

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 200
    body = resp.json()
    desglose = body["desglose_tarifa"]
    assert desglose is not None
    assert desglose["arrancada"] == 0.5
    # Los 3 rubros ya redondeados deben sumar exacto al subtotal.
    assert round(desglose["arrancada"] + desglose["distancia"] + desglose["espera"], 2) == desglose["subtotal"]
    # Viaje corto: el subtotal no alcanza la carrera mínima -> el piso se
    # aplicó, tarifa_final queda por encima del subtotal desglosado.
    assert desglose["subtotal"] < body["tarifa_final"]
    assert body["tarifa_final"] == 1.5


async def test_finalizar_viaje_desglosa_tarifa_sin_piso_aplicado(client, db, redis):
    """Viaje con distancia real suficiente para superar la carrera_minima
    (1.5 DIURNA) sin necesidad del piso -- subtotal == tarifa_final."""
    _, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf-desg2", telefono="+593970300022", vehiculo_id="vf-desg2", placa="FIN0022"
    )
    # 2 reportes consecutivos de ~0.015 grados (~1.67 km) cada uno -- cada
    # salto individual queda bajo el umbral anti-spoofing de
    # `flota/service.py::_SALTO_IMPOSIBLE_KM` (3 km), pero la suma acumulada
    # (~3.3 km) alcanza para que 0.5 (arrancada) + 0.35 * km > 1.5 sin
    # necesidad del piso.
    await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": -0.2001,
            "lon": -78.5001,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:10Z",
        },
    )
    await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": -0.2151,
            "lon": -78.5001,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:15Z",
        },
    )
    viaje_antes = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_antes["km_recorridos"] > 2.857  # (1.5 - 0.5) / 0.35

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 200
    body = resp.json()
    desglose = body["desglose_tarifa"]
    assert desglose is not None
    assert desglose["subtotal"] == body["tarifa_final"]
    assert desglose["subtotal"] > 1.5


async def test_finalizar_viaje_suma_km_recorridos_al_vehiculo(client, db, redis):
    """Ronda 2, Fase B (H7): alimentación hacia adelante de
    vehiculos.km_acumulado -- antes de este cambio el campo nunca se
    escribía (confirmado en la auditoría: 81/81 vehículos reales en 0)."""
    _, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf-km1", telefono="+593970300091", vehiculo_id="vf-km1", placa="FINKM001"
    )
    # `_viaje_en_curso` ya manda un primer reporte de posición tras
    # "iniciar" (semilla de la traza, sin distancia acumulada todavía --
    # `registrar_punto_traza` necesita un punto ANTERIOR para poder
    # calcular una distancia). Un segundo reporte real es el que efectivamente
    # suma km_recorridos.
    await client.post(
        "/flota/posiciones",
        headers=headers_conductor,
        json={
            "lat": -0.1901,
            "lon": -78.5001,
            "precision_m": 10,
            "velocidad": 30,
            "ts_dispositivo": "2026-07-29T12:00:10Z",
        },
    )
    viaje_antes = await db.viajes.find_one({"_id": viaje_id})
    km_recorridos_antes_de_finalizar = viaje_antes["km_recorridos"]
    assert km_recorridos_antes_de_finalizar > 0

    vehiculo_antes = await db.vehiculos.find_one({"_id": "vf-km1"})
    assert (vehiculo_antes.get("km_acumulado") or 0.0) == 0.0

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)
    assert resp.status_code == 200

    vehiculo_despues = await db.vehiculos.find_one({"_id": "vf-km1"})
    assert vehiculo_despues["km_acumulado"] == km_recorridos_antes_de_finalizar


async def test_finalizar_viaje_sin_destino_usa_posicion_actual(client, db, redis):
    _, headers_conductor, _viaje_id = await _viaje_en_curso(
        client,
        db,
        redis,
        conductor_id="cf2",
        telefono="+593970300012",
        vehiculo_id="vf2",
        placa="FIN0002",
        con_destino=False,
    )

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 200
    body = resp.json()
    assert body["destino_lat"] is not None
    assert body["destino_lon"] is not None


async def test_finalizar_viaje_marca_revision_si_discrepancia_mayor_30(client, db, redis):
    _, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf3", telefono="+593970300013", vehiculo_id="vf3", placa="FIN0003"
    )
    # Fuerza una tarifa_estimada artificialmente baja para disparar revision_tarifa.
    await db.viajes.update_one({"_id": viaje_id}, {"$set": {"tarifa_estimada": 0.10}})

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 200
    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["revision_tarifa"] is True


async def test_finalizar_sin_estar_en_curso_devuelve_409(client, db, redis):
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="cf4",
        telefono="+593970300014",
        vehiculo_id="vf4",
        placa="FIN0004",
        estado_servicio="DISPONIBLE",
    )
    headers_conductor = auth_headers("cf4", ["conductor"])

    resp = await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    assert resp.status_code == 409
    assert resp.json()["code"] == "TRANSICION_INVALIDA"


async def test_calificar_viaje_ambas_direcciones_actualiza_promedio(client, db, redis):
    headers_pasajero, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf5", telefono="+593970300015", vehiculo_id="vf5", placa="FIN0005"
    )
    await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    resp_pasajero = await client.post(
        f"/viajes/{viaje_id}/calificar", headers=headers_pasajero, json={"puntaje": 5, "comentario": "Excelente"}
    )
    assert resp_pasajero.status_code == 200
    assert resp_pasajero.json()["calificacion_pasajero_a_conductor"]["puntaje"] == 5

    resp_conductor = await client.post(
        f"/viajes/{viaje_id}/calificar", headers=headers_conductor, json={"puntaje": 4, "comentario": None}
    )
    assert resp_conductor.status_code == 200
    assert resp_conductor.json()["calificacion_conductor_a_pasajero"]["puntaje"] == 4

    conductor_db = await db.usuarios.find_one({"_id": "cf5"})
    assert conductor_db["conductor"]["calificacion_promedio"] == 5.0

    pasajero_db = await db.usuarios.find_one({"_id": "pf1"})
    assert pasajero_db["pasajero"]["calificacion_promedio"] == 4.0


async def test_calificar_dos_veces_devuelve_409(client, db, redis):
    headers_pasajero, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf6", telefono="+593970300016", vehiculo_id="vf6", placa="FIN0006"
    )
    await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    await client.post(f"/viajes/{viaje_id}/calificar", headers=headers_pasajero, json={"puntaje": 5})
    resp = await client.post(f"/viajes/{viaje_id}/calificar", headers=headers_pasajero, json={"puntaje": 3})

    assert resp.status_code == 409
    assert resp.json()["code"] == "YA_CALIFICADO"


async def test_calificar_viaje_no_finalizado_devuelve_409(client, db, redis):
    headers_pasajero, _, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf7", telefono="+593970300017", vehiculo_id="vf7", placa="FIN0007"
    )
    # No se llama a /finalizar — el viaje sigue EN_CURSO.

    resp = await client.post(f"/viajes/{viaje_id}/calificar", headers=headers_pasajero, json={"puntaje": 5})

    assert resp.status_code == 409
    assert resp.json()["code"] == "VIAJE_NO_CALIFICABLE"


async def test_obtener_viaje_por_id_tras_finalizar(client, db, redis):
    """GET /viajes/{id} es lo único que permite al pasajero enterarse de la
    transición a FINALIZADO — /viajes/activo deja de incluirlo por diseño
    (ver comentario en router_finalizacion.py)."""
    headers_pasajero, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="cf8", telefono="+593970300018", vehiculo_id="vf8", placa="FIN0008"
    )
    await client.post("/viajes/conductor/finalizar", headers=headers_conductor)

    resp_pasajero = await client.get(f"/viajes/{viaje_id}", headers=headers_pasajero)
    assert resp_pasajero.status_code == 200
    assert resp_pasajero.json()["estado"] == "FINALIZADO"

    resp_conductor = await client.get(f"/viajes/{viaje_id}", headers=headers_conductor)
    assert resp_conductor.status_code == 200

    headers_extrano = await _pasajero_headers(db, usuario_id="pf-extrano", telefono="+593970300099")
    resp_extrano = await client.get(f"/viajes/{viaje_id}", headers=headers_extrano)
    assert resp_extrano.status_code == 404


async def test_ruta_dinamica_viaje_id_no_sombrea_oferta_actual(client, db, redis):
    """Regresión: GET /viajes/{id} está registrada en el último router
    montado precisamente para no capturar rutas literales como
    /viajes/oferta-actual de otros routers — si el orden de montaje en
    main.py cambiara, este test debe fallar con SIN_OFERTA_ACTIVA (404 del
    endpoint correcto) y no con un 200/404 del endpoint equivocado."""
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="cf9",
        telefono="+593970300019",
        vehiculo_id="vf9",
        placa="FIN0009",
        estado_servicio="DISPONIBLE",
    )
    headers_conductor = auth_headers("cf9", ["conductor"])

    resp = await client.get("/viajes/oferta-actual", headers=headers_conductor)

    assert resp.status_code == 404
    assert resp.json()["code"] == "SIN_OFERTA_ACTIVA"
