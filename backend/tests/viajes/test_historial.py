from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _pasajero_headers(db, usuario_id="ph1", telefono="+593970400001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


def _viaje_terminal(*, viaje_id, pasajero_id, conductor_id, estado, ts_solicitud, tarifa_final=None):
    return {
        "_id": viaje_id,
        "pasajero_id": pasajero_id,
        "conductor_id": conductor_id,
        "vehiculo_id": "veh-hist" if conductor_id else None,
        "estado": estado,
        "origen_lat": -0.18,
        "origen_lon": -78.5,
        "origen_direccion": "Origen",
        "destino_lat": None,
        "destino_lon": None,
        "destino_direccion": None,
        "franja": "DIURNA",
        "ts_solicitud": ts_solicitud,
        "ts_asignacion": None,
        "ts_llegada_origen": None,
        "ts_inicio": None,
        "ts_fin": None,
        "km_recorridos": None,
        "min_espera": None,
        "tarifa_estimada": None,
        "tarifa_final": tarifa_final,
        "motivo_cancelacion": None,
        "conductor_nombre": None,
        "conductor_calificacion": None,
        "vehiculo_placa": None,
        "vehiculo_marca": None,
        "vehiculo_color": None,
        "calificacion_pasajero_a_conductor": None,
        "calificacion_conductor_a_pasajero": None,
    }


async def test_pasajero_lista_su_historial_excluye_viajes_activos(client, db):
    headers = await _pasajero_headers(db)
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="h1",
                pasajero_id="ph1",
                conductor_id="c1",
                estado="FINALIZADO",
                ts_solicitud=ahora,
                tarifa_final=3.5,
            ),
            _viaje_terminal(
                viaje_id="h2",
                pasajero_id="ph1",
                conductor_id="c1",
                estado="CANCELADO",
                ts_solicitud=ahora - timedelta(hours=1),
            ),
            _viaje_terminal(
                viaje_id="h3", pasajero_id="ph1", conductor_id=None, estado="SOLICITADO", ts_solicitud=ahora
            ),
        ]
    )

    resp = await client.get("/viajes", headers=headers, params={"rol": "pasajero"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [v["id"] for v in body["viajes"]]
    assert "h3" not in ids
    assert ids == ["h1", "h2"]  # orden descendente por ts_solicitud


async def test_filtrar_historial_por_estado(client, db):
    headers = await _pasajero_headers(db, usuario_id="ph2", telefono="+593970400002")
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="h4", pasajero_id="ph2", conductor_id="c2", estado="FINALIZADO", ts_solicitud=ahora
            ),
            _viaje_terminal(
                viaje_id="h5", pasajero_id="ph2", conductor_id="c2", estado="CANCELADO", ts_solicitud=ahora
            ),
        ]
    )

    resp = await client.get("/viajes", headers=headers, params={"rol": "pasajero", "estado": "FINALIZADO"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "h4"


async def test_filtrar_historial_por_rango_de_fechas(client, db):
    headers = await _pasajero_headers(db, usuario_id="ph3", telefono="+593970400003")
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="h6",
                pasajero_id="ph3",
                conductor_id="c3",
                estado="FINALIZADO",
                ts_solicitud=ahora - timedelta(days=10),
            ),
            _viaje_terminal(
                viaje_id="h7", pasajero_id="ph3", conductor_id="c3", estado="FINALIZADO", ts_solicitud=ahora
            ),
        ]
    )

    desde = (ahora - timedelta(days=1)).isoformat()
    resp = await client.get("/viajes", headers=headers, params={"rol": "pasajero", "desde": desde})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "h7"


