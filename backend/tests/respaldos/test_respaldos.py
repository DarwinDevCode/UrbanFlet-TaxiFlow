from src.core.db_mongo import get_mongo_client
from src.respaldos import service as respaldos_service
from tests.utils import auth_headers, crear_usuario_activo


class _ResultadoFalso:
    def __init__(self, column_names, result_rows):
        self.column_names = column_names
        self.result_rows = result_rows


class _ClickHouseFalso:
    """Reemplaza `clickhouse_connect` real -- sin esto, los tests tocarían el
    ClickHouse real del stack (alcanzable en localhost:8123 fuera de
    docker), igual que ya se evitó en `tests/sistema/test_monitoreo.py`."""

    def __init__(self):
        self.tablas: dict[str, dict] = {}
        self.comandos: list[str] = []
        self.inserts: list[tuple] = []

    def query(self, sql, parameters=None):
        if "system.tables" in sql:
            nombres = [n for n in self.tablas if n.startswith("rpt_")]
            return _ResultadoFalso(["name"], [[n] for n in nombres])
        tabla = sql.strip().split()[-1]
        if tabla not in self.tablas:
            raise ValueError(f"tabla inexistente: {tabla}")
        t = self.tablas[tabla]
        return _ResultadoFalso(t["columnas"], t["filas"])

    def command(self, cmd, use_database=True):
        self.comandos.append(cmd)
        return "ok"

    def insert(self, table, data, column_names=None, database=None):
        self.inserts.append((database, table, column_names, data))


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-resp-1", telefono="+593900000900", roles=["admin_sistema"])
    return auth_headers("admin-resp-1", ["admin_sistema"])


def _mockear_todo(monkeypatch, tmp_path):
    fake = _ClickHouseFalso()
    monkeypatch.setattr(respaldos_service, "_ruta_respaldos", lambda: tmp_path)
    monkeypatch.setattr(respaldos_service, "get_clickhouse_client", lambda: fake)
    return fake


async def test_disparar_respaldo_requiere_admin_sistema(client, db):
    await crear_usuario_activo(db, usuario_id="fin-resp-1", telefono="+593900000901", roles=["admin_financiero"])
    headers = auth_headers("fin-resp-1", ["admin_financiero"])

    resp = await client.post("/respaldos", headers=headers)
    assert resp.status_code == 403


