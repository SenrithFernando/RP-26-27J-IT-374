LOCATIONS = [
    {"id": "DEPOT", "name": "Vehicle starting point"},
    {"id": "HOME_01", "name": "Student A home"},
    {"id": "HOME_02", "name": "Student B home"},
    {"id": "HOME_03", "name": "Student C home"},
    {"id": "SCHOOL_01", "name": "Test school"},
]

STUDENTS = [
    {
        "id": "STU_01",
        "name": "Student A",
        "home_id": "HOME_01",
        "school_id": "SCHOOL_01",
        "vehicle_id": "VAN_01",
    },
    {
        "id": "STU_02",
        "name": "Student B",
        "home_id": "HOME_02",
        "school_id": "SCHOOL_01",
        "vehicle_id": "VAN_01",
    },
    {
        "id": "STU_03",
        "name": "Student C",
        "home_id": "HOME_03",
        "school_id": "SCHOOL_01",
        "vehicle_id": "VAN_01",
    },
]

VEHICLE = {
    "id": "VAN_01",
    "capacity": 8,
}

# Invented travel durations in seconds.
# Row = starting location; column = destination.
# Location order matches LOCATIONS above.

MORNING_MATRIX = [
    [0,   240, 420, 600, 900],
    [260, 0,   180, 420, 660],
    [440, 200, 0,   180, 480],
    [620, 440, 200, 0,   240],
    [920, 680, 500, 260, 0],
]

AFTERNOON_MATRIX = [
    [0,   300, 480, 660, 960],
    [240, 0,   240, 480, 720],
    [420, 180, 0,   240, 540],
    [600, 420, 180, 0,   300],
    [900, 660, 480, 240, 0],
]