import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    To get distnce from 2 coordinates in km C(Haversineformula).
    """
    R = 6371.0  # heart radius in km 
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
    To eximate the explorable radius based on trip duration 
    I decide to use the concept of diminishing retuns
    It's based on 3 solution:
    -Short trip - under 7 days (every day value 200km)
    -Medium trip - between 8 and 15 days (every day value 150km)
    -Long trip - over 15 day (every day value 100KM )
    """
    if trip_duration_days <= 7:
        radius = trip_duration_days * 200
    elif trip_duration_days <= 15:
        radius = 1400 + (trip_duration_days - 7) * 150
    else:
        radius = 2600 + (trip_duration_days - 15) * 100

    return min(radius, 5000)  # cap a 5000 km


def estimate_stops(trip_duration_days: int) -> int:
    """To get intermediate airport stops you will can do."""
    if trip_duration_days <= 7:
        return min(2, trip_duration_days // 3)
    elif trip_duration_days <= 15:
        return min(3, trip_duration_days // 4)
    else:
        return min(4, trip_duration_days // 5)
