"""Prototype access rules for SafeRide-LK camera monitoring."""

USERS = {
    "admin01": {"name": "Administrator", "role": "administrator", "vehicle": "ALL"},
    "driver01": {"name": "Driver", "role": "driver", "vehicle": "BUS-01"},
    "parent01": {"name": "Parent", "role": "parent", "vehicle": "BUS-01"},
}


def can_view_camera(user: dict[str, str], requested_vehicle: str, trip_active: bool) -> bool:
    """Allow only the assigned driver or parent during an active trip."""
    if not trip_active:
        return False
    if user["role"] == "administrator":
        return True
    return user["role"] in {"driver", "parent"} and user["vehicle"] == requested_vehicle