async def test_disparar_respaldo_crea_dos_registros_en_progreso(client, db, monkeypatch, tmp_path):
    _mockear_todo(monkeypatch, tmp_path)
    headers = await _admin(db)

    resp = await client.post("/respaldos", headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert {r["motor"] for r in body} == {"mongo", "clickhouse"}
    assert all(r["estado"] == "en_progreso" for r in body)

    evento = await db.bitacora.find_one({"accion": "RESPALDO_DISPARO"})
    assert evento is not None


async def test_ejecutar_respaldo_mongo_produce_archivo_real_con_hash_valido(db, monkeypatch, tmp_path):
    monkeypatch.setattr(respaldos_service, "_ruta_respaldos", lambda: tmp_path)
    await crear_usuario_activo(db, usuario_id="admin-mongo-1", telefono="+593900000902", roles=["admin_sistema"])

    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-mongo-1", actor_rol="admin_sistema")
    doc_mongo = next(d for d in docs if d["motor"] == "mongo")

    await respaldos_service.ejecutar_respaldo_mongo(doc_mongo["_id"])

    actualizado = await db.respaldos.find_one({"_id": doc_mongo["_id"]})
    assert actualizado["estado"] == "completado"
    assert actualizado["tamano_bytes"] > 0
    assert actualizado["hash_sha256"]
    assert "usuarios" in actualizado["colecciones"]
    # Las colecciones propias del módulo nunca se incluyen en su propio respaldo.
    assert "respaldos" not in actualizado["colecciones"]
    assert "plan_dr" not in actualizado["colecciones"]

    import hashlib

    with open(actualizado["ruta_archivo"], "rb") as f:
        recalculado = hashlib.sha256(f.read()).hexdigest()
    assert recalculado == actualizado["hash_sha256"]


async def test_verificar_respaldo_detecta_archivo_corrompido(db, monkeypatch, tmp_path):
    monkeypatch.setattr(respaldos_service, "_ruta_respaldos", lambda: tmp_path)
    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-ver-1", actor_rol="admin_sistema")
    doc_mongo = next(d for d in docs if d["motor"] == "mongo")
    await respaldos_service.ejecutar_respaldo_mongo(doc_mongo["_id"])

    integro = await respaldos_service.verificar_respaldo(db, doc_mongo["_id"])
    assert integro["integro"] is True

    actualizado = await db.respaldos.find_one({"_id": doc_mongo["_id"]})
    with open(actualizado["ruta_archivo"], "ab") as f:
        f.write(b"dato corrupto agregado despues del respaldo\n")

    corrupto = await respaldos_service.verificar_respaldo(db, doc_mongo["_id"])
    assert corrupto["integro"] is False


async def test_restaurar_respaldo_mongo_solo_toca_la_base_de_prueba_aislada(db, monkeypatch, tmp_path):
    monkeypatch.setattr(respaldos_service, "_ruta_respaldos", lambda: tmp_path)
    assert respaldos_service.MONGO_RESTORE_DB != "urbanflet"

    await crear_usuario_activo(db, usuario_id="usuario-real-1", telefono="+593900000903", roles=["jefe_mantenimiento"])
    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-rest-1", actor_rol="admin_sistema")
    doc_mongo = next(d for d in docs if d["motor"] == "mongo")
    await respaldos_service.ejecutar_respaldo_mongo(doc_mongo["_id"])
    respaldo = await db.respaldos.find_one({"_id": doc_mongo["_id"]})

    restauracion = await respaldos_service.restaurar_respaldo(
        db, actor_id="admin-rest-1", actor_rol="admin_sistema", respaldo_id=doc_mongo["_id"]
    )
    assert restauracion["base_destino"] == respaldos_service.MONGO_RESTORE_DB
    await respaldos_service.ejecutar_restauracion_mongo(restauracion["_id"], respaldo["ruta_archivo"])

    actualizada = await db.restauraciones.find_one({"_id": restauracion["_id"]})
    assert actualizada["estado"] == "completado"
    assert actualizada["conteos"]["usuarios"] >= 1

    destino = get_mongo_client()[respaldos_service.MONGO_RESTORE_DB]
    restaurado = await destino.usuarios.find_one({"_id": "usuario-real-1"})
    assert restaurado is not None
    assert restaurado["telefono"] == "+593900000903"

    evento = await db.bitacora.find_one({"accion": "RESPALDO_RESTAURACION_PRUEBA"})
    assert evento is not None
    assert evento["datos_posteriores"]["base_destino"] == respaldos_service.MONGO_RESTORE_DB


async def test_restaurar_exige_respaldo_completado(db, monkeypatch, tmp_path):
    monkeypatch.setattr(respaldos_service, "_ruta_respaldos", lambda: tmp_path)
    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-rest-2", actor_rol="admin_sistema")
    doc_mongo = next(d for d in docs if d["motor"] == "mongo")

    try:
        await respaldos_service.restaurar_respaldo(
            db, actor_id="admin-rest-2", actor_rol="admin_sistema", respaldo_id=doc_mongo["_id"]
        )
        raise AssertionError("debía rechazar restaurar un respaldo en_progreso")
    except respaldos_service.RespaldoNoDisponibleError:
        pass


async def test_respaldo_clickhouse_solo_incluye_tablas_rpt_y_referencia(db, monkeypatch, tmp_path):
    fake = _mockear_todo(monkeypatch, tmp_path)
    fake.tablas["rpt_margen_comision"] = {"columnas": ["periodo", "margen"], "filas": [["2026-07", 0.2]]}
    fake.tablas["dim_tiempo"] = {"columnas": ["fecha"], "filas": [["2026-07-01"]]}
    fake.tablas["bronze_viajes"] = {"columnas": ["id"], "filas": [["v1"]]}  # NO debe respaldarse

    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-ch-1", actor_rol="admin_sistema")
    doc_ch = next(d for d in docs if d["motor"] == "clickhouse")
    await respaldos_service.ejecutar_respaldo_clickhouse(doc_ch["_id"])

    actualizado = await db.respaldos.find_one({"_id": doc_ch["_id"]})
    assert actualizado["estado"] == "completado"
    assert "rpt_margen_comision" in actualizado["colecciones"]
    assert "dim_tiempo" in actualizado["colecciones"]
    assert "bronze_viajes" not in actualizado["colecciones"]


async def test_restaurar_respaldo_clickhouse_crea_en_base_de_prueba(db, monkeypatch, tmp_path):
    fake = _mockear_todo(monkeypatch, tmp_path)
    fake.tablas["rpt_margen_comision"] = {"columnas": ["periodo", "margen"], "filas": [["2026-07", 0.2]]}

    docs = await respaldos_service.disparar_respaldo(db, actor_id="admin-ch-2", actor_rol="admin_sistema")
    doc_ch = next(d for d in docs if d["motor"] == "clickhouse")
    await respaldos_service.ejecutar_respaldo_clickhouse(doc_ch["_id"])
    respaldo = await db.respaldos.find_one({"_id": doc_ch["_id"]})

    restauracion = await respaldos_service.restaurar_respaldo(
        db, actor_id="admin-ch-2", actor_rol="admin_sistema", respaldo_id=doc_ch["_id"]
    )
    assert restauracion["base_destino"] == respaldos_service.CLICKHOUSE_RESTORE_DB
    await respaldos_service.ejecutar_restauracion_clickhouse(restauracion["_id"], respaldo["ruta_archivo"])

    actualizada = await db.restauraciones.find_one({"_id": restauracion["_id"]})
    assert actualizada["estado"] == "completado"
    assert actualizada["conteos"]["rpt_margen_comision"] == 1
    assert any(respaldos_service.CLICKHOUSE_RESTORE_DB in c for c in fake.comandos)
    assert any(db_ == respaldos_service.CLICKHOUSE_RESTORE_DB for db_, *_ in fake.inserts)


# --- Módulo 7.2: plan de continuidad -----------------------------------


async def test_plan_dr_requiere_admin_sistema_o_gerencia(client, db):
    await crear_usuario_activo(db, usuario_id="cumpl-dr-1", telefono="+593900000904", roles=["supervisor_cumplimiento"])
    headers = auth_headers("cumpl-dr-1", ["supervisor_cumplimiento"])

    resp = await client.get("/respaldos/plan-dr", headers=headers)
    assert resp.status_code == 403


async def test_gerencia_puede_ver_y_editar_plan_dr(client, db):
    await crear_usuario_activo(db, usuario_id="gerencia-dr-1", telefono="+593900000905", roles=["gerencia"])
    headers = auth_headers("gerencia-dr-1", ["gerencia"])

    listado = await client.get("/respaldos/plan-dr", headers=headers)
    assert listado.status_code == 200
    assert len(listado.json()) == 7
    assert all(item["rto"] == "" for item in listado.json())

    actualizado = await client.put(
        "/respaldos/plan-dr/operaciones_despacho",
        headers=headers,
        json={"rto": "15 minutos", "rpo": "0 (sin pérdida de viajes en curso)", "notas": "Prioridad máxima"},
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["rto"] == "15 minutos"

    evento = await db.bitacora.find_one({"accion": "PLAN_DR_CAMBIO", "entidad_id": "operaciones_despacho"})
    assert evento is not None
    assert evento["datos_posteriores"]["rto"] == "15 minutos"


async def test_registrar_y_listar_simulacro(client, db):
    await crear_usuario_activo(db, usuario_id="admin-sim-1", telefono="+593900000906", roles=["admin_sistema"])
    headers = auth_headers("admin-sim-1", ["admin_sistema"])

    creado = await client.post(
        "/respaldos/simulacros",
        headers=headers,
        json={
            "fecha": "2026-08-01T10:00:00Z",
            "resultado": "exitoso",
            "notas": "Restauración de prueba real ejecutada",
        },
    )
    assert creado.status_code == 201

    listado = await client.get("/respaldos/simulacros", headers=headers)
    assert listado.status_code == 200
    assert any(s["resultado"] == "exitoso" for s in listado.json())

    evento = await db.bitacora.find_one({"accion": "SIMULACRO_DR_REGISTRO"})
    assert evento is not None
