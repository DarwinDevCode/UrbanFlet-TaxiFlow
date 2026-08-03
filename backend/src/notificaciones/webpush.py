"""Web Push VAPID — para eventos que llegan con la pestaña cerrada
(arquitectura_software.md línea 91-99): "los eventos que llegan con la
pestaña cerrada se entregan por Web Push y se recuperan por REST al reabrir
(GET /viajes/activo)"."""

import json
import logging

from pywebpush import WebPushException, webpush

from src.core.config import get_settings

logger = logging.getLogger("urbanflet.webpush")


async def send_web_push(subscription_info: dict, payload: dict) -> bool:
    settings = get_settings()
    if not settings.vapid_private_key:
        logger.info("VAPID no configurado; se omite Web Push (payload=%s)", payload)
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException:
        logger.warning("Fallo al enviar Web Push", exc_info=True)
        return False
