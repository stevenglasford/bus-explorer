from flask import Blueprint, render_template, jsonify, request
from math import radians, sin, cos, sqrt, atan2
from .services import fetch_routes, fetch_stops, fetch_departures, fetch_stops_nearby, check_route_frequency, fetch_osm_bus_stops, fetch_stop_departures, calculate_frequency


# Define a Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1000  # Convert to meters

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
# def routes_by_frequency():
#     stop_ids = request.args.getlist('stops')
#     frequency_limit = int(request.args.get('frequency'))

#     routes = []
#     for stop_id in stop_ids:
#         is_frequent = check_route_frequency(stop_id, frequency_limit)
#         routes.append({"route_id": stop_id, "is_frequent": is_frequent})

#     return jsonify(routes)

def get_routes_and_stops():
    user_lat = float(request.args.get('lat'))
    user_lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius'))
    frequency_limit = float(request.args.get('frequency'))

    try:
        # Fetch nearby stops from OSM
        osm_stops = fetch_osm_bus_stops(user_lat, user_lon, radius)
        results = []

        for stop in osm_stops:
            # Use `metcouncil:site_id` to query Metro Transit API
            stop_id = stop.get("tags", {}).get("metcouncil:site_id")
            if not stop_id:
                continue

            stop_data = fetch_stop_departures(stop_id)
            departures = stop_data.get("departures", [])
            current_time = int(datetime.now().timestamp())
            avg_frequency = calculate_frequency(departures, current_time)

            # Determine if the route meets the frequency criteria
            print(departures)
            for dep in departures:
                route_id = dep["route_id"]
                meets_frequency = avg_frequency is not None and avg_frequency <= frequency_limit

                results.append({
                    "stop_id": stop_id,
                    "route_id": route_id,
                    "description": stop_data.get("stops", [{}])[0].get("description", ""),
                    "frequency": avg_frequency,
                    "meets_frequency": meets_frequency,
                })
            
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
