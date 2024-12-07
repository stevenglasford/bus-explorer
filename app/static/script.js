let userLat, userLng;
let map, userMarker;

function updateValue(slider, spanId) {
    document.getElementById(spanId).textContent = slider.value;
}

function initMap(lat, lng) {
    if (!map) {
        // Initialize the map
        map = L.map('map').setView([lat, lng], 13);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // Add a marker for the user's location
        userMarker = L.marker([lat, lng]).addTo(map).bindPopup('You are here').openPopup();
    } else {
        // Update map and marker if already initialized
        map.setView([lat, lng], 13);
        userMarker.setLatLng([lat, lng]);
    }
}

async function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                userLat = position.coords.latitude;
                userLng = position.coords.longitude;
                initMap(userLat, userLng);
            },
            (error) => {
                console.error('Error getting location:', error);
                alert('Unable to retrieve your location. Please enable location services.');
            }
        );
    } else {
        alert('Geolocation is not supported by your browser.');
    }
}

async function fetchRoutesAndStops() {
    console.log("button clicked!");
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;

    if (!userLat || !userLng) {
        alert("Location not yet determined.");
        return;
    }

    const loadingContainer = document.getElementById("loading-container");
    loadingContainer.style.display = "block";

    try {
        const response = await axios.get("/api/routes", {
            params: { lat: userLat, lon: userLng, radius: distance, frequency }
        });

        const data = response.data;

        // Hide loading spinner
        loadingContainer.style.display = "none";

        // Update the routes list
        const routesList = document.getElementById("routes-list");
        routesList.innerHTML = "";

        data.forEach((route) => {
            const button = document.createElement("button");
            button.textContent = `Route ${route.route_id} - ${route.description}`;
            button.style.backgroundColor = route.color;
            routesList.appendChild(button);
        });
    } catch (error) {
        console.error("Error fetching routes and stops:", error);
        alert("There was an error fetching the data. Please try again.");
            
        // Hide loading spinner
        loadingContainer.style.display = "none";
    }
}



// Get user location on page load
document.getElementById("get-routes-btn").addEventListener("click", fetchRoutesAndStops);
window.onload = getUserLocation;