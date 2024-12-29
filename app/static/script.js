let userLat, userLng;
let map, userMarker;
let routeLayer = null; // For displaying selected routes on the map

// Update the displayed value of sliders
function updateValue(slider, spanId) {
    document.getElementById(spanId).textContent = slider.value;
}

// Initialize the map and user's marker
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

// Get user's location from the browser
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

// Fetch and display a route on the map
async function fetchAndDisplayRoute(routeId, branchLetter = null) {
    try {
        const response = await axios.get("/api/route_shape", {
            params: { route_id: routeId, branch_letter: branchLetter },
        });

        const geojsonData = response.data;

        // Remove existing route layer if present
        if (routeLayer) {
            map.removeLayer(routeLayer);
        }

        // Add the new route layer
        routeLayer = L.geoJSON(geojsonData, {
            style: { color: "blue", weight: 4 },
        }).addTo(map);

        // Adjust map view to fit the route
        const bounds = routeLayer.getBounds();
        map.fitBounds(bounds);
    } catch (error) {
        console.error("Error fetching route shape:", error);
        alert("Unable to display the route. Please try again.");
    }
}

// Fetch routes and stops and update the list
async function fetchRoutesAndStops() {
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;

    if (!userLat || !userLng) {
        alert("Location not yet determined.");
        return;
    }

    const loadingContainer = document.getElementById("loading-container");
    loadingContainer.style.display = "block";

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat: userLat, lon: userLng, distance, frequency },
        });

        const data = response.data;

        // Hide loading spinner
        loadingContainer.style.display = "none";

        // Update the routes list
        const routesList = document.getElementById("routes-list");
        routesList.innerHTML = ""; // Clear previous rows

        data.forEach((route) => {
            const routeRow = document.createElement("div");
            routeRow.classList.add("route-row");

            // Add Route and Branch Information
            const routeInfo = document.createElement("span");
            routeInfo.textContent = `Route ${route[0]}${route[1] ? ` - Branch ${route[1]}` : ""}: `;
            routeRow.appendChild(routeInfo);

            // Add Route Button
            const routeButton = document.createElement("button");
            routeButton.textContent = "View Route";
            routeButton.classList.add("route-btn");
            routeButton.style.backgroundColor = "blue";
            routeButton.style.color = "white";

            // Attach event to display the route on the map
            routeButton.addEventListener("click", () => {
                fetchAndDisplayRoute(route[0], route[1]);
            });

            routeRow.appendChild(routeButton);

            // Add Buttons for Each Schedule Type
            ["reduced", "holiday", "saturday", "sunday", "weekday"].forEach((schedType, index) => {
                const button = document.createElement("button");
                const flag = route[2 + index]; // Start from the 3rd column for schedule flags

                if (flag === 0) {
                    button.style.display = "none"; // Hide button if no trips
                } else {
                    button.textContent = schedType.charAt(0).toUpperCase() + schedType.slice(1); // Capitalize label
                    button.style.backgroundColor = flag === 1 ? "red" : "green"; // Red for 1, Green for 2
                    button.classList.add("schedule-button");
                }

                routeRow.appendChild(button);
            });

            routesList.appendChild(routeRow);
        });
    } catch (error) {
        console.error("Error fetching routes and stops:", error);
        alert("There was an error fetching the data. Please try again.");
    } finally {
        loadingContainer.style.display = "none";
    }
}

// Attach event listeners
document.getElementById("get-routes-btn").addEventListener("click", fetchRoutesAndStops);

// Get user location on page load
window.onload = getUserLocation;
