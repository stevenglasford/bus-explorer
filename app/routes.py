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
import sqlite3

##Constants
GTFS_URL = "https://svc.metrotransit.org/mtgtfs/gtfs.zip"
CACHE_DIR = "/tmp"
GTFS_FILENAME = "gtfs.zip"
COOKIE_NAME = "gtfs_last_updated"

def load_gtfs_to_sql(gtfs_zip_path, db_path):
    # Extract the GTFS zip file
    with zipfile.ZipFile(gtfs_zip_path, 'r') as zip_ref:
        zip_ref.extractall("gtfs_data")

    # Connect to SQLite database (or create it)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define GTFS files and corresponding SQL table names
    gtfs_files = [
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "calendar.txt",
        "calendar_dates.txt",
        "shapes.txt"
    ]

    for file_name in gtfs_files:
        file_path = os.path.join("gtfs_data", file_name)
        if os.path.exists(file_path):
            # Load the CSV file into a DataFrame
            df = pd.read_csv(file_path)

            # Create a table in SQLite
            table_name = file_name.replace(".txt", "")
            df.to_sql(table_name, conn, if_exists="replace", index=False)

            print(f"Loaded {file_name} into table {table_name}.")

    # Commit changes and close the connection
    conn.commit()
    conn.close()
    print("GTFS data loaded into database successfully!")

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

# Update the handle_gtfs function
@main.route('/api/gtfs')
def handle_gtfs():
    """Check if the GTFS file needs to be updated or served."""
    gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
    db_path = os.path.join(CACHE_DIR, "gtfs.db")  # Path for SQLite database
    last_modified_cookie = request.cookies.get(COOKIE_NAME)
    # last_load_cookie = request.cookies.get(COOKIE_NAME)

    # Check if the GTFS file exists and is recent
    if os.path.exists(gtfs_path):
        file_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(gtfs_path))).total_seconds()
        if file_age < 86400:  # File is less than a day old
            print("GTFS file is less than a day old. Skipping download.")
            # Ensure the SQLite database exists
            if not os.path.exists(db_path):
                print("SQLite database missing. Loading GTFS data into database.")
                load_gtfs_to_sql(gtfs_path, db_path)
            else:
                print("SQLite database exists. Skipping data reload.")
            return send_file(gtfs_path)

    headers = {}
    if last_modified_cookie:
        # Add "If-Modified-Since" header if we have a cookie
        headers["If-Modified-Since"] = last_modified_cookie

    # Make a HEAD request to check "Last-Modified"
    response = requests.head(GTFS_URL, headers=headers)
    if response.status_code == 304:
        # File has not been modified; serve the cached file
        if os.path.exists(gtfs_path):
            print("GTFS file not modified. Serving cached file.")
            if not os.path.exists(db_path):
                print("SQLite database missing. Loading GTFS data into database.")
                load_gtfs_to_sql(gtfs_path, db_path)
            else:
                print("SQLite database exists. Skipping data reload.")
            return send_file(gtfs_path)

    if response.status_code == 200:
        # File has been modified or no cache exists; download the updated file
        print("GTFS file updated. Downloading new file.")
        gtfs_path = download_gtfs_file()
        last_modified = response.headers.get("Last-Modified", datetime.now().strftime("%Y-%m-%d"))

        # Load GTFS data into SQLite
        print("Reloading data into database.")
        load_gtfs_to_sql(gtfs_path, db_path)

        # Set a cookie with the new "Last-Modified" date
        response = make_response(send_file(gtfs_path))
        response.set_cookie(COOKIE_NAME, last_modified, max_age=7 * 24 * 60 * 60)
        return response

    # Handle errors gracefully
    return jsonify({"error": "Failed to fetch GTFS data"}), response.status_code


# @main.route('/api/gtfs')
# def handle_gtfs():
#     """Handle GTFS file fetching and database loading."""
#     gtfs_path = os.path.join(CACHE_DIR, GTFS_FILENAME)
#     db_path = os.path.join(CACHE_DIR, "gtfs.db")  # Path for SQLite database
#     last_load_cookie = request.cookies.get(COOKIE_NAME)

