import math
from typing import Optional, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two GPS points on Earth in meters
    using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def validate_geofence(
    user_lat: float,
    user_lon: float,
    user_accuracy: float,
    target_lat: float,
    target_lon: float,
    max_radius_meters: float,
    max_accuracy_meters: float = 50.0,
) -> Tuple[bool, float, Optional[str]]:
    """
    Validates user GPS against target geofencing center and maximum accuracy tolerance.
    Returns: (is_valid: bool, distance_meters: float, error_message: Optional[str])
    """
    # 1. Validate coordinate bounds
    if not (-90.0 <= user_lat <= 90.0 and -180.0 <= user_lon <= 180.0):
        return False, 0.0, "Invalid GPS latitude or longitude values received."

    if not (-90.0 <= target_lat <= 90.0 and -180.0 <= target_lon <= 180.0):
        return False, 0.0, "Institution geofence center coordinates are unconfigured or invalid."

    # 2. Strict GPS Accuracy Quality Gate (Option A: <= 50m)
    if user_accuracy is not None and user_accuracy > max_accuracy_meters:
        return (
            False,
            0.0,
            f"GPS signal accuracy too weak (±{user_accuracy:.1f}m). Required accuracy is within ±{max_accuracy_meters:.0f}m. Please move outdoors or enable High Accuracy GPS.",
        )

    # 3. Calculate distance from campus center
    distance = haversine_distance(user_lat, user_lon, target_lat, target_lon)

    if distance > max_radius_meters:
        return (
            False,
            round(distance, 1),
            f"You are {distance:.1f}m away from campus. Maximum allowed check-in radius is {max_radius_meters:.1f}m.",
        )

    return True, round(distance, 1), None
