from datetime import date, datetime, timedelta

from src.plataforma import service
from tests.utils import auth_headers, crear_usuario_activo


# ---------------------------------------------------------------------------
# RBAC (mínimo exigido: 403 para roles sin acceso, 200 para los que sí)
# ---------------------------------------------------------------------------

async def test_rol_sin_acceso_recibe_403(client, db, monkeypatch):
    monkeypatch.setattr(service, "obtener_catalogo_indicadores", lambda: [])
    await crear_usuario_activo(db, usuario_id="u-pasajero-plat", telefono="+593900200001", roles=["pasajero"])

    resp = await client.get("/plataforma/indicadores", headers=auth_headers("u-pasajero-plat", ["pasajero"]))

    assert resp.status_code == 403


async def test_responsable_plataforma_puede_consultar_indicadores(client, db, monkeypatch):
    hoy = date.today()
    catalogo = [
        {
            "id": "flota_activa_franja",
            "nombre": "% de flota activa por franja",
            "datos_al": hoy,
            "retrasado": False,
            "filas": [{"franja": "06-12", "pct_disponible": 0.5, "total_registros": 10}],
        }
    ]
    monkeypatch.setattr(service, "obtener_catalogo_indicadores", lambda: catalogo)
    await crear_usuario_activo(
        db, usuario_id="u-plataforma-1", telefono="+593900200002", roles=["responsable_plataforma"]
    )

    resp = await client.get(
        "/plataforma/indicadores", headers=auth_headers("u-plataforma-1", ["responsable_plataforma"])
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["informes"]) == 1
    assert body["informes"][0]["id"] == "flota_activa_franja"
    assert body["informes"][0]["retrasado"] is False
    assert body["informes"][0]["filas"][0]["franja"] == "06-12"


async def test_gerencia_tambien_tiene_acceso(client, db, monkeypatch):
    monkeypatch.setattr(service, "obtener_catalogo_indicadores", lambda: [])
    await crear_usuario_activo(db, usuario_id="u-gerencia-1", telefono="+593900200003", roles=["gerencia"])

    resp = await client.get("/plataforma/indicadores", headers=auth_headers("u-gerencia-1", ["gerencia"]))

    assert resp.status_code == 200
    assert resp.json()["informes"] == []


# ---------------------------------------------------------------------------
# Lógica de shaping / frescura (service._snapshot_informe) con un cliente
# ClickHouse falso -- no requiere una instancia real de ClickHouse corriendo.
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, column_names, result_rows):
        self.column_names = column_names
        self.result_rows = result_rows


class _FakeClient:
    """Responde SELECT max(fecha_datos) FROM tabla con `max_fecha`, y
    cualquier otro SELECT (las filas del snapshot) con `filas`."""

    def __init__(self, max_fecha, columnas, filas):
        self._max_fecha = max_fecha
        self._columnas = columnas
        self._filas = filas

    def query(self, sql, parameters=None):
        if sql.strip().startswith("SELECT max("):
            return _FakeResult(["max"], [[self._max_fecha]])
        return _FakeResult(self._columnas, self._filas)


def test_snapshot_informe_hoy_no_esta_retrasado():
    hoy = date.today()
    ahora = datetime.utcnow()
    fake = _FakeClient(
        max_fecha=hoy,
        columnas=["franja", "pct_disponible", "total_registros", "fecha_datos", "actualizado_en"],
        filas=[["06-12", 0.5, 10, hoy, ahora]],
    )

    informe = service._snapshot_informe(
        fake, "flota_activa_franja", "% de flota activa por franja", "rpt_flota_activa_franja"
    )

    assert informe["datos_al"] == hoy
    assert informe["retrasado"] is False
    assert informe["filas"] == [
        {"franja": "06-12", "pct_disponible": 0.5, "total_registros": 10, "actualizado_en": ahora.isoformat()}
    ]


def test_snapshot_informe_de_ayer_queda_marcado_retrasado():
    """A1: si la última corrida buena fue ayer (la de hoy falló), el
    catálogo debe marcar el informe como retrasado -- sin excepciones."""
    ayer = date.today() - timedelta(days=1)
    fake = _FakeClient(
        max_fecha=ayer,
        columnas=["tipo", "pct_vigente", "total_registros", "fecha_datos", "actualizado_en"],
        filas=[["CEDULA", 0.9, 5, ayer, datetime.utcnow()]],
    )

    informe = service._snapshot_informe(
        fake, "documentacion_vigente", "Documentación vigente por tipo", "rpt_documentacion_vigente"
    )

    assert informe["datos_al"] == ayer
    assert informe["retrasado"] is True


def test_snapshot_informe_sin_datos_todavia():
    """Dominio que nunca corrió (o tabla recién creada, vacía): informe
    vacío y retrasado, nunca un error."""
    fake = _FakeClient(max_fecha=None, columnas=[], filas=[])

    informe = service._snapshot_informe(
        fake, "uso_integraciones", "Uso de integraciones por endpoint", "rpt_uso_integraciones"
    )

    assert informe["datos_al"] is None
    assert informe["retrasado"] is True
    assert informe["filas"] == []
