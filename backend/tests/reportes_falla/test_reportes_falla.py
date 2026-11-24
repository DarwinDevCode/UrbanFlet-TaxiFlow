from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _sembrar_tipo_falla(db, *, nombre="Falla mecánica") -> str:
    await db.motivos_cancelacion.insert_one(
        {"_id": "mot-falla-1", "nombre": nombre, "descripcion": "", "categoria": "incidencia", "activo": True}
    )
    return nombre


async def _sembrar_jefe_mantenimiento(db) -> None:
    await crear_usuario_activo(db, usuario_id="jefe-mant-1", telefono="+593970500001", roles=["jefe_mantenimiento"])


async def _sembrar_coordinador_operaciones(db) -> None:
    await crear_usuario_activo(
        db, usuario_id="coord-ops-1", telefono="+593970500002", roles=["coordinador_operaciones"]
    )


async def _sembrar_tarifas(client, db):
    await crear_usuario_activo(db, usuario_id="admin-tarifa-rf", telefono="+593970599999", roles=["admin_plataforma"])
    headers_admin = auth_headers("admin-tarifa-rf", ["admin_plataforma"])
    for franja, valores in (
        ("DIURNA", {"arrancada": 0.5, "costo_km": 0.35, "costo_min_espera": 0.07, "carrera_minima": 1.5}),
        ("NOCTURNA", {"arrancada": 0.6, "costo_km": 0.4, "costo_min_espera": 0.09, "carrera_minima": 1.75}),
    ):
        await client.post(
            "/parametros/tarifas",
            headers=headers_admin,
            json={**valores, "franja": franja, "vigente_desde": "2020-01-01T00:00:00Z"},
        )


async def _viaje_en_curso(client, db, redis, *, conductor_id, telefono, vehiculo_id, placa, lat=-0.1801, lon=-78.5001):
    await _sembrar_tarifas(client, db)
    await crear_usuario_activo(db, usuario_id="pas-rf-1", telefono="+593970600001", roles=["pasajero"])
    headers_pasajero = auth_headers("pas-rf-1", ["pasajero"])
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
        json={
            "origen_lat": lat,
            "origen_lon": lon,
            "origen_direccion": "Origen",
            "destino_lat": lat - 0.01,
            "destino_lon": lon,
            "destino_direccion": "Destino",
        },
    )
    viaje_id = creado.json()["id"]

    await client.post("/viajes/oferta/responder", headers=headers_conductor, json={"aceptar": True})
    await client.post("/viajes/conductor/en-camino", headers=headers_conductor)
    await client.post("/viajes/conductor/iniciar", headers=headers_conductor)

    return headers_pasajero, headers_conductor, viaje_id


