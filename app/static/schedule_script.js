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

        // Clear existing rows
        const scheduleBody = document.querySelector("#schedule-table tbody");
        const actionBody = document.querySelector("#action-table tbody");
        scheduleBody.innerHTML = "";
        actionBody.innerHTML = "";

        data.forEach((row) => {
            // Update the schedule table
            const tr = document.createElement("tr");
            const scheduleRow = document.createElement("tr");

            const routeCell = document.createElement("td");
            routeCell.textContent = row[0]; // Route ID
            scheduleRow.appendChild(routeCell);

            const branchCell1 = document.createElement("td");
            branchCell1.textContent = row[1] || "Main"; // Branch Letter or "Main"

            scheduleRow.appendChild(branchCell1);

            // Schedule buttons for each schedule type
            ["reduced", "holiday", "saturday", "sunday", "weekday"].forEach((scheduleType, index) => {
                const cell = document.createElement("td");
                const value = row[index + 2];

                if (value === 0) {
                    cell.textContent = "N/A";
                    cell.style.color = "#BDC3C7"; // Gray for no trips
                } else {
                    cell.textContent = value === 1 ? "No" : "Yes"; // No if frequency doesn't meet
                    cell.style.color = value === 1 ? "red" : "green";
                }

                scheduleRow.appendChild(cell);
            });

            scheduleBody.appendChild(scheduleRow);

            // Update the action table
            const actionRow = document.createElement("tr");

            const routeActionCell = document.createElement("td");
            routeActionCell.textContent = row[0]; // Route ID
            actionRow.appendChild(routeActionCell);

            const branchCell = document.createElement("td");
            branchCell.textContent = row[1] || "Main"; // Branch Letter or "Main"
            actionRow.appendChild(branchCell);

            const routeButtonCell = document.createElement("td");
            const routeButton = document.createElement("button");
            routeButton.textContent = "Show Route";
            routeButton.classList.add("route-btn");
            routeButton.dataset.routeId = row[0];
            routeButton.dataset.branchLetter = row[1];
            routeButton.addEventListener("click", () => {
                fetchRouteShape(row[0], row[1]);
            });
            routeButtonCell.appendChild(routeButton);
            actionRow.appendChild(routeButtonCell);

            const poiButtonCell = document.createElement("td");
            const poiButton = document.createElement("button");
            poiButton.textContent = `Find POIs (${row[0]}${row[1] ? ` - ${row[1]}` : ""})`;
            poiButton.classList.add("poi-btn");
            poiButton.dataset.routeId = row[0];
            poiButton.dataset.branchLetter = row[1];
            poiButton.addEventListener("click", () => {
                fetchPOIs(row[0], row[1]);
            });
            poiButtonCell.appendChild(poiButton);
            actionRow.appendChild(poiButtonCell);

            actionBody.appendChild(actionRow);
        });
    } catch (error) {
        console.error("Error fetching nearby stops:", error);
        alert("There was an error fetching the data. Please try again.");
    } finally {
        hideLoading();
    }
}

// Fetch POIs for the selected route
async function fetchPOIs(routeId, branchLetter) {
    const distance = document.getElementById("distance").value;

    try {
        const response = await axios.get("/api/pois_along_route", {
            params: {
                route_id: routeId,
                branch_letter: branchLetter,
                lat: userLat,
                lon: userLng,
                distance
            }
        });

        const pois = response.data;
        const poiList = document.getElementById("poi-list");
        poiList.innerHTML = "";

        pois.forEach((poi) => {
            const li = document.createElement("li");
            li.textContent = `${poi.name} (${poi.type}) - ${poi.distance.toFixed(2)} ft`;
            poiList.appendChild(li);
        });

        document.getElementById("poi-section").style.display = "block";
    } catch (error) {
        console.error("Error fetching POIs:", error);
        alert("Error fetching points of interest. Please try again.");
    }
}

// Fetch route shape and display on map
async function fetchRouteShape(routeId, branchLetter) {
    try {
        const response = await axios.get("/api/route_shape", {
            params: {
                route_id: routeId,
                branch_letter: branchLetter
            }
        });

        const geojsonData = response.data;

        if (routeLayer) {
            map.removeLayer(routeLayer);
        }

        routeLayer = L.geoJSON(geojsonData, {
            style: { color: "blue", weight: 4 }
        }).addTo(map);

        const bounds = routeLayer.getBounds();
        map.fitBounds(bounds);
    } catch (error) {
        console.error("Error fetching route shape:", error);
        alert("Could not load the route shape. Please try again.");
    }
}

// Handle route visualization when a button is clicked
async function handleRouteVisualization(event) {
    const routeId = event.target.dataset.routeId;
    const branchLetter = event.target.dataset.branchLetter;

    if (!routeId) {
        console.error("Route ID is missing.");
        return;
    }

    try {
        const response = await axios.get("/api/route_shape", {
            params: { route_id: routeId, branch_letter: branchLetter },
        });

        const geojsonData = response.data;

        // Remove the existing route layer if present
        if (routeLayer) {
            map.removeLayer(routeLayer);
        }

        // Add the new route layer
        routeLayer = L.geoJSON(geojsonData, {
            style: { color: "blue", weight: 4 },
        }).addTo(map);

        // Adjust the map view to fit the route
        const bounds = routeLayer.getBounds();
        map.fitBounds(bounds);
    } catch (error) {
        console.error("Error fetching route shape:", error);
        alert("Could not load the route shape. Please try again.");
    }
}

// Fetch and display POIs along the selected route
async function fetchPOIs(routeId, branchLetter) {
    try {
        const response = await axios.get("/api/pois_along_route", {
            params: {
                route_id: routeId,
                branch_letter: branchLetter,
                lat: userLat,
                lon: userLng,
                distance: document.getElementById("distance").value
            }
        });

        const pois = response.data;
        const poiList = document.getElementById("poi-list");
        poiList.innerHTML = ""; // Clear existing POIs

        pois.forEach((poi) => {
            const li = document.createElement("li");
            li.textContent = `${poi.name} (${poi.type}) - ${poi.distance.toFixed(2)} ft`;
            poiList.appendChild(li);
        });

        document.getElementById("poi-section").style.display = "block";
    } catch (error) {
        console.error("Error fetching POIs:", error);
        alert("Error fetching points of interest. Please try again.");
    }
}

// Attach click event to route buttons
document.querySelectorAll(".route-btn").forEach((button) => {
    button.addEventListener("click", (event) => {
        const routeId = event.target.dataset.routeId;
        const branchLetter = event.target.dataset.branchLetter;

        fetchRouteShape(routeId, branchLetter);
        fetchPOIs(routeId, branchLetter);
    });
});



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
