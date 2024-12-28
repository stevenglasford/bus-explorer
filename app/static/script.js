let userLat, userLng;
let map, userMarker;

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

// Fetch nearby routes and stops from the API
async function fetchRoutesAndStops() {
    console.log("Fetching routes and stops...");
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
        routesList.innerHTML = ""; // Clear previous data

        data.forEach((route) => {
            const row = document.createElement("div");
            row.classList.add("route-row");

            const routeInfo = document.createElement("div");
            routeInfo.textContent = `Route ${route[0]} - ${route[1] || "Main"}`;
            routeInfo.style.fontWeight = "bold";
            row.appendChild(routeInfo);

            ["reduced", "holiday", "saturday", "sunday", "weekday"].forEach((scheduleType, index) => {
                const value = route[index + 2];

                if (value === 0) {
                    // No trips for this schedule type
                    const span = document.createElement("span");
                    span.textContent = "N/A";
                    span.style.marginRight = "10px";
                    span.style.color = "#BDC3C7"; // Gray color for "N/A"
                    row.appendChild(span);
                } else {
                    // Create a button for valid schedule types
                    const button = document.createElement("button");
                    button.textContent = scheduleType.charAt(0).toUpperCase() + scheduleType.slice(1);

                    // Set button color based on frequency flag
                    if (value === 1) {
                        button.style.backgroundColor = "red"; // Frequency does not meet user desires
                        button.style.color = "white";
                    } else if (value === 2) {
                        button.style.backgroundColor = "green"; // Frequency meets user desires
                        button.style.color = "white";
                    }

                    button.classList.add("schedule-button");
                    row.appendChild(button);
                }
            });

            routesList.appendChild(row);
        });
    } catch (error) {
        console.error("Error fetching routes and stops:", error);
        alert("There was an error fetching the data. Please try again.");

        // Hide loading spinner
        loadingContainer.style.display = "none";
    }
}

// Attach event listeners
document.getElementById("get-routes-btn").addEventListener("click", fetchRoutesAndStops);

// Get user location on page load
window.onload = getUserLocation;
