// Initialize map
const map = L.map("map").setView([44.9778, -93.2650], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
let loadingInterval;
let routeLayer; // Store the current route layer

// Show loading text with animation
function showLoading() {
    const loadingText = document.getElementById("loading-text");
    loadingText.style.display = "inline";
    let isBlack = true;
    loadingInterval = setInterval(() => {
        loadingText.style.color = isBlack ? "black" : "gray";
        isBlack = !isBlack;
    }, 500);
}

// Hide loading text
function hideLoading() {
    clearInterval(loadingInterval);
    const loadingText = document.getElementById("loading-text");
    loadingText.style.display = "none";
}

// Update user's location display
function updateLocationDisplay(lat, lon) {
    const locationElement = document.getElementById("user-location");
    locationElement.textContent = `Your Location: Latitude: ${lat.toFixed(6)}, Longitude: ${lon.toFixed(6)}`;
}

// Validate and parse manual coordinates
function getCoordinates() {
    const useManual = document.getElementById("manual-coordinates").checked;
    if (useManual) {
        const latInput = document.getElementById("latitude").value.trim();
        const lonInput = document.getElementById("longitude").value.trim();
        const lat = parseFloat(latInput);
        const lon = parseFloat(lonInput);

        if (
            isNaN(lat) || isNaN(lon) ||
            lat < -90 || lat > 90 || lon < -180 || lon > 180
        ) {
            alert("Parse error on the coordinates. Please enter valid decimal coordinates.");
            throw new Error("Parse error on the coordinates");
        }
        return { lat, lon };
    } else {
        return {
            lat: map.getCenter().lat,
            lon: map.getCenter().lng,
        };
    }
}

// Enable or disable manual coordinate input
document.getElementById("manual-coordinates").addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    document.getElementById("latitude").disabled = !isChecked;
    document.getElementById("longitude").disabled = !isChecked;
});

// Fetch nearby stops and update the table
async function fetchNearbyStops() {
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;

    if (!distance || !frequency) {
        alert("Please enter both walking distance and frequency!");
        return;
    }

    updateLocationDisplay(map.getCenter().lat, map.getCenter().lng);
    showLoading();

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat: map.getCenter().lat, lon: map.getCenter().lng, distance, frequency },
        });

        const rows = response.data;
        const tableBody = document.querySelector("#routes-table tbody");
        tableBody.innerHTML = ""; // Clear previous rows

        rows.forEach((row) => {
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

// Handle button clicks for route visualization
document.querySelectorAll('.route-btn').forEach(button => {
    button.addEventListener('click', async () => {
        const routeId = button.dataset.routeId;
        const branchLetter = button.dataset.branchLetter;

        // Fetch route shape from the server
        try {
            const response = await axios.get('/api/route_shape', {
                params: { route_id: routeId, branch_letter: branchLetter }
            });
            const geojsonData = response.data;

            // Remove the existing route layer if present
            if (routeLayer) {
                map.removeLayer(routeLayer);
            }

            // Add the new route layer
            routeLayer = L.geoJSON(geojsonData, {
                style: { color: 'blue', weight: 4 }
            }).addTo(map);

            // Adjust the map view to fit the route
            const bounds = routeLayer.getBounds();
            map.fitBounds(bounds);

        } catch (error) {
            console.error("Error fetching route shape:", error);
            alert("Could not load the route shape. Please try again.");
        }
    });
});