async def test_reportar_falla_sin_viaje_activo_queda_pendiente_y_notifica_al_jefe(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await _sembrar_jefe_mantenimiento(db)
    await _sembrar_coordinador_operaciones(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf1", telefono="+593970700001", vehiculo_id="vrf1", placa="RFA0001"
    )
    headers = auth_headers("crf1", ["conductor"])

    resp = await client.post(
        "/reportes-falla",
        headers=headers,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "Ruido raro en el motor",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": False,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "PENDIENTE"
    assert body["viaje_id"] is None
    assert body["vehiculo_id"] == "vrf1"
    assert body["vehiculo_placa"] == "RFA0001"

    reporte_db = await db.reportes_falla.find_one({"_id": body["id"]})
    assert reporte_db is not None
    assert reporte_db["conductor_id"] == "crf1"

    notificacion = await db.notificaciones_usuario.find_one({"usuario_id": "jefe-mant-1"})
    assert notificacion is not None
    assert notificacion["payload"]["tipo_alerta"] == "reporte_falla"

    # CU-O07 A4: aviso en vivo, independiente del anterior, al Coordinador
    # de Operaciones -- se dispara siempre, no solo cuando hay viaje o
    # cuando impide_continuar=true.
    notificacion_ops = await db.notificaciones_usuario.find_one({"usuario_id": "coord-ops-1"})
    assert notificacion_ops is not None
    assert notificacion_ops["payload"]["tipo_alerta"] == "incidencia_operativa"


async def test_reportar_falla_impide_continuar_sin_viaje_no_pasa_a_ningun_lado_mas(client, db):
    """Sin viaje EN_CURSO, `impide_continuar=true` no tiene ningún viaje que
    cancelar -- el reporte igual se crea normalmente."""
    tipo_falla = await _sembrar_tipo_falla(db)
    await _sembrar_jefe_mantenimiento(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf2", telefono="+593970700002", vehiculo_id="vrf2", placa="RFA0002"
    )
    headers = auth_headers("crf2", ["conductor"])

    resp = await client.post(
        "/reportes-falla",
        headers=headers,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "No enciende",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": True,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["estado"] == "PENDIENTE"


async def test_reportar_falla_durante_viaje_sin_impedir_continuar_no_cancela(client, db, redis):
    tipo_falla = await _sembrar_tipo_falla(db)
    await _sembrar_jefe_mantenimiento(db)
    _, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="crf3", telefono="+593970700003", vehiculo_id="vrf3", placa="RFA0003"
    )

    resp = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "Luz de aceite encendida, pero se puede seguir",
            "lat": -0.185,
            "lon": -78.5,
            "impide_continuar": False,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["viaje_id"] == viaje_id

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["estado"] == "EN_CURSO"


async def test_reportar_falla_impide_continuar_en_curso_cancela_y_redespacha(client, db, redis):
    """CU-O07 A4: el viaje EN_CURSO se cancela con motivo INCIDENCIA y se
    crea una nueva solicitud automática para el mismo pasajero desde la
    posición del incidente."""
    tipo_falla = await _sembrar_tipo_falla(db)
    await _sembrar_jefe_mantenimiento(db)
    await _sembrar_coordinador_operaciones(db)
    headers_pasajero, headers_conductor, viaje_id = await _viaje_en_curso(
        client, db, redis, conductor_id="crf4", telefono="+593970700004", vehiculo_id="vrf4", placa="RFA0004"
    )

    resp = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "Pinchazo, no puedo continuar",
            "lat": -0.186,
            "lon": -78.501,
            "impide_continuar": True,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["viaje_id"] == viaje_id
    assert body["impide_continuar"] is True

    viaje_viejo = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_viejo["estado"] == "CANCELADO"
    assert viaje_viejo["motivo_cancelacion"] == "INCIDENCIA"
    assert viaje_viejo["actor_cancelacion"] == "conductor"

    conductor_db = await db.usuarios.find_one({"_id": "crf4"})
    assert conductor_db["conductor"]["estado_servicio"] == "DISPONIBLE"

    nuevo_viaje = await db.viajes.find_one(
        {"pasajero_id": "pas-rf-1", "_id": {"$ne": viaje_id}, "ts_solicitud": {"$exists": True}}
    )
    assert nuevo_viaje is not None
    assert nuevo_viaje["origen_lat"] == -0.186
    assert nuevo_viaje["origen_lon"] == -78.501
    assert nuevo_viaje["estado"] in ("SOLICITADO", "OFERTADO", "ASIGNADO", "SIN_CONDUCTOR")

    resp_activo = await client.get("/viajes/activo", headers=headers_pasajero)
    assert resp_activo.status_code == 200
    assert resp_activo.json()["id"] == nuevo_viaje["_id"]

    # CU-O07 A4: el aviso al Coordinador de Operaciones se dispara también
    # en este caso (con viaje activo, impide_continuar=true) -- no está
    # condicionado a que el viaje se cancele o no.
    notificacion_ops = await db.notificaciones_usuario.find_one({"usuario_id": "coord-ops-1"})
    assert notificacion_ops is not None
    assert notificacion_ops["payload"]["tipo_alerta"] == "incidencia_operativa"


async def test_reportar_falla_tipo_invalido_devuelve_422(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf5", telefono="+593970700005", vehiculo_id="vrf5", placa="RFA0005"
    )
    headers = auth_headers("crf5", ["conductor"])

    resp = await client.post(
        "/reportes-falla",
        headers=headers,
        json={
            "tipo_falla": "Motivo inexistente",
            "descripcion": "x",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": False,
        },
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "TIPO_FALLA_INVALIDO"


async def test_reportar_falla_sin_vehiculo_asignado_devuelve_404(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_usuario_activo(db, usuario_id="crf6", telefono="+593970700006", roles=["conductor"])
    headers = auth_headers("crf6", ["conductor"])

    resp = await client.post(
        "/reportes-falla",
        headers=headers,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "x",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": False,
        },
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "VEHICULO_NO_ASIGNADO"


async def _jefe_headers(db, *, usuario_id="jefe-mant-fase-d", telefono="+593970800001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["jefe_mantenimiento"])
    return auth_headers(usuario_id, ["jefe_mantenimiento"])


async def test_bandeja_lista_solo_pendientes_y_gatea_a_jefe_mantenimiento(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf8", telefono="+593970700008", vehiculo_id="vrf8", placa="RFA0008"
    )
    headers_conductor = auth_headers("crf8", ["conductor"])
    await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={"tipo_falla": tipo_falla, "descripcion": "x", "lat": -0.19, "lon": -78.5, "impide_continuar": False},
    )

    resp_conductor = await client.get("/reportes-falla", headers=headers_conductor)
    assert resp_conductor.status_code == 403

    headers_jefe = await _jefe_headers(db)
    resp_jefe = await client.get("/reportes-falla?estado=PENDIENTE", headers=headers_jefe)
    assert resp_jefe.status_code == 200
    reportes = resp_jefe.json()
    assert len(reportes) == 1
    assert reportes[0]["vehiculo_placa"] == "RFA0008"
    assert reportes[0]["estado"] == "PENDIENTE"


async def test_convertir_reporte_en_orden_hereda_vehiculo_descripcion_y_evidencia(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf9", telefono="+593970700009", vehiculo_id="vrf9", placa="RFA0009"
    )
    headers_conductor = auth_headers("crf9", ["conductor"])

    subida = await client.post(
        "/archivos",
        headers=headers_conductor,
        data={"contexto": "reporte_falla"},
        files={"file": ("falla.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    creado = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "Fuga de aceite visible bajo el motor",
            "lat": -0.19123,
            "lon": -78.50456,
            "impide_continuar": False,
            "evidencias": [archivo_id],
        },
    )
    reporte_id = creado.json()["id"]

    headers_jefe = await _jefe_headers(db)
    conv = await client.post(
        f"/reportes-falla/{reporte_id}/convertir",
        headers=headers_jefe,
        json={
            "taller": "Taller Central",
            "fecha_programada": "2026-08-20",
            "km_entrada": 45000,
            "retirar_vehiculo": False,
        },
    )
    assert conv.status_code == 200
    body = conv.json()
    assert body["estado"] == "CONVERTIDO_A_ORDEN"
    assert body["orden_id"] is not None

    orden_db = await db.ordenes.find_one({"_id": body["orden_id"]})
    assert orden_db is not None
    assert orden_db["vehiculo_id"] == "vrf9"
    assert orden_db["tipo"] == "CORRECTIVA"
    assert orden_db["estado"] == "ABIERTA"
    assert orden_db["km_entrada"] == 45000
    assert orden_db["taller"] == "Taller Central"
    assert orden_db["evidencias"] == [archivo_id]
    assert tipo_falla in orden_db["descripcion"]
    assert "Fuga de aceite visible bajo el motor" in orden_db["descripcion"]

    reporte_db = await db.reportes_falla.find_one({"_id": reporte_id})
    assert reporte_db["estado"] == "CONVERTIDO_A_ORDEN"
    assert reporte_db["orden_id"] == body["orden_id"]

    # Convertir un reporte ya resuelto (segundo intento) debe fallar.
    conv_repetido = await client.post(
        f"/reportes-falla/{reporte_id}/convertir",
        headers=headers_jefe,
        json={"taller": "Taller Central", "fecha_programada": "2026-08-21", "km_entrada": 45010},
    )
    assert conv_repetido.status_code == 409
    assert conv_repetido.json()["code"] == "REPORTE_FALLA_YA_RESUELTO"


async def test_descartar_reporte_exige_motivo_y_marca_estado(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf10", telefono="+593970700010", vehiculo_id="vrf10", placa="RFA0010"
    )
    headers_conductor = auth_headers("crf10", ["conductor"])
    creado = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={"tipo_falla": tipo_falla, "descripcion": "x", "lat": -0.19, "lon": -78.5, "impide_continuar": False},
    )
    reporte_id = creado.json()["id"]

    headers_jefe = await _jefe_headers(db)
    sin_motivo = await client.post(f"/reportes-falla/{reporte_id}/descartar", headers=headers_jefe, json={"motivo": ""})
    assert sin_motivo.status_code == 422

    resp = await client.post(
        f"/reportes-falla/{reporte_id}/descartar",
        headers=headers_jefe,
        json={"motivo": "Duplicado del reporte anterior"},
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "DESCARTADO"

    reporte_db = await db.reportes_falla.find_one({"_id": reporte_id})
    assert reporte_db["estado"] == "DESCARTADO"
    assert reporte_db["motivo_descarte"] == "Duplicado del reporte anterior"

    # Ya no aparece en la bandeja de PENDIENTE.
    bandeja = await client.get("/reportes-falla?estado=PENDIENTE", headers=headers_jefe)
    assert all(r["id"] != reporte_id for r in bandeja.json())


async def test_reportar_falla_con_evidencia_queda_referenciada_y_es_visible(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await _sembrar_jefe_mantenimiento(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf7", telefono="+593970700007", vehiculo_id="vrf7", placa="RFA0007"
    )
    headers = auth_headers("crf7", ["conductor"])

    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("falla.jpg", b"\xff\xd8\xff" + b"0" * 100, "image/jpeg")},
    )
    assert subida.status_code == 201
    archivo_id = subida.json()["id"]

    resp = await client.post(
        "/reportes-falla",
        headers=headers,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "Con foto",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": False,
            "evidencias": [archivo_id],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["evidencias"] == [archivo_id]

    # El propio conductor (propietario del archivo) puede verlo después.
    ver = await client.get(f"/archivos/{archivo_id}", headers=headers)
    assert ver.status_code == 200

    # El Jefe de Mantenimiento (rol del contexto "reporte_falla") también.
    await crear_usuario_activo(db, usuario_id="jefe-mant-7", telefono="+593970500007", roles=["jefe_mantenimiento"])
    headers_jefe = auth_headers("jefe-mant-7", ["jefe_mantenimiento"])
    ver_jefe = await client.get(f"/archivos/{archivo_id}", headers=headers_jefe)
    assert ver_jefe.status_code == 200


async def test_mis_reportes_solo_devuelve_los_del_conductor_autenticado(client, db):
    """Grupo B de la ronda de correcciones UX/UI: el conductor ahora puede
    consultar sus propios reportes. El filtro sale del token, nunca de un id
    del cliente -- un conductor no ve los reportes de otro, ni la bandeja
    completa que sí ve el Jefe de Mantenimiento."""
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf20", telefono="+593970700020", vehiculo_id="vrf20", placa="RFA0020"
    )
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf21", telefono="+593970700021", vehiculo_id="vrf21", placa="RFA0021"
    )
    headers_uno = auth_headers("crf20", ["conductor"])
    headers_otro = auth_headers("crf21", ["conductor"])

    for headers in (headers_uno, headers_otro):
        resp = await client.post(
            "/reportes-falla",
            headers=headers,
            json={
                "tipo_falla": tipo_falla,
                "descripcion": "ruido raro",
                "lat": -0.19,
                "lon": -78.5,
                "impide_continuar": False,
            },
        )
        assert resp.status_code == 201

    mios = await client.get("/reportes-falla/mias", headers=headers_uno)
    assert mios.status_code == 200
    assert [r["vehiculo_placa"] for r in mios.json()] == ["RFA0020"]

    del_otro = await client.get("/reportes-falla/mias", headers=headers_otro)
    assert [r["vehiculo_placa"] for r in del_otro.json()] == ["RFA0021"]

    # La bandeja completa sigue siendo exclusiva del Jefe de Mantenimiento.
    assert (await client.get("/reportes-falla", headers=headers_uno)).status_code == 403

    headers_jefe = await _jefe_headers(db, usuario_id="jefe-mant-mias", telefono="+593970800020")
    assert (await client.get("/reportes-falla/mias", headers=headers_jefe)).status_code == 403


# ---------------------------------------------------------------------------
# Ronda "corrección acotada por estado"
# ---------------------------------------------------------------------------


async def test_corregir_reporte_pendiente_cambia_tipo_y_descripcion(client, db):
    tipo_falla = await _sembrar_tipo_falla(db, nombre="Falla mecánica")
    tipo_falla_correcto = "Falla eléctrica"
    await db.motivos_cancelacion.insert_one(
        {
            "_id": "mot-falla-2",
            "nombre": tipo_falla_correcto,
            "descripcion": "",
            "categoria": "incidencia",
            "activo": True,
        }
    )
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf-corr-1", telefono="+593970700020", vehiculo_id="vrf-corr-1", placa="RFC0001"
    )
    headers_conductor = auth_headers("crf-corr-1", ["conductor"])
    creado = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={
            "tipo_falla": tipo_falla,
            "descripcion": "texto con typo",
            "lat": -0.19,
            "lon": -78.5,
            "impide_continuar": False,
        },
    )
    reporte_id = creado.json()["id"]

    headers_jefe = await _jefe_headers(db)
    resp = await client.patch(
        f"/reportes-falla/{reporte_id}/correccion",
        headers=headers_jefe,
        json={
            "tipo_falla": tipo_falla_correcto,
            "descripcion": "texto corregido",
            "motivo": "Error de tipeo del conductor",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["tipo_falla"] == tipo_falla_correcto
    assert resp.json()["descripcion"] == "texto corregido"

    evento = await db.bitacora.find_one({"accion": "REPORTE_FALLA_CORRECCION", "entidad_id": reporte_id})
    assert evento is not None
    assert evento["datos_previos"]["tipo_falla"] == tipo_falla
    assert evento["datos_posteriores"]["tipo_falla"] == tipo_falla_correcto
    assert evento["datos_posteriores"]["motivo"] == "Error de tipeo del conductor"


async def test_corregir_reporte_ya_convertido_da_409(client, db):
    tipo_falla = await _sembrar_tipo_falla(db)
    await crear_conductor_con_vehiculo(
        db, conductor_id="crf-corr-2", telefono="+593970700021", vehiculo_id="vrf-corr-2", placa="RFC0002"
    )
    headers_conductor = auth_headers("crf-corr-2", ["conductor"])
    creado = await client.post(
        "/reportes-falla",
        headers=headers_conductor,
        json={"tipo_falla": tipo_falla, "descripcion": "x", "lat": -0.19, "lon": -78.5, "impide_continuar": False},
    )
    reporte_id = creado.json()["id"]
    headers_jefe = await _jefe_headers(db)
    await client.post(
        f"/reportes-falla/{reporte_id}/convertir",
        headers=headers_jefe,
        json={"taller": "Taller Central", "fecha_programada": "2026-08-20", "km_entrada": 1000},
    )

    resp = await client.patch(
        f"/reportes-falla/{reporte_id}/correccion",
        headers=headers_jefe,
        json={"descripcion": "ya no debería poder", "motivo": "intento tardío"},
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "REPORTE_FALLA_YA_RESUELTO"
