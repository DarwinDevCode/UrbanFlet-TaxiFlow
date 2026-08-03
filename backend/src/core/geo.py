"""Cálculos geográficos compartidos. Extraído de flota/service.py (detección
de salto imposible, CU-O19 A4) porque viajes/service.py también lo necesita
(estimación de distancia recta para la tarifa estimada, CU-O04)."""

import math


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radio_tierra_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radio_tierra_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
