import asyncio

from src.sistema import service as sistema_service
from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-mon-1", telefono="+593900000700", roles=["admin_sistema"])
    return auth_headers("admin-mon-1", ["admin_sistema"])


def _mockear_pings_externos(monkeypatch, *, clickhouse_ok=True, airflow_ok=True):
    # `mongo`/`redis` ya son reales-en-memoria (mongomock/fakeredis, ver
    # conftest.py) -- rápidos y deterministas sin mockear nada. ClickHouse y
    # Airflow sí requieren mock: no hay garantía de que estén accesibles
    # (ni rápidos) desde el proceso de pytest.
    async def _ok() -> None:
        return None

    async def _falla() -> None:
        raise ConnectionError("simulado")

    monkeypatch.setattr(sistema_service, "_ping_clickhouse", _ok if clickhouse_ok else _falla)
    monkeypatch.setattr(sistema_service, "_ping_airflow", _ok if airflow_ok else _falla)


async def test_solo_admin_sistema_ve_el_panel_de_salud(client, db):
    await crear_usuario_activo(db, usuario_id="fin-mon-1", telefono="+593900000701", roles=["admin_financiero"])
    headers = auth_headers("fin-mon-1", ["admin_financiero"])

    resp = await client.get("/sistema/salud", headers=headers)
    assert resp.status_code == 403


async def test_salud_reporta_los_5_componentes_con_disponibilidad_real(client, db, monkeypatch):
    _mockear_pings_externos(monkeypatch, clickhouse_ok=True, airflow_ok=False)
    headers = await _admin(db)

    resp = await client.get("/sistema/salud", headers=headers)

    assert resp.status_code == 200
    por_componente = {c["componente"]: c for c in resp.json()}
    assert set(por_componente) == {"backend", "mongo", "redis", "clickhouse", "airflow"}
    # backend/mongo/redis/clickhouse: reales-en-memoria u mockeadas a "ok" --
    # deben quedar disponibles con latencia medida (nunca simulada a mano).
    for componente in ("backend", "mongo", "redis", "clickhouse"):
        assert por_componente[componente]["disponible"] is True
        assert por_componente[componente]["estado"] == "bien"
    # airflow mockeado a fallar -- debe degradar a "no disponible" / "crítico",
    # nunca propagar el texto crudo de la excepción simulada.
    assert por_componente["airflow"]["disponible"] is False
    assert por_componente["airflow"]["latencia_ms"] is None
    assert por_componente["airflow"]["estado"] == "critico"


async def test_umbrales_por_defecto_y_actualizacion_con_efecto_en_el_panel(client, db, monkeypatch):
    _mockear_pings_externos(monkeypatch)
    headers = await _admin(db)

    listado = await client.get("/sistema/umbrales-monitoreo", headers=headers)
    assert listado.status_code == 200
    mongo_default = next(u for u in listado.json() if u["componente"] == "mongo")
    assert mongo_default == {"componente": "mongo", "latencia_advertencia_ms": 200, "latencia_critica_ms": 1000}

    actualizado = await client.put(
        "/sistema/umbrales-monitoreo/mongo",
        headers=headers,
        json={"latencia_advertencia_ms": 5, "latencia_critica_ms": 60000},
    )
    assert actualizado.status_code == 200
    assert actualizado.json() == {"componente": "mongo", "latencia_advertencia_ms": 5, "latencia_critica_ms": 60000}

    evento = await db.bitacora.find_one({"accion": "MONITOREO_UMBRAL_CAMBIO", "entidad_id": "mongo"})
    assert evento is not None
    assert evento["datos_previos"] == {"latencia_advertencia_ms": 200, "latencia_critica_ms": 1000}
    assert evento["datos_posteriores"] == {"latencia_advertencia_ms": 5, "latencia_critica_ms": 60000}

    # mongomock responde en <<1ms real -- para probar el efecto del umbral
    # nuevo (5ms) sin perseguir timing frágil, se agrega una demora real y
    # controlada al ping de mongo (por encima del umbral, por debajo de
    # crítico) en vez de asumir cuánto tarda el mock por sí solo.
    ping_original = sistema_service._ping_mongo

    async def _ping_mongo_lento(db_):
        await ping_original(db_)
        await asyncio.sleep(0.01)

    monkeypatch.setattr(sistema_service, "_ping_mongo", _ping_mongo_lento)

    salud = await client.get("/sistema/salud", headers=headers)
    mongo_salud = next(c for c in salud.json() if c["componente"] == "mongo")
    assert mongo_salud["disponible"] is True
    assert mongo_salud["latencia_ms"] >= 5
    assert mongo_salud["estado"] == "advertencia"


async def test_componente_invalido_devuelve_422(client, db):
    headers = await _admin(db)
    resp = await client.put(
        "/sistema/umbrales-monitoreo/no-existe",
        headers=headers,
        json={"latencia_advertencia_ms": 100, "latencia_critica_ms": 500},
    )
    assert resp.status_code == 422


async def test_indicadores_degradan_a_no_disponible_cuando_el_driver_no_soporta_el_comando(client, db):
    # mongomock/fakeredis (ver conftest.py) no implementan serverStatus/dbStats
    # ni INFO -- exactamente el mismo criterio de degradación que _medir():
    # nunca debe reventar el endpoint, solo reportar disponible=False.
    headers = await _admin(db)

    resp = await client.get("/sistema/indicadores", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"mongo", "redis", "clickhouse"}
    assert body["mongo"]["disponible"] is False
    assert body["redis"]["disponible"] is False


async def test_solo_admin_sistema_ve_los_indicadores(client, db):
    await crear_usuario_activo(db, usuario_id="fin-mon-2", telefono="+593900000702", roles=["admin_financiero"])
    headers = auth_headers("fin-mon-2", ["admin_financiero"])

    resp = await client.get("/sistema/indicadores", headers=headers)
    assert resp.status_code == 403


async def test_historial_latencia_se_registra_en_cada_consulta_de_salud(client, db, monkeypatch):
    _mockear_pings_externos(monkeypatch)
    headers = await _admin(db)

    await client.get("/sistema/salud", headers=headers)
    await client.get("/sistema/salud", headers=headers)

    resp = await client.get("/sistema/historial-latencia", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    por_componente = {p["componente"] for p in body}
    assert {"backend", "mongo", "redis", "clickhouse", "airflow"}.issubset(por_componente)
    assert len(body) == 10  # 5 componentes x 2 consultas


async def test_historial_latencia_filtra_por_ventana_de_horas(client, db, monkeypatch):
    _mockear_pings_externos(monkeypatch)
    headers = await _admin(db)
    await client.get("/sistema/salud", headers=headers)

    fuera_de_rango = await client.get("/sistema/historial-latencia?horas=200", headers=headers)
    assert fuera_de_rango.status_code == 422

    dentro_de_rango = await client.get("/sistema/historial-latencia?horas=1", headers=headers)
    assert dentro_de_rango.status_code == 200
    assert len(dentro_de_rango.json()) == 5
