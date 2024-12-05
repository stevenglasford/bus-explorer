from flask import Blueprint, render_template, jsonify, request
from math import radians, sin, cos, sqrt, atan2
from .services import fetch_routes
from .services import fetch_stops
from .services import fetch_departures
from .services import fetch_stops_nearby, check_route_frequency


# Define a Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c * 1000  # Convert to meters

def filter_stops_by_distance(stops, user_lat, user_lon, max_distance):
    return [
        stop for stop in stops
        if calculate_distance(user_lat, user_lon, stop['latitude'], stop['longitude']) <= max_distance
    ]

@main.route('/routes')
def routes():
    try:
        routes = fetch_routes()
        return render_template('routes.html', routes=routes)
    except requests.HTTPError as e:
        return jsonify({"error": str(e)}), 500

@main.route('/stops', methods=['GET'])
def stops():
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
def departures():
    stop_id = request.args.get('stop_id')
    try:
        departures = fetch_departures(stop_id)
        return jsonify(departures)
    except requests.HTTPError as e:
        return jsonify({"error": str(e)}), 500    
    
@main.route('/api/stops', methods=['GET'])
def stops():
    user_lat = float(request.args.get('lat'))
    user_lng = float(request.args.get('lng'))
    max_distance = float(request.args.get('distance'))

    stops = fetch_stops_nearby(user_lat, user_lng, max_distance)
    return jsonify(stops)

@main.route('/api/routes', methods=['GET'])
def routes():
    stop_ids = request.args.getlist('stops')
    frequency_limit = int(request.args.get('frequency'))

    routes = []
    for stop_id in stop_ids:
        is_frequent = check_route_frequency(stop_id, frequency_limit)
        routes.append({"route_id": stop_id, "is_frequent": is_frequent})

    return jsonify(routes)