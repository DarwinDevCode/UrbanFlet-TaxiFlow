"""Preferencias de interfaz/notificaciones por cuenta — Sección 1.4/2.3/3.2
de `specs/specs-administrativas/ux_complementaria.md`. Un solo documento
por `usuario_id` en vez de una colección/tabla por cada preferencia suelta
(tema, densidad de tablas, push por categoría, sonido/vibración de nueva
oferta, hora habitual de turno) -- todas comparten el mismo ciclo de vida
(lectura/escritura de la propia cuenta, sin auditoría: son ajustes de
interfaz, no acciones de seguridad ni de negocio).
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

DEFAULTS: dict = {
    "tema": "claro",
    "densidad_tablas": "comoda",
    # Segundo rediseño visual (v2): color de sidebar por cuenta, ver
    # `schemas.py::SidebarTono`.
    "sidebar_tono": "claro",
    "notificaciones_push": {},
    "sonido_oferta": True,
    "vibracion_oferta": True,
    "recordatorio_turno_hora": None,
    # Ronda de personalización: accesibilidad (factor sobre la escala
    # tipográfica, ver shared-ui/tamanoTexto.ts) y accesos rápidos del
    # sidebar. `secciones_favoritas` guarda ids de sección de `web-interno`
    # (`App.tsx::SECCIONES`) -- se valida contra las secciones que el rol
    # realmente ve al renderizar, nunca acá: un id que ya no existe (sección
    # retirada) o que el rol perdió simplemente no se pinta, sin romper.
    "tamano_texto": "normal",
    "secciones_favoritas": [],
}


async def obtener_preferencias(db: AsyncIOMotorDatabase, usuario_id: str) -> dict:
    doc = await db.preferencias_usuario.find_one({"_id": usuario_id})
    if doc is None:
        return dict(DEFAULTS)
    return {campo: doc.get(campo, valor_default) for campo, valor_default in DEFAULTS.items()}


async def actualizar_preferencias(db: AsyncIOMotorDatabase, *, usuario_id: str, cambios: dict) -> dict:
    if cambios:
        await db.preferencias_usuario.update_one({"_id": usuario_id}, {"$set": cambios}, upsert=True)
    return await obtener_preferencias(db, usuario_id)
