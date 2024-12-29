// Initialize map
const map = L.map("map").setView([44.9778, -93.2650], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let userLat, userLng;
let userMarker = null;
let routeLayer = null; // For route visualization

document.getElementById("get-stops-btn").addEventListener("click", () => {
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;

    if (!distance || distance <= 0) {
        alert("Please enter a valid walking distance.");
        return;
    }

    if (!frequency || frequency <= 0) {
        alert("Please enter a valid desired frequency.");
        return;
    }

    // Proceed with form submission or data fetching
});

// Show loading text
function showLoading() {
    const loadingText = document.getElementById("loading-text");
    loadingText.style.display = "inline";
}

// Hide loading text
function hideLoading() {
    const loadingText = document.getElementById("loading-text");
    loadingText.style.display = "none";
}

// Update user's location display
function updateLocationDisplay(lat, lon) {
    const locationElement = document.getElementById("user-location");
    locationElement.textContent = `Your Location: Latitude: ${lat.toFixed(6)}, Longitude: ${lon.toFixed(6)}`;
}

// Initialize or update map marker
function initMarker(lat, lng) {
    if (userMarker) {
        userMarker.setLatLng([lat, lng]);
    } else {
        userMarker = L.marker([lat, lng], { draggable: true }).addTo(map)
            .bindPopup("Drag to adjust your location.")
            .openPopup();

        userMarker.on("dragend", function () {
            const position = userMarker.getLatLng();
            userLat = position.lat;
            userLng = position.lng;
            updateLocationDisplay(userLat, userLng);
        });
    }
    map.setView([lat, lng], 13);
    updateLocationDisplay(lat, lng);
}

// Fetch user's geolocation
function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                userLat = position.coords.latitude;
                userLng = position.coords.longitude;
                initMarker(userLat, userLng);
            },
            () => {
                alert("Unable to retrieve location. Please use manual input.");
                initMarker(44.9778, -93.2650); // Default location
            }
        );
    } else {
        alert("Geolocation is not supported by your browser.");
        initMarker(44.9778, -93.2650); // Default location
    }
}

// Update location based on manual input
function updateManualLocation() {
    const latInput = parseFloat(document.getElementById("latitude").value.trim());
    const lonInput = parseFloat(document.getElementById("longitude").value.trim());

    if (isNaN(latInput) || isNaN(lonInput) || latInput < -90 || latInput > 90 || lonInput < -180 || lonInput > 180) {
        alert("Invalid coordinates. Please enter valid latitude and longitude.");
        return;
    }

    userLat = latInput;
    userLng = lonInput;
    initMarker(userLat, userLng);
}

// Fetch nearby stops and update the table
async function fetchNearbyStops() {
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;

    if (!userLat || !userLng) {
        alert("Location not yet determined.");
        return;
    }

    showLoading();

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat: userLat, lon: userLng, distance, frequency },
        });

        const data = response.data;
        const tableBody = document.querySelector("#routes-table tbody");
        tableBody.innerHTML = ""; // Clear previous rows

        data.forEach((row) => {
            const tr = document.createElement("tr");

            // Route and Branch
            const routeCell = document.createElement("td");
            routeCell.textContent = row[0]; // Route ID
            tr.appendChild(routeCell);

            const branchCell = document.createElement("td");
            branchCell.textContent = row[1] || "Main"; // Branch Letter or "Main"
            tr.appendChild(branchCell);

            // Schedule buttons for each schedule type
            ["reduced", "holiday", "saturday", "sunday", "weekday"].forEach((scheduleType, index) => {
                const value = row[index + 2];
                const cell = document.createElement("td");

                if (value === 0) {
                    cell.textContent = "N/A"; // No trips
                    cell.style.color = "#BDC3C7"; // Gray color
                } else {
                    const button = document.createElement("button");
                    button.textContent = scheduleType.charAt(0).toUpperCase() + scheduleType.slice(1);

                    if (value === 1) {
                        button.style.backgroundColor = "red"; // Frequency does not meet user desires
                        button.style.color = "white";
                    } else if (value === 2) {
                        button.style.backgroundColor = "green"; // Frequency meets user desires
                        button.style.color = "white";
                    }

                    button.classList.add("schedule-button");
                    cell.appendChild(button);
                }

                tr.appendChild(cell);
            });

            tableBody.appendChild(tr);
        });
    } catch (error) {
        console.error("Error fetching nearby stops:", error);
        alert("There was an error fetching the data. Please try again.");
    } finally {
        hideLoading();
    }
}

// Attach event listener to the fetch button
document.getElementById("get-stops-btn").addEventListener("click", fetchNearbyStops);

// Handle manual input toggle
document.getElementById("manual-coordinates").addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    document.getElementById("latitude").disabled = !isChecked;
    document.getElementById("longitude").disabled = !isChecked;

    if (isChecked) {
        updateManualLocation();
    }
});

// Event listeners for manual location updates
document.getElementById("latitude").addEventListener("change", updateManualLocation);
document.getElementById("longitude").addEventListener("change", updateManualLocation);

// Initialize geolocation or fallback
window.onload = getUserLocation;
