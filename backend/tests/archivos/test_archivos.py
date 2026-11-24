"""Fase A de la Ronda 2 (flujo de fallas): primer mecanismo de carga de
archivos del proyecto. Cubre validación de tipo/tamaño y el control de
acceso por contexto (propietario siempre puede, roles adicionales según
CONTEXTOS_PERMITIDOS)."""

from src.archivos import service as archivos_service
from tests.utils import auth_headers, crear_usuario_activo


async def _conductor(db, usuario_id="cond-arch-1", telefono="+593900700001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["conductor"])
    return auth_headers(usuario_id, ["conductor"])


async def test_subir_imagen_real_y_descargarla(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers = await _conductor(db)

    resp = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.jpg", b"\xff\xd8\xff\xe0contenido-de-prueba", "image/jpeg")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["nombre_original"] == "foto.jpg"
    assert body["content_type"] == "image/jpeg"
    assert body["tamano_bytes"] == len(b"\xff\xd8\xff\xe0contenido-de-prueba")
    assert body["propietario_id"] == "cond-arch-1"

    descarga = await client.get(f"/archivos/{body['id']}", headers=headers)
    assert descarga.status_code == 200
    assert descarga.content == b"\xff\xd8\xff\xe0contenido-de-prueba"
    assert descarga.headers["content-type"] == "image/jpeg"


async def test_tipo_de_archivo_no_permitido_devuelve_422(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers = await _conductor(db)

    resp = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("script.exe", b"MZ-binario", "application/x-msdownload")},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "TIPO_ARCHIVO_NO_PERMITIDO"


async def test_archivo_demasiado_grande_devuelve_413(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    monkeypatch.setattr(archivos_service, "TAMANO_MAXIMO_BYTES", 10)
    headers = await _conductor(db)

    resp = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.png", b"0123456789ABCDEF", "image/png")},
    )

    assert resp.status_code == 413
    assert resp.json()["code"] == "ARCHIVO_DEMASIADO_GRANDE"
    # No debe quedar un archivo parcial huérfano en disco.
    assert list(tmp_path.iterdir()) == []


async def test_contexto_no_reconocido_devuelve_422(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers = await _conductor(db)

    resp = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "algo_inventado"},
        files={"file": ("foto.png", b"contenido", "image/png")},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "CONTEXTO_INVALIDO"


async def test_solo_el_propietario_o_un_rol_permitido_puede_descargar(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers_conductor = await _conductor(db)
    await crear_usuario_activo(db, usuario_id="otro-cond-1", telefono="+593900700002", roles=["conductor"])
    headers_otro_conductor = auth_headers("otro-cond-1", ["conductor"])
    await crear_usuario_activo(db, usuario_id="jefe-mant-1", telefono="+593900700003", roles=["jefe_mantenimiento"])
    headers_jefe = auth_headers("jefe-mant-1", ["jefe_mantenimiento"])

    subida = await client.post(
        "/archivos",
        headers=headers_conductor,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.jpg", b"contenido-real", "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    # El propio conductor que subió la evidencia sí puede verla.
    propio = await client.get(f"/archivos/{archivo_id}", headers=headers_conductor)
    assert propio.status_code == 200

    # jefe_mantenimiento está en CONTEXTOS_PERMITIDOS["reporte_falla"].
    jefe = await client.get(f"/archivos/{archivo_id}", headers=headers_jefe)
    assert jefe.status_code == 200

    # Otro conductor, sin relación con el archivo, no debe poder verlo.
    ajeno = await client.get(f"/archivos/{archivo_id}", headers=headers_otro_conductor)
    assert ajeno.status_code == 403
    assert ajeno.json()["code"] == "ACCESO_DENEGADO_ARCHIVO"


async def test_archivo_inexistente_devuelve_404(client, db):
    headers = await _conductor(db)
    resp = await client.get("/archivos/no-existe", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ARCHIVO_NO_ENCONTRADO"


async def test_foto_perfil_se_puede_descargar_sin_sesion(client, db, monkeypatch, tmp_path):
    """Ronda de foto de perfil: `foto_perfil` es el único contexto de lectura
    pública (ver CONTEXTOS_LECTURA_PUBLICA) -- lo necesita la vista pública
    de "Compartir viaje", que no tiene ninguna sesión."""
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers = await _conductor(db)

    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "foto_perfil"},
        files={"file": ("foto.jpg", b"contenido-de-foto-real", "image/jpeg")},
    )
    assert subida.status_code == 201
    archivo_id = subida.json()["id"]

    descarga_anonima = await client.get(f"/archivos/{archivo_id}")
    assert descarga_anonima.status_code == 200
    assert descarga_anonima.content == b"contenido-de-foto-real"


async def test_reporte_falla_sigue_sin_ser_publico(client, db, monkeypatch, tmp_path):
    """`reporte_falla` (evidencia sensible) no se contagia del contexto
    público -- un visitante anónimo sigue sin poder verlo."""
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers = await _conductor(db)

    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.jpg", b"evidencia-real", "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    descarga_anonima = await client.get(f"/archivos/{archivo_id}")
    assert descarga_anonima.status_code == 403
    assert descarga_anonima.json()["code"] == "ACCESO_DENEGADO_ARCHIVO"
