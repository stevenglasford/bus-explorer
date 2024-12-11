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

// Fetch nearby stops and update the table
async function fetchNearbyStops() {
    const lat = map.getCenter().lat;
    const lon = map.getCenter().lng;
    const distance = document.getElementById("distance").value;

    if (!distance) {
        alert("Please enter a walking distance!");
        return;
    }

    updateLocationDisplay(lat, lon);
    showLoading();

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat, lon, distance },
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
                if (row[sched]) {
                    const button = document.createElement("button");
                    button.textContent = sched;
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