#     # Check if this is a fresh load (no cookie) or the file is missing
#     if not last_load_cookie or not os.path.exists(gtfs_path):
#         print("Fresh page load or missing GTFS file. Fetching data.")
#         gtfs_path = download_gtfs_file()
#         load_gtfs_to_sql(gtfs_path, db_path)

#         # Set a cookie to track this load
#         last_loaded_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
#         response = make_response(send_file(gtfs_path))
#         response.set_cookie(COOKIE_NAME, last_loaded_time, max_age=7 * 24 * 60 * 60)  # Cookie expires in 7 days
#         return response

#     # If the GTFS file exists and cookie is present, check if the database exists
#     if os.path.exists(gtfs_path):
#         if not os.path.exists(db_path):
#             print("SQLite database missing. Reloading GTFS data into the database.")
#             load_gtfs_to_sql(gtfs_path, db_path)
#         else:
#             print("SQLite database exists. Skipping data reload.")
#         return send_file(gtfs_path)

#     # Default to a graceful failure if something unexpected occurs
#     return jsonify({"error": "Failed to fetch GTFS data"}), 500


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

def normalize_departure_time(time_str):
    """Normalize extended times like '25:54:00' to '01:54:00' and track day offset."""
    hours, minutes, seconds = map(int, time_str.split(":"))
    if hours >= 24:
        hours -= 24
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}", 1  # Add one day offset
    return time_str, 0  # No offset

