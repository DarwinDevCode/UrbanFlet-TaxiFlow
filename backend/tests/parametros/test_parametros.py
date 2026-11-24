from datetime import datetime, UTC

from tests.utils import auth_headers, crear_usuario_activo

_ADMIN_ID = "u-admin-parametros"


async def _admin_headers(db):
    await crear_usuario_activo(db, usuario_id=_ADMIN_ID, telefono="+593988888888", roles=["admin_plataforma"])
    return auth_headers(_ADMIN_ID, ["admin_plataforma"])


async def test_nueva_version_de_tarifa_cierra_la_anterior(client, db):
    headers = await _admin_headers(db)
    v1_desde = datetime(2026, 1, 1, tzinfo=UTC)
    v2_desde = datetime(2026, 2, 1, tzinfo=UTC)

    r1 = await client.post(
        "/parametros/tarifas",
        headers=headers,
        json={
            "franja": "DIURNA",
            "arrancada": 0.5,
            "costo_km": 0.35,
            "costo_min_espera": 0.07,
            "carrera_minima": 1.5,
            "vigente_desde": v1_desde.isoformat(),
        },
    )
    assert r1.status_code == 201
    v1_id = r1.json()["id"]

    r2 = await client.post(
        "/parametros/tarifas",
        headers=headers,
        json={
            "franja": "DIURNA",
            "arrancada": 0.6,
            "costo_km": 0.4,
            "costo_min_espera": 0.08,
            "carrera_minima": 1.6,
            "vigente_desde": v2_desde.isoformat(),
        },
    )
    assert r2.status_code == 201

    v1 = await db.parametros.find_one({"_id": v1_id})
    assert v1["vigente_hasta"] is not None
    assert datetime.fromisoformat(str(v1["vigente_hasta"])).replace(tzinfo=UTC) == v2_desde or v1[
        "vigente_hasta"
    ] == v2_desde


async def test_obtener_vigente_devuelve_la_version_correcta_por_fecha(client, db):
    headers = await _admin_headers(db)
    await client.post(
        "/parametros/tarifas",
        headers=headers,
        json={
            "franja": "NOCTURNA",
            "arrancada": 0.6,
            "costo_km": 0.4,
            "costo_min_espera": 0.09,
            "carrera_minima": 1.75,
            "vigente_desde": "2026-01-01T00:00:00Z",
        },
    )
    await client.post(
        "/parametros/tarifas",
        headers=headers,
        json={
            "franja": "NOCTURNA",
            "arrancada": 0.7,
            "costo_km": 0.45,
            "costo_min_espera": 0.1,
            "carrera_minima": 1.9,
            "vigente_desde": "2026-03-01T00:00:00Z",
        },
    )

    resp = await client.get(
        "/parametros/vigente", params={"tipo": "tarifa", "franja": "NOCTURNA", "fecha": "2026-02-01T00:00:00Z"}
    )

    assert resp.status_code == 200
    assert resp.json()["valores"]["arrancada"] == 0.6


async def test_historial_de_comision_lista_todas_las_versiones_mas_reciente_primero(client, db):
    headers = await _admin_headers(db)
    await client.post(
        "/parametros/comisiones",
        headers=headers,
        json={"porcentaje": 0.2, "vigente_desde": "2026-01-01T00:00:00Z"},
    )
    await client.post(
        "/parametros/comisiones",
        headers=headers,
        json={"porcentaje": 0.25, "vigente_desde": "2026-03-01T00:00:00Z"},
    )

    resp = await client.get("/parametros/historial", params={"tipo": "comision"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # Más reciente primero.
    assert body[0]["valores"]["porcentaje"] == 0.25
    assert body[0]["vigente_hasta"] is None
    assert body[1]["valores"]["porcentaje"] == 0.2
    assert body[1]["vigente_hasta"] is not None


async def test_historial_de_comision_rechaza_rol_sin_permiso(client, db):
    await crear_usuario_activo(db, usuario_id="u-fin-parametros", telefono="+593977777777", roles=["admin_financiero"])
    headers = auth_headers("u-fin-parametros", ["admin_financiero"])

    resp = await client.get("/parametros/historial", params={"tipo": "comision"}, headers=headers)

    assert resp.status_code == 403
