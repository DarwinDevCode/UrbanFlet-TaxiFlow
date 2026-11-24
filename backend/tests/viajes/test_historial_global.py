from datetime import UTC, datetime, timedelta

import pytest

from tests.utils import auth_headers, crear_usuario_activo


def _viaje_terminal(*, viaje_id, pasajero_id, conductor_id, conductor_nombre, estado, ts_solicitud):
    return {
        "_id": viaje_id,
        "pasajero_id": pasajero_id,
        "conductor_id": conductor_id,
        "vehiculo_id": "veh-hg" if conductor_id else None,
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
        "tarifa_final": None,
        "motivo_cancelacion": None,
        "conductor_nombre": conductor_nombre,
        "conductor_calificacion": None,
        "vehiculo_placa": None,
        "vehiculo_marca": None,
        "vehiculo_color": None,
        "calificacion_pasajero_a_conductor": None,
        "calificacion_conductor_a_pasajero": None,
    }


async def _coordinador(db):
    await crear_usuario_activo(db, usuario_id="coord-hg-1", telefono="+593900003000", roles=["coordinador_operaciones"])
    return auth_headers("coord-hg-1", ["coordinador_operaciones"])


async def test_historial_global_requiere_rol_autorizado(client, db):
    await crear_usuario_activo(db, usuario_id="pasajero-hg-1", telefono="+593900003001", roles=["pasajero"])
    headers = auth_headers("pasajero-hg-1", ["pasajero"])

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 403


async def test_historial_global_incluye_viajes_de_cualquier_pasajero(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-a", telefono="+593900003002", roles=["pasajero"])
    await crear_usuario_activo(db, usuario_id="p-hg-b", telefono="+593900003003", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-1", pasajero_id="p-hg-a", conductor_id="c-hg-1", conductor_nombre="Juan Pérez",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-2", pasajero_id="p-hg-b", conductor_id="c-hg-2", conductor_nombre="Pedro Ruiz",
                estado="CANCELADO", ts_solicitud=ahora - timedelta(hours=1),
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = {v["id"] for v in body["viajes"]}
    assert ids == {"hg-1", "hg-2"}


async def test_historial_global_filtra_por_estado(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-c", telefono="+593900003004", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-3", pasajero_id="p-hg-c", conductor_id="c-hg-3", conductor_nombre="Ana Sosa",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-4", pasajero_id="p-hg-c", conductor_id="c-hg-3", conductor_nombre="Ana Sosa",
                estado="SIN_CONDUCTOR", ts_solicitud=ahora,
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers, params={"estado": "SIN_CONDUCTOR"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "hg-4"


async def test_historial_global_busca_por_texto_de_pasajero_o_conductor(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-maria", telefono="+593900003005", roles=["pasajero"])
    await db.usuarios.update_one({"_id": "p-hg-maria"}, {"$set": {"nombre": "María Fernanda Torres"}})
    await crear_usuario_activo(db, usuario_id="p-hg-otro", telefono="+593900003006", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-5", pasajero_id="p-hg-maria", conductor_id="c-hg-5", conductor_nombre="Luis Vera",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-6", pasajero_id="p-hg-otro", conductor_id="c-hg-6", conductor_nombre="Otro Conductor",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers, params={"texto": "María"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "hg-5"
    assert body["viajes"][0]["pasajero_nombre"] == "María"


async def test_historial_global_incluye_foto_de_ambos_participantes(client, db):
    """Ronda de fotos en historial/usuarios: `conductor_foto_url` viene
    snapshoteado en el propio documento del viaje (igual que
    `conductor_nombre`), `pasajero_foto_url` se resuelve en tiempo de
    consulta (igual que `pasajero_nombre`, ver `enriquecer_con_pasajero`)."""
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-foto", telefono="+593900003009", roles=["pasajero"])
    await db.usuarios.update_one({"_id": "p-hg-foto"}, {"$set": {"foto_url": "archivo-foto-pasajero-hg"}})
    viaje = _viaje_terminal(
        viaje_id="hg-foto1", pasajero_id="p-hg-foto", conductor_id="c-hg-foto", conductor_nombre="Chofer Foto",
        estado="FINALIZADO", ts_solicitud=datetime.now(UTC),
    )
    viaje["conductor_foto_url"] = "archivo-foto-conductor-hg"
    await db.viajes.insert_one(viaje)

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    fila = resp.json()["viajes"][0]
    assert fila["conductor_foto_url"] == "archivo-foto-conductor-hg"
    assert fila["pasajero_foto_url"] == "archivo-foto-pasajero-hg"


async def test_historial_global_nunca_expone_telefono_del_pasajero(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-tel", telefono="+593900003007", roles=["pasajero"])
    await db.viajes.insert_one(
        _viaje_terminal(
            viaje_id="hg-7", pasajero_id="p-hg-tel", conductor_id="c-hg-7", conductor_nombre="Chofer Uno",
            estado="FINALIZADO", ts_solicitud=datetime.now(UTC),
        )
    )

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    assert "pasajero_telefono" not in resp.json()["viajes"][0]
    assert "+593900003007" not in resp.text


async def test_supervisor_cumplimiento_y_gerencia_tambien_pueden_ver(client, db):
    await crear_usuario_activo(db, usuario_id="cumpl-hg-1", telefono="+593900003008", roles=["supervisor_cumplimiento"])
    headers_cumplimiento = auth_headers("cumpl-hg-1", ["supervisor_cumplimiento"])
    resp1 = await client.get("/viajes/historial-global", headers=headers_cumplimiento)
    assert resp1.status_code == 200

    await crear_usuario_activo(db, usuario_id="gerencia-hg-1", telefono="+593900003009", roles=["gerencia"])
    headers_gerencia = auth_headers("gerencia-hg-1", ["gerencia"])
    resp2 = await client.get("/viajes/historial-global", headers=headers_gerencia)
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Mapa del historial (CU-O14 paso 3) — detalle con la traza GPS real.
# ---------------------------------------------------------------------------


def _con_traza(viaje: dict, puntos: list[tuple[float, float]]) -> dict:
    ts = datetime.now(UTC)
    return {**viaje, "traza": [{"lat": lat, "lon": lon, "ts": ts, "velocidad": 20.0} for lat, lon in puntos]}


async def test_detalle_historial_global_devuelve_la_traza_real(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-tz-1", telefono="+593900003100", roles=["pasajero"])
    viaje = _con_traza(
        _viaje_terminal(
            viaje_id="v-tz-1",
            pasajero_id="p-tz-1",
            conductor_id="c-tz-1",
            conductor_nombre="Conductor Traza",
            estado="PAGADO",
            ts_solicitud=datetime.now(UTC),
        ),
        [(-0.18, -78.5), (-0.181, -78.501), (-0.182, -78.502)],
    )
    await db.viajes.insert_one(viaje)

    resp = await client.get("/viajes/historial-global/v-tz-1", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["traza"] == [[-0.18, -78.5], [-0.181, -78.501], [-0.182, -78.502]]


async def test_la_lista_del_historial_global_nunca_serializa_la_traza(client, db):
    """La traza solo viaja en el detalle: en una lista de 20 filas multiplicaría
    el payload por cada viaje sin que ninguna pantalla la use ahí."""
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-tz-2", telefono="+593900003101", roles=["pasajero"])
    await db.viajes.insert_one(
        _con_traza(
            _viaje_terminal(
                viaje_id="v-tz-2",
                pasajero_id="p-tz-2",
                conductor_id="c-tz-2",
                conductor_nombre="Conductor Traza 2",
                estado="PAGADO",
                ts_solicitud=datetime.now(UTC),
            ),
            [(-0.18, -78.5), (-0.181, -78.501)],
        )
    )

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    fila = next(v for v in resp.json()["viajes"] if v["id"] == "v-tz-2")
    assert fila["traza"] is None


async def test_viaje_sin_traza_devuelve_none_y_no_una_recta_fabricada(client, db):
    """Regla central del mapa de historial: si el viaje nunca acumuló traza
    (cancelado antes de arrancar, o los históricos sembrados desde el dataset
    NYC, que nacen con `traza: []`), el backend devuelve `None`. Nunca une
    origen con destino como si fuera el recorrido real."""
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-tz-3", telefono="+593900003102", roles=["pasajero"])
    await db.viajes.insert_one(
        {
            **_viaje_terminal(
                viaje_id="v-tz-3",
                pasajero_id="p-tz-3",
                conductor_id=None,
                conductor_nombre=None,
                estado="SIN_CONDUCTOR",
                ts_solicitud=datetime.now(UTC),
            ),
            "traza": [],
        }
    )

    resp = await client.get("/viajes/historial-global/v-tz-3", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["traza"] is None


async def test_detalle_historial_global_requiere_rol_autorizado(client, db):
    await crear_usuario_activo(db, usuario_id="p-tz-4", telefono="+593900003103", roles=["pasajero"])
    headers = auth_headers("p-tz-4", ["pasajero"])

    resp = await client.get("/viajes/historial-global/v-tz-1", headers=headers)

    assert resp.status_code == 403


async def test_traza_muy_larga_se_muestrea_conservando_extremos(client, db):
    """El muestreo solo DESCARTA puntos reales -- nunca interpola uno nuevo --
    y conserva siempre el primero y el último."""
    from src.viajes.service_historial import TRAZA_MAX_PUNTOS_SALIDA, simplificar_traza

    cruda = [{"lat": -0.1 - i / 10000, "lon": -78.5, "ts": None} for i in range(5000)]
    salida = simplificar_traza(cruda)

    assert salida is not None
    assert len(salida) == TRAZA_MAX_PUNTOS_SALIDA
    assert salida[0] == (cruda[0]["lat"], cruda[0]["lon"])
    assert salida[-1] == (cruda[-1]["lat"], cruda[-1]["lon"])
    reales = {(p["lat"], p["lon"]) for p in cruda}
    assert all(punto in reales for punto in salida)


# ---------------------------------------------------------------------------
# RBAC del detalle: la traza GPS es un dato de ubicación sensible, así que el
# alcance se fija explícitamente en vez de confiar en que "es interno".
# El gate es EL MISMO objeto (`_historial_global_roles`) que el de la lista de
# la que se abre el detalle -- estos tests existen para que una edición futura
# no lo ensanche ni lo angoste sin que nadie lo note.
# ---------------------------------------------------------------------------

_ROLES_CON_ACCESO = ["coordinador_operaciones", "supervisor_cumplimiento", "gerencia", "admin_sistema"]
# Roles internos REALES que NO deben poder abrirlo: tampoco ven la lista, así
# que darles el detalle sería ensanchar el alcance por la puerta de atrás.
_ROLES_INTERNOS_SIN_ACCESO = ["coordinador_flota", "admin_captacion", "jefe_mantenimiento", "admin_financiero"]


async def _viaje_con_traza_fijo(db, viaje_id: str, pasajero_id: str):
    await crear_usuario_activo(db, usuario_id=pasajero_id, telefono=f"+59390000{viaje_id[-4:]}", roles=["pasajero"])
    await db.viajes.insert_one(
        _con_traza(
            _viaje_terminal(
                viaje_id=viaje_id,
                pasajero_id=pasajero_id,
                conductor_id="c-rbac",
                conductor_nombre="Conductor RBAC",
                estado="PAGADO",
                ts_solicitud=datetime.now(UTC),
            ),
            [(-0.18, -78.5), (-0.181, -78.501)],
        )
    )


@pytest.mark.parametrize("rol", _ROLES_CON_ACCESO)
async def test_detalle_historial_global_permite_exactamente_estos_roles(client, db, rol):
    await _viaje_con_traza_fijo(db, "v-rbac-ok", "p-rbac-ok")
    await crear_usuario_activo(
        db, usuario_id=f"u-{rol}", telefono=f"+59390100{_ROLES_CON_ACCESO.index(rol)}", roles=[rol]
    )

    resp = await client.get("/viajes/historial-global/v-rbac-ok", headers=auth_headers(f"u-{rol}", [rol]))

    assert resp.status_code == 200, f"{rol} debería poder abrir el detalle (ve la lista)"
    assert resp.json()["traza"] is not None


@pytest.mark.parametrize("rol", _ROLES_INTERNOS_SIN_ACCESO)
async def test_detalle_historial_global_niega_al_resto_del_personal_interno(client, db, rol):
    await _viaje_con_traza_fijo(db, "v-rbac-no", "p-rbac-no")
    await crear_usuario_activo(
        db, usuario_id=f"u-{rol}", telefono=f"+59390200{_ROLES_INTERNOS_SIN_ACCESO.index(rol)}", roles=[rol]
    )

    resp = await client.get("/viajes/historial-global/v-rbac-no", headers=auth_headers(f"u-{rol}", [rol]))

    assert resp.status_code == 403, f"{rol} no ve la lista, no debería ver el detalle"


async def test_el_detalle_usa_el_mismo_gate_que_la_lista(client, db):
    """Guard estructural: si alguien cambia uno de los dos gates y no el otro,
    esto falla -- es la deriva concreta que se quiere evitar."""
    from src.viajes import router_trips

    def _gates(path: str) -> set:
        ruta = next(r for r in router_trips.router.routes if r.path == path)
        return {d.call for d in ruta.dependant.dependencies if d.call is not None}

    assert router_trips._historial_global_roles in _gates("/viajes/historial-global")
    assert router_trips._historial_global_roles in _gates("/viajes/historial-global/{viaje_id}")
