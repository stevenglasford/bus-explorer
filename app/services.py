from datetime import datetime
import requests
from math import radians, sin, cos, sqrt, atan2

BASE_URL = "https://svc.metrotransit.org/nextrip"  # Replace with the actual API base URL if different.


# Distance calculation (unchanged)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1000  # Convert to meters

# Fetch nearby stops
def fetch_stops_nearby(user_lat, user_lon, max_distance):
    response = requests.get(f"{BASE_URL}/stops/all")
    response.raise_for_status()
    all_stops = response.json()

    # Filter stops within the distance bubble
    return [
        stop for stop in all_stops
        if calculate_distance(user_lat, user_lon, stop["latitude"], stop["longitude"]) <= max_distance
    ]

# Fetch departures and check frequency
def check_route_frequency(stop_id, frequency_limit):
    response = requests.get(f"{BASE_URL}/{stop_id}")
    response.raise_for_status()
    departures = response.json()["departures"]

    # Get the next 4 departures
    if len(departures) < 4:
        return False  # Not enough data to evaluate frequency

    departure_times = []
    for dep in departures[:4]:
        time_string = dep["departure_time"]  # Example format: "2024-12-02T14:30:00Z"
        time_obj = datetime.fromisoformat(time_string.replace("Z", "+00:00"))
        departure_times.append(time_obj)

    # Calculate intervals
    intervals = [(departure_times[i + 1] - departure_times[i]).total_seconds() / 60 for i in range(3)]
    avg_interval = sum(intervals) / len(intervals)

    return avg_interval <= frequency_limit

def fetch_routes():
    response = requests.get(f"{BASE_URL}/routes")
    response.raise_for_status()
    return response.json()

def fetch_stops(route_id, direction_id):
    response = requests.get(f"{BASE_URL}/stops/{route_id}/{direction_id}")
    response.raise_for_status()
    return response.json()

def fetch_departures(stop_id):
    response = requests.get(f"{BASE_URL}/{stop_id}")
    response.raise_for_status()
    return response.json()

def fetch_vehicles(route_id):
    response = requests.get(f"{BASE_URL}/vehicles/{route_id}")
    response.raise_for_status()
    return response.json()
