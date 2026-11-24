from tests.utils import auth_headers, crear_usuario_activo


async def _headers(db, usuario_id="pref-1", telefono="+593900001000"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def test_preferencias_por_defecto_sin_documento_previo(client, db):
    headers = await _headers(db)

    resp = await client.get("/preferencias", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "tema": "claro",
        "densidad_tablas": "comoda",
        "notificaciones_push": {},
        "sonido_oferta": True,
        "vibracion_oferta": True,
        "recordatorio_turno_hora": None,
        # Ronda de personalización: accesibilidad + accesos rápidos del
        # sidebar. Los defaults dejan el sistema exactamente como antes
        # (escala tipográfica sin cambio, sin favoritos).
        "tamano_texto": "normal",
        "secciones_favoritas": [],
        # Segundo rediseño visual (v2): color de sidebar por cuenta,
        # "claro" por defecto (PLAN_REDISENO_V2.md §3).
        "sidebar_tono": "claro",
    }


async def test_editar_preferencias_aplica_solo_los_campos_enviados(client, db):
    headers = await _headers(db)

    primero = await client.patch("/preferencias", headers=headers, json={"tema": "oscuro"})
    assert primero.status_code == 200
    assert primero.json()["tema"] == "oscuro"
    assert primero.json()["densidad_tablas"] == "comoda"

    segundo = await client.patch("/preferencias", headers=headers, json={"densidad_tablas": "compacta"})
    assert segundo.status_code == 200
    assert segundo.json()["tema"] == "oscuro"
    assert segundo.json()["densidad_tablas"] == "compacta"


async def test_editar_notificaciones_push_por_categoria(client, db):
    headers = await _headers(db)

    resp = await client.patch(
        "/preferencias",
        headers=headers,
        json={"notificaciones_push": {"oferta_aceptada": False, "conductor_en_camino": True}},
    )

    assert resp.status_code == 200
    assert resp.json()["notificaciones_push"] == {"oferta_aceptada": False, "conductor_en_camino": True}


async def test_recordatorio_turno_hora_valida_formato(client, db):
    headers = await _headers(db)

    invalido = await client.patch("/preferencias", headers=headers, json={"recordatorio_turno_hora": "25:99"})
    assert invalido.status_code == 422

    valido = await client.patch("/preferencias", headers=headers, json={"recordatorio_turno_hora": "07:30"})
    assert valido.status_code == 200
    assert valido.json()["recordatorio_turno_hora"] == "07:30"

    limpiado = await client.patch("/preferencias", headers=headers, json={"recordatorio_turno_hora": None})
    assert limpiado.status_code == 200
    assert limpiado.json()["recordatorio_turno_hora"] is None


async def test_preferencias_son_por_cuenta_no_compartidas(client, db):
    headers_a = await _headers(db, usuario_id="pref-a", telefono="+593900001001")
    headers_b = await _headers(db, usuario_id="pref-b", telefono="+593900001002")

    await client.patch("/preferencias", headers=headers_a, json={"tema": "oscuro"})

    resp_b = await client.get("/preferencias", headers=headers_b)
    assert resp_b.json()["tema"] == "claro"


async def test_preferencias_requiere_autenticacion(client):
    resp = await client.get("/preferencias")
    assert resp.status_code == 401


async def test_guardar_tamano_texto_y_secciones_favoritas(client, db):
    """Ronda de personalización: los 2 campos nuevos se guardan y se releen."""
    headers = await _headers(db, usuario_id="pref-pers", telefono="+593900001010")

    resp = await client.patch(
        "/preferencias",
        headers=headers,
        json={"tamano_texto": "grande", "secciones_favoritas": ["flota", "finanzas"]},
    )

    assert resp.status_code == 200
    assert resp.json()["tamano_texto"] == "grande"
    assert resp.json()["secciones_favoritas"] == ["flota", "finanzas"]

    relectura = await client.get("/preferencias", headers=headers)
    assert relectura.json()["tamano_texto"] == "grande"
    assert relectura.json()["secciones_favoritas"] == ["flota", "finanzas"]


async def test_tamano_texto_rechaza_valor_fuera_del_catalogo(client, db):
    headers = await _headers(db, usuario_id="pref-mal", telefono="+593900001011")

    resp = await client.patch("/preferencias", headers=headers, json={"tamano_texto": "gigante"})

    assert resp.status_code == 422


async def test_guardar_sidebar_tono_y_rechazar_valor_fuera_del_catalogo(client, db):
    """Segundo rediseño visual (v2): 4 opciones predefinidas, nunca un color
    libre -- guardar una de las 4 se relee igual, y un valor fuera del
    catálogo se rechaza con 422 (mismo criterio que `tamano_texto`)."""
    headers = await _headers(db, usuario_id="pref-sidebar", telefono="+593900001030")

    resp = await client.patch("/preferencias", headers=headers, json={"sidebar_tono": "ambar"})
    assert resp.status_code == 200
    assert resp.json()["sidebar_tono"] == "ambar"

    relectura = await client.get("/preferencias", headers=headers)
    assert relectura.json()["sidebar_tono"] == "ambar"

    invalido = await client.patch("/preferencias", headers=headers, json={"sidebar_tono": "azul"})
    assert invalido.status_code == 422


async def test_preferencias_son_por_cuenta_no_globales(client, db):
    """La preferencia de una cuenta no debe filtrarse a otra."""
    headers_a = await _headers(db, usuario_id="pref-a", telefono="+593900001020")
    headers_b = await _headers(db, usuario_id="pref-b", telefono="+593900001021")

    await client.patch("/preferencias", headers=headers_a, json={"tamano_texto": "muy_grande"})

    de_b = await client.get("/preferencias", headers=headers_b)
    assert de_b.json()["tamano_texto"] == "normal"
