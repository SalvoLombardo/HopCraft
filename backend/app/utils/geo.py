"""
Utility geografiche — formula Haversine e calcoli raggio/tappe.

Usate da:
  - Endpoint /airports/in-radius (1.9)
  - Area calculator per Smart Multi-City (2.1)
"""
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcola la distanza in km tra due coordinate geografiche (formula Haversine).
    """
    R = 6371.0  # raggio terrestre in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def estimate_radius_km(trip_duration_days: int) -> int:
    """
    Stima il raggio esplorabile in km dalla durata del viaggio.
    Logica: più giorni = raggio più ampio, ma con rendimenti decrescenti.
    Usata nello Step 1 della pipeline Smart Multi-City.
    """
    if trip_duration_days <= 7:
        radius = trip_duration_days * 200
    elif trip_duration_days <= 15:
        radius = 1400 + (trip_duration_days - 7) * 150
    else:
        radius = 2600 + (trip_duration_days - 15) * 100

    return min(radius, 5000)  # cap a 5000 km


def estimate_stops(trip_duration_days: int) -> int:
    """Numero di tappe intermedie suggerite in base alla durata del viaggio."""
    if trip_duration_days <= 7:
        return min(2, trip_duration_days // 3)
    elif trip_duration_days <= 15:
        return min(3, trip_duration_days // 4)
    else:
        return min(4, trip_duration_days // 5)