@main.route('/api/schedule/nearby', methods=['GET'])
def schedule_nearby():
    """Find nearby stops and analyze GTFS data."""
    try:
        ## handle gtfs
        handle_gtfs()
        # Get user input
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
        distance_limit = float(request.args.get("distance"))
        frequency_limit = float(request.args.get("frequency"))

        # Connect to the database
        db_path = os.path.join(CACHE_DIR, "gtfs.db")
        conn = sqlite3.connect(db_path)

        # SQL query with bindings
        query = """
        WITH nearby_stops AS (
            SELECT 
                stop_id,
                stop_lat,
                stop_lon,
                (
                    6371000 * 2 * ATAN2(
                        SQRT(
                            SIN(RADIANS(stop_lat - :user_lat) / 2) * SIN(RADIANS(stop_lat - :user_lat) / 2) +
                            COS(RADIANS(:user_lat)) * COS(RADIANS(stop_lat)) *
                            SIN(RADIANS(stop_lon - :user_lon) / 2) * SIN(RADIANS(stop_lon - :user_lon) / 2)
                        ),
                        SQRT(1 - (
                            SIN(RADIANS(stop_lat - :user_lat) / 2) * SIN(RADIANS(stop_lat - :user_lat) / 2) +
                            COS(RADIANS(:user_lat)) * COS(RADIANS(stop_lat)) *
                            SIN(RADIANS(stop_lon - :user_lon) / 2) * SIN(RADIANS(stop_lon - :user_lon) / 2)
                        ))
                    )
                ) * 3.28084 AS distance_feet
            FROM stops
            WHERE (
                6371000 * 2 * ATAN2(
                    SQRT(
                        SIN(RADIANS(stop_lat - :user_lat) / 2) * SIN(RADIANS(stop_lat - :user_lat) / 2) +
                        COS(RADIANS(:user_lat)) * COS(RADIANS(stop_lat)) *
                        SIN(RADIANS(stop_lon - :user_lon) / 2) * SIN(RADIANS(stop_lon - :user_lon) / 2)
                    ),
                    SQRT(1 - (
                        SIN(RADIANS(stop_lat - :user_lat) / 2) * SIN(RADIANS(stop_lat - :user_lat) / 2) +
                        COS(RADIANS(:user_lat)) * COS(RADIANS(stop_lat)) *
                        SIN(RADIANS(stop_lon - :user_lon) / 2) * SIN(RADIANS(stop_lon - :user_lon) / 2)
                    ))
                )
            ) * 3.28084 <= :distance_limit
        ),
        trip_times AS (
            SELECT 
                t.route_id,
                t.branch_letter,
                st.trip_id,
                st.stop_id,
                st.departure_time,
                (
                    CASE 
                        WHEN CAST(SUBSTR(st.departure_time, 1, 2) AS INTEGER) >= 24 
                        THEN (CAST(SUBSTR(st.departure_time, 1, 2) AS INTEGER) - 24) * 3600 +
                             CAST(SUBSTR(st.departure_time, 4, 2) AS INTEGER) * 60 +
                             CAST(SUBSTR(st.departure_time, 7, 2) AS INTEGER) + 86400
                        ELSE CAST(SUBSTR(st.departure_time, 1, 2) AS INTEGER) * 3600 +
                             CAST(SUBSTR(st.departure_time, 4, 2) AS INTEGER) * 60 +
                             CAST(SUBSTR(st.departure_time, 7, 2) AS INTEGER)
                    END
                ) AS departure_time_seconds,
                (CASE 
                    WHEN t.trip_id LIKE '%Reduced%' THEN 'Reduced'
                    WHEN t.trip_id LIKE '%Holiday%' THEN 'Holiday'
                    WHEN t.trip_id LIKE '%Saturday%' THEN 'Saturday'
                    WHEN t.trip_id LIKE '%Sunday%' THEN 'Sunday'
                    ELSE 'Weekday'
                END) AS schedule_type
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN nearby_stops ns ON st.stop_id = ns.stop_id
        ),
        frequency_analysis AS (
            SELECT 
                route_id,
                branch_letter,
                schedule_type,
                COUNT(*) AS total_trips,
                MIN(departure_time_seconds) AS first_trip,
                MAX(departure_time_seconds) AS last_trip,
                CASE 
                    WHEN COUNT(*) > 1 THEN (MAX(departure_time_seconds) - MIN(departure_time_seconds)) / (COUNT(*) - 1) / 60
                    ELSE NULL
                END AS average_frequency
            FROM trip_times
            GROUP BY route_id, branch_letter, schedule_type
        ),
        frequency_flags AS (
            SELECT 
                route_id,
                branch_letter,
                schedule_type,
                total_trips,
                first_trip,
                last_trip,
                average_frequency,
                CASE 
                    WHEN total_trips = 0 THEN 0
                    WHEN average_frequency > :frequency_limit THEN 1
                    ELSE 2
                END AS frequency_flag
            FROM frequency_analysis
        )
        SELECT 
            route_id,
            branch_letter,
            MAX(CASE WHEN schedule_type = 'Reduced' THEN frequency_flag ELSE 0 END) AS reduced,
            MAX(CASE WHEN schedule_type = 'Holiday' THEN frequency_flag ELSE 0 END) AS holiday,
            MAX(CASE WHEN schedule_type = 'Saturday' THEN frequency_flag ELSE 0 END) AS saturday,
            MAX(CASE WHEN schedule_type = 'Sunday' THEN frequency_flag ELSE 0 END) AS sunday,
            MAX(CASE WHEN schedule_type = 'Weekday' THEN frequency_flag ELSE 0 END) AS weekday
        FROM frequency_flags
        GROUP BY route_id, branch_letter
        ORDER BY route_id, branch_letter;
        """

        # Execute the query with parameters
        cursor = conn.cursor()
        cursor.execute(query, {
            "user_lat": user_lat,
            "user_lon": user_lon,
            "distance_limit": distance_limit,
            "frequency_limit": frequency_limit
        })
        results = cursor.fetchall()

        # Close the connection
        conn.close()

        print("Frequencies calculated.")
        with open("frequency_data.json", "w") as json_file:
            json.dump(results, json_file, indent=4)



        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
#make a bus route on the map after the user clicks the bus route
@main.route('/api/route_shape', methods=['GET'])
def route_shape():
    """
    Fetch and return the GeoJSON shape of a specified route and branch.
    """
    print('Trying to shape out the route')
    try:
        # Retrieve route_id and branch_letter from request parameters
        route_id = request.args.get("route_id")
        branch_letter = request.args.get("branch_letter", None)  # Optional

        if not route_id:
            return jsonify({"error": "Route ID is required"}), 400

        # Connect to SQLite database
        db_path = os.path.join(CACHE_DIR, "gtfs.db")
        conn = sqlite3.connect(db_path)

        # Build SQL query to get shape data
        query = """
            SELECT s.shape_id, s.shape_pt_lat AS lat, s.shape_pt_lon AS lon, s.shape_pt_sequence AS seq
            FROM shapes s
            JOIN trips t ON s.shape_id = t.shape_id
            WHERE t.route_id = ?
        """

        params = [route_id]

        # If branch_letter is provided, add it to the query
        if branch_letter:
            query += " AND t.branch_letter = ?"
            params.append(branch_letter)

        query += " ORDER BY s.shape_id, s.shape_pt_sequence"

        # Execute query
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "No shape data found for the specified route and branch"}), 404

        # Group data by shape_id
        from collections import defaultdict
        shapes = defaultdict(list)
        for row in rows:
            shape_id = row[0]
            lat, lon = row[1], row[2]
            shapes[shape_id].append((lon, lat))  # (lon, lat) format

        # Prepare GeoJSON structure
        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        for shape_id, coordinates in shapes.items():
            geojson["features"].append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "properties": {
                    "route_id": route_id,
                    "branch_letter": branch_letter,
                    "shape_id": shape_id
                }
            })

        return jsonify(geojson)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

#Find the POIs along the route
@main.route('/api/pois_along_route', methods=['GET'])
def pois_along_route():
    print("Trying to find POIs along the route")
    """
    Fetch POIs along the specified route, filtered by direction and distance.
    """
    try:
        # Retrieve route_id, branch_letter, user coordinates, and walking distance
        route_id = request.args.get("route_id")
        branch_letter = request.args.get("branch_letter", None)  # Optional
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
        walking_distance = float(request.args.get("distance"))

        if not route_id or not user_lat or not user_lon or not walking_distance:
            return jsonify({"error": "Missing required parameters"}), 400

        # Connect to SQLite database
        db_path = os.path.join(CACHE_DIR, "gtfs.db")
        conn = sqlite3.connect(db_path)

        # Query shape points for the route and branch
        query = """
            SELECT s.shape_pt_lat AS lat, s.shape_pt_lon AS lon, s.shape_pt_sequence AS seq
            FROM shapes s
            JOIN trips t ON s.shape_id = t.shape_id
            WHERE t.route_id = ?
        """
        params = [route_id]
        if branch_letter:
            query += " AND t.branch_letter = ?"
            params.append(branch_letter)
        query += " ORDER BY s.shape_id, s.shape_pt_sequence"

        cursor = conn.cursor()
        cursor.execute(query, params)
        shape_points = cursor.fetchall()
        conn.close()

        if not shape_points:
            return jsonify({"error": "No shape data found for the specified route"}), 404

        # Calculate the direction vector for the route
        route_direction = (
            shape_points[-1][0] - shape_points[0][0],
            shape_points[-1][1] - shape_points[0][1]
        )

        # Fetch POIs from OSM within the bounding box of the route
        bounding_box = (
            min(lat for lat, _, _ in shape_points) - 0.01,
            min(lon for _, lon, _ in shape_points) - 0.01,
            max(lat for lat, _, _ in shape_points) + 0.01,
            max(lon for _, lon, _ in shape_points) + 0.01
        )

        overpass_query = f"""
        [out:json];
        node
          ["amenity"]
          ({bounding_box[0]},{bounding_box[1]},{bounding_box[2]},{bounding_box[3]});
        out body;
        """
        response = requests.post("https://overpass-api.de/api/interpreter", data={"data": overpass_query})
        response.raise_for_status()
        pois = response.json()["elements"]

        # Filter POIs by walking distance and direction
        filtered_pois = []
        for poi in pois:
            poi_lat = poi["lat"]
            poi_lon = poi["lon"]

            # Calculate distance from the user
            distance = haversine_distance(user_lat, user_lon, poi_lat, poi_lon)
            if distance > walking_distance:
                continue

            # Calculate direction relative to the route
            direction_vector = (poi_lat - user_lat, poi_lon - user_lon)
            dot_product = (
                route_direction[0] * direction_vector[0] +
                route_direction[1] * direction_vector[1]
            )
            if dot_product <= 0:  # Skip POIs opposite to the route's direction
                continue

            filtered_pois.append({
                "name": poi.get("tags", {}).get("name", "Unknown POI"),
                "type": poi.get("tags", {}).get("amenity", "Unknown Type"),
                "distance": distance,
                "coordinates": (poi_lat, poi_lon)
            })

        # Sort POIs by distance
        filtered_pois.sort(key=lambda x: x["distance"])

        return jsonify(filtered_pois)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
