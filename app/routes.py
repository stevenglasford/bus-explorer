from flask import Blueprint, json, render_template, jsonify, request, make_response, send_file
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import zipfile
import pandas as pd
from .services import fetch_routes, fetch_stops, fetch_departures, fetch_stops_nearby, check_route_frequency, fetch_osm_bus_stops, fetch_stop_departures, calculate_frequency, fetch_osm_bus_stops, fetch_all_departures, calculate_frequency
import asyncio
import requests
import os
import multiprocessing as mp
import numpy as np

##Constants
GTFS_URL = "https://svc.metrotransit.org/mtgtfs/gtfs.zip"
CACHE_DIR = "/tmp"
GTFS_FILENAME = "gtfs.zip"
COOKIE_NAME = "gtfs_last_updated"

# Define a Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('landing.html')

@main.route('/realtime')
def realtime_page():
    return render_template('index.html')  # Existing real-time page

@main.route('/schedule')
def schedule_page():
    return render_template('schedule.html')

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance in feet between two lat/lon points using the Haversine formula."""
    R = 6371000  # Radius of Earth in meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance_meters = R * c
    return distance_meters * 3.28084  # Convert to feet

def get_walking_distance(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/walking/{lon1},{lat1};{lon2},{lat2}?overview=false"
    response = requests.get(url)
    data = response.json()

    if "routes" in data and len(data["routes"]) > 0:
        return data["routes"][0]["distance"]  # Distance in meters
    else:
        return None

# # Example usage
# walking_distance = get_walking_distance(user_lat, user_lon, stop_lat, stop_lon)
# print(f"Walking Distance: {walking_distance / 1609.34:.2f} miles")

def filter_stops_by_distance(stops, user_lat, user_lon, max_distance):
    return [
        stop for stop in stops
        if calculate_distance(user_lat, user_lon, stop["latitude"], stop["longitude"]) <= max_distance
    ]

@main.route('/routes')
def list_routes():
    try:
        routes = fetch_routes()
        return render_template('routes.html', routes=routes)
    except requests.HTTPError as e:
        return jsonify({"error": str(e)}), 500

@main.route('/stops', methods=['GET'])
def stops_by_route():
    route_id = request.args.get('route_id')
    direction_id = request.args.get('direction_id')
    user_lat = float(request.args.get('lat'))
    user_lon = float(request.args.get('lon'))
    max_distance = float(request.args.get('max_distance'))

    try:
        stops = fetch_stops(route_id, direction_id)
        filtered_stops = filter_stops_by_distance(stops, user_lat, user_lon, max_distance)
        return jsonify(filtered_stops)
    except requests.HTTPError as e:
        return jsonify({"error": str(e)}), 500

@main.route('/departures', methods=['GET'])
def list_departures():
    stop_id = request.args.get('stop_id')
    try:
        departures = fetch_departures(stop_id)
        return jsonify(departures)
    except requests.HTTPError as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/stops', methods=['GET'])
def stops_nearby():
    user_lat = float(request.args.get('lat'))
    user_lng = float(request.args.get('lng'))
    max_distance = float(request.args.get('distance'))

    stops = fetch_stops_nearby(user_lat, user_lng, max_distance)
    return jsonify(stops)

@main.route('/api/routes', methods=['GET'])
def get_routes_and_stops():
    user_lat = float(request.args.get('lat'))
    user_lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius'))
    frequency_limit = float(request.args.get('frequency'))

    try:
        # Fetch nearby stops from OSM
        osm_stops = fetch_osm_bus_stops(user_lat, user_lon, radius)

        # Collect all stops with their routes
        stops_info = []
        for stop in osm_stops:
            route_string = stop.get("tags", {}).get("route", "")
            stop_id = stop.get("tags", {}).get("metcouncil:site_id")
            if not stop_id or not route_string:
                continue

            routes = route_string.split()  # Split space-separated route numbers
            stops_info.append({
                "stop_id": stop_id,
                "latitude": stop.get("lat"),
                "longitude": stop.get("lon"),
                "routes": routes
            })

        # Fetch departures for all stops asynchronously
        stop_ids = [stop["stop_id"] for stop in stops_info]
        departure_data = asyncio.run(fetch_all_departures(stop_ids))

        # Find the closest stop for each route
        closest_stops = {}
        current_time = int(datetime.now().timestamp())

        for stop_info, stop_data in zip(stops_info, departure_data):
            if not stop_data or "departures" not in stop_data:
                continue

            stop_distance = calculate_distance(
                user_lat, user_lon, stop_info["latitude"], stop_info["longitude"]
            )

            for route in stop_info["routes"]:
                # Filter departures for this route
                departures = [
                    dep for dep in stop_data["departures"] if dep["route_id"] == route
                ]

                # Count the number of valid departures
                num_departures = len(departures)

                # Determine the route's color
                if num_departures == 0:
                    color = "white"  # No buses scheduled
                elif num_departures <= 2:
                    color = "black"  # Few buses remaining
                else:
                    avg_frequency = calculate_frequency(departures, current_time)
                    color = (
                        "green" if avg_frequency is not None and avg_frequency <= frequency_limit
                        else "red"
                    )

                # Check if this stop is closer for this route
                if (
                    route not in closest_stops
                    or stop_distance < closest_stops[route]["distance"]
                ):
                    closest_stops[route] = {
                        "stop_id": stop_info["stop_id"],
                        "description": stop_data.get("stops", [{}])[0].get("description", ""),
                        "distance": stop_distance,
                        "frequency": calculate_frequency(departures, current_time),
                        "num_departures": num_departures,
                        "color": color,
                    }

        # Format results
        results = [
            {
                "route_id": route_id,
                "stop_id": info["stop_id"],
                "description": info["description"],
                "distance": info["distance"],
                "frequency": info["frequency"],
                "num_departures": info["num_departures"],
                "color": info["color"],
            }
            for route_id, info in closest_stops.items()
        ]

        return jsonify(results)
    except Exception as e:
        print(f"Error fetching routes and stops: {e}")
        return jsonify({"error": str(e)}), 500
    
def download_gtfs_file():
    """Download the GTFS file from the URL and save it to the cache directory."""
    response = requests.get(GTFS_URL, stream=True)
    response.raise_for_status()
    gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
    with open(gtfs_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return gtfs_path

@main.route('/api/gtfs')
def handle_gtfs():
    """Check if the GTFS file needs to be updated or served."""
    gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
    last_modified_cookie = request.cookies.get(COOKIE_NAME)

    headers = {}
    if last_modified_cookie:
        # Add "If-Modified-Since" header if we have a cookie
        headers["If-Modified-Since"] = last_modified_cookie

    # Make a HEAD request to check "Last-Modified"
    response = requests.head(GTFS_URL, headers=headers)
    if response.status_code == 304:
        # File has not been modified; serve the cached file
        if os.path.exists(gtfs_path):
            return send_file(gtfs_path)

    if response.status_code == 200:
        # File has been modified; download the updated file
        gtfs_path = download_gtfs_file()
        last_modified = response.headers.get("Last-Modified", datetime.now().strftime("%Y-%m-%d"))

        # Set a cookie with the new "Last-Modified" date
        response = make_response(send_file(gtfs_path))
        response.set_cookie(COOKIE_NAME, last_modified, max_age=7 * 24 * 60 * 60)
        return response

    # Handle errors gracefully
    return jsonify({"error": "Failed to fetch GTFS data"}), response.status_code


@main.route('/api/schedule', methods=['GET'])
def schedule_data():
    # Fetch the GTFS file path from the /api/gtfs route
    gtfs_path = "/tmp/gtfs.zip"  # Cached file path

    if not os.path.exists(gtfs_path):
        download_gtfs_file()

    with zipfile.ZipFile(gtfs_path, 'r') as z:
        # Load relevant GTFS files
        ##debugging start
        file_list = z.namelist()
        print("Files in GTFS zip:", file_list)
        ##debugging end
        with z.open('stops.txt') as f:
            stops = pd.read_csv(f)
            ##debuging start
            print("Stops sample:", stops.head())
            ## debuging end
        with z.open('stop_times.txt') as f:
            stop_times = pd.read_csv(f)

    # Merge stops with stop_times
    schedule = stop_times.merge(stops, on='stop_id')

    # Simplify schedule data
    schedule_data = schedule[['trip_id', 'arrival_time', 'departure_time', 'stop_name']].head(10)

    return jsonify(schedule_data.to_dict(orient='records'))

def get_nearby_stops(lat, lon, distance_feet):
    """Query OpenStreetMap for nearby bus stops."""
    # Convert distance from feet to meters (1 foot = 0.3048 meters)
    radius_meters = distance_feet * 0.3048
    query = f"""
    [out:json];
    node["highway"="bus_stop"](around:{radius_meters},{lat},{lon});
    out body;
    """
    response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query})
    response.raise_for_status()
    return response.json()["elements"]

def filter_stop_times_by_stop_id(stop_id, stop_times):
    """Filter stop_times for a specific stop_id."""
    return stop_times[stop_times["stop_id"] == stop_id]["trip_id"].unique()

@main.route('/api/schedule/nearby', methods=['GET'])
def schedule_nearby():
    """Find nearby stops and parse GTFS data for routes and branches."""
    print("got to the nearby_stops")
    try:
        # Get user input
        print("get user stuff")
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
        distance_feet = float(request.args.get("distance"))
        frequency_limit = float(request.args.get("frequency"))

        # Load GTFS data
        print("Check for the gtfs")
        handle_gtfs()
        print("Got the gtfs")
        gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
        with zipfile.ZipFile(gtfs_path, 'r') as z:
            with z.open('stops.txt') as f:
                stops = pd.read_csv(f)
            with z.open('stop_times.txt') as f:
                stop_times = pd.read_csv(f)
            with z.open('trips.txt') as f:
                trips = pd.read_csv(f)

        print("Raw data loaded.")

        # Step 1: Filter stops by distance using vectorized operations
        print("Filtering stops by distance...")
        stops_coords = np.radians(stops[["stop_lat", "stop_lon"]].values)
        user_coords = np.radians([user_lat, user_lon])
        dlat = stops_coords[:, 0] - user_coords[0]
        dlon = stops_coords[:, 1] - user_coords[1]
        a = np.sin(dlat / 2) ** 2 + np.cos(stops_coords[:, 0]) * np.cos(user_coords[0]) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        stops["distance"] = 6371000 * c * 3.28084  # Earth radius in meters, converted to feet
        nearby_stops = stops[stops["distance"] <= distance_feet]
        nearby_stop_ids = pd.to_numeric(nearby_stops["stop_id"]).tolist()  # Convert to numeric
        print("Nearby stops filtered:", len(nearby_stops))

        # Step 2: Filter stop_times by nearby stop IDs
        print("Filtering stop_times...")
        matching_trip_ids = stop_times[stop_times["stop_id"].isin(nearby_stop_ids)]["trip_id"].unique()
        print("Matching trip IDs:", len(matching_trip_ids))

        # Step 3: Find unique route and branch combinations with schedule types
        print("Processing trips...")
        trips["schedule_type"] = trips["trip_id"].apply(
            lambda x: next(
                (sched for sched in ["Reduced", "Saturday", "Sunday", "Holiday", "Weekday"] if sched in x),
                None,
            )
        )
        unique_routes = trips[trips["trip_id"].isin(matching_trip_ids)][
            ["route_id", "branch_letter", "schedule_type", "trip_id"]
        ]
        print("Unique routes processed.")
        print(unique_routes.groupby("schedule_type").size())


        # Step 4: Calculate frequencies
        print("Calculating frequencies...")
        stop_times["arrival_time_seconds"] = stop_times["arrival_time"].apply(
            lambda x: sum(int(t) * 60 ** i for i, t in enumerate(reversed(x.split(":"))))
        )

        frequency_data = []

        # Group by route_id and branch_letter
        for (route_id, branch_letter), group in unique_routes.groupby(["route_id", "branch_letter"]):
            print(f"Processing Group: Route {route_id}, Branch {branch_letter}")
            group_trip_ids = group["trip_id"].unique()
            print("Group Trip IDs:", group_trip_ids)

            # Filter relevant stop_times
            relevant_stop_times = stop_times[stop_times["trip_id"].isin(group_trip_ids)]
            print("Relevant Stop Times:", relevant_stop_times)

            if relevant_stop_times.empty:
                print("No relevant stop times. Skipping...")
                frequency_data.append({
                    "route": f"{route_id}{branch_letter}",
                    "schedule_type": group["schedule_type"].iloc[0],
                    "meets_frequency": False  # Default to False if no data
                })
                continue

            # Calculate frequency
            first_trip = relevant_stop_times["arrival_time_seconds"].min()
            last_trip = relevant_stop_times["arrival_time_seconds"].max()
            total_trips = relevant_stop_times["trip_id"].nunique()

            if total_trips > 1:
                average_frequency = (last_trip - first_trip) / (total_trips - 1)
            else:
                average_frequency = float("inf")

            meets_frequency = average_frequency <= frequency_limit * 60

            # Debugging group and frequency calculation
            # print(f"First Trip: {first_trip}, Last Trip: {last_trip}, Total Trips: {total_trips}")
            # print(f"Average Frequency: {average_frequency}, Meets Frequency: {meets_frequency}")

            # Append to frequency_data
            frequency_data.append({
                "route": f"{route_id}{branch_letter}",
                "schedule_type": group["schedule_type"].iloc[0],
                "meets_frequency": bool(meets_frequency)
            })


        print("Frequencies calculated.")
        with open("frequency_dump.txt", "w") as json_file:
            json.dump(frequency_data, json_file, indent=4)

        print(frequency_data)
        return jsonify(frequency_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route('/api/route_shape', methods=['GET'])
def route_shape():
    """Return the shape of the selected route."""
    try:
        route_id = request.args.get("route_id")
        branch_letter = request.args.get("branch_letter")
        
        # Load GTFS data
        gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
        with zipfile.ZipFile(gtfs_path, 'r') as z:
            with z.open('shapes.txt') as f:
                shapes = pd.read_csv(f)
            with z.open('trips.txt') as f:
                trips = pd.read_csv(f)

        # Filter trips for the selected route and branch
        selected_trips = trips[
            (trips["route_id"] == route_id) & 
            (trips["branch_letter"] == branch_letter)
        ]
        shape_ids = selected_trips["shape_id"].unique()

        # Filter shapes for the selected trips
        route_shapes = shapes[shapes["shape_id"].isin(shape_ids)]
        route_shapes = route_shapes.sort_values(by=["shape_id", "shape_pt_sequence"])

        # Prepare GeoJSON data
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }
        for shape_id, shape_group in route_shapes.groupby("shape_id"):
            coordinates = shape_group[["shape_pt_lon", "shape_pt_lat"]].values.tolist()
            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "properties": {"shape_id": shape_id}
            })

        return jsonify(geojson_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
