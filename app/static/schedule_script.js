// Initialize map
const map = L.map("map").setView([44.9778, -93.2650], 13);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);

let loadingInterval;

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
    const lat = map.getCenter().lat;
    const lon = map.getCenter().lng;
    const distance = document.getElementById("distance").value;
    const frequency = document.getElementById("frequency").value;
    
    if (!distance || !frequency) {
        alert("Please enter both walking distance and frequency!");
        return;
    }

    // let coordinates;
    // try {
    //     coordinates = getCoordinates();
    // } catch (error) {
    //     return; // Abort if coordinates are invalid
    // }

    // const { lat, lon } = coordinates;
    updateLocationDisplay(lat, lon);
    showLoading();

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat, lon, distance, frequency },
        });

        const rows = response.data;
        const tbody = document.querySelector("#routes-table tbody");
        tbody.innerHTML = ""; // Clear previous rows

        rows.forEach((row) => {
            const tr = document.createElement("tr");
            const routeCell = document.createElement("td");
            routeCell.textContent = row.route;
            tr.appendChild(routeCell);

            ["Reduced", "Saturday", "Sunday", "Holiday", "Weekday"].forEach((sched) => {
                const cell = document.createElement("td");
                if (row.schedule_type === sched) {
                    const button = document.createElement("button");
                    button.textContent = sched;
                    button.style.backgroundColor = row.meets_frequency ? "green" : "red";
                    cell.appendChild(button);
                }
                tr.appendChild(cell);
            });

            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error("Error fetching nearby stops:", error);
    } finally {
        hideLoading();
    }
}

document.getElementById("get-stops-btn").addEventListener("click", fetchNearbyStops);
