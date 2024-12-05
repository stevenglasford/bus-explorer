import requests

BASE_URL = "https://svc.metrotransit.org/nextrip"  # Replace with the actual API base URL if different.

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