async def test_paginacion_de_historial(client, db):
    headers = await _pasajero_headers(db, usuario_id="ph4", telefono="+593970400004")
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id=f"h-pag-{i}",
                pasajero_id="ph4",
                conductor_id="c4",
                estado="FINALIZADO",
                ts_solicitud=ahora - timedelta(minutes=i),
            )
            for i in range(5)
        ]
    )

    resp = await client.get("/viajes", headers=headers, params={"rol": "pasajero", "pagina": 2, "limite": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["viajes"]) == 2
    assert body["viajes"][0]["id"] == "h-pag-2"  # salta los 2 primeros (página 1)


async def test_conductor_lista_historial_ve_nombre_de_pila_del_pasajero(client, db):
    await crear_usuario_activo(db, usuario_id="ph5", telefono="+593970400005", roles=["pasajero"])
    await db.usuarios.update_one(
        {"_id": "ph5"},
        {"$set": {"nombre": "María Fernanda López", "pasajero": {"calificacion_promedio": 4.5}}},
    )
    await crear_conductor_con_vehiculo(
        db, conductor_id="c5", telefono="+593970400015", vehiculo_id="v5", placa="HIS0005"
    )
    headers_conductor = auth_headers("c5", ["conductor"])

    await db.viajes.insert_one(
        _viaje_terminal(
            viaje_id="h8", pasajero_id="ph5", conductor_id="c5", estado="FINALIZADO", ts_solicitud=datetime.now(UTC)
        )
    )

    resp = await client.get("/viajes", headers=headers_conductor, params={"rol": "conductor"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["viajes"][0]["pasajero_nombre"] == "María"
    assert body["viajes"][0]["pasajero_calificacion"] == 4.5


async def test_conductor_lista_historial_ve_foto_del_pasajero(client, db):
    """Ronda de fotos en historial/usuarios: `pasajero_foto_url` viaja junto
    al resto de la "contraparte limitada" de CU-O14 A2 -- mismo tipo de dato
    de identidad visual que ya expone `pasajero_nombre`, resuelto en tiempo
    de consulta desde `usuarios.foto_url` (nunca un mecanismo de foto
    aparte)."""
    await crear_usuario_activo(db, usuario_id="ph-foto1", telefono="+593970400025", roles=["pasajero"])
    await db.usuarios.update_one({"_id": "ph-foto1"}, {"$set": {"foto_url": "archivo-foto-pasajero-1"}})
    await crear_conductor_con_vehiculo(
        db, conductor_id="c-foto1", telefono="+593970400026", vehiculo_id="v-foto1", placa="HISFOTO1"
    )
    headers_conductor = auth_headers("c-foto1", ["conductor"])

    await db.viajes.insert_one(
        _viaje_terminal(
            viaje_id="h-foto1",
            pasajero_id="ph-foto1",
            conductor_id="c-foto1",
            estado="FINALIZADO",
            ts_solicitud=datetime.now(UTC),
        )
    )

    resp = await client.get("/viajes", headers=headers_conductor, params={"rol": "conductor"})

    assert resp.status_code == 200
    assert resp.json()["viajes"][0]["pasajero_foto_url"] == "archivo-foto-pasajero-1"


async def test_detalle_de_viaje_para_conductor_incluye_pasajero(client, db):
    await crear_usuario_activo(db, usuario_id="ph6", telefono="+593970400006", roles=["pasajero"])
    await db.usuarios.update_one({"_id": "ph6"}, {"$set": {"nombre": "Carlos Andrade"}})
    await crear_conductor_con_vehiculo(
        db, conductor_id="c6", telefono="+593970400016", vehiculo_id="v6", placa="HIS0006"
    )
    headers_conductor = auth_headers("c6", ["conductor"])

    await db.viajes.insert_one(
        _viaje_terminal(
            viaje_id="h9", pasajero_id="ph6", conductor_id="c6", estado="FINALIZADO", ts_solicitud=datetime.now(UTC)
        )
    )

    resp = await client.get("/viajes/h9", headers=headers_conductor)

    assert resp.status_code == 200
    assert resp.json()["pasajero_nombre"] == "Carlos"


async def test_solicitar_historial_con_rol_no_disponible_devuelve_403(client, db):
    headers = await _pasajero_headers(db, usuario_id="ph7", telefono="+593970400007")

    resp = await client.get("/viajes", headers=headers, params={"rol": "conductor"})

    assert resp.status_code == 403
    assert resp.json()["code"] == "ROL_NO_DISPONIBLE"
