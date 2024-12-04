from flask import render_template, request, jsonify
from .services import get_nearby_stops

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stops', methods=['GET'])
def stops():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', type=int, default=1000)
    frequency = request.args.get('frequency', type=int)

    stops = get_nearby_stops(lat, lng, radius, frequency)
    return jsonify(stops)
