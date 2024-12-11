// Initialize map
const map = L.map("map").setView([44.9778, -93.2650], 13); // Default location: Minneapolis
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
}).addTo(map);

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

// Hide loading text and stop animation
function hideLoading() {
    clearInterval(loadingInterval);
    const loadingText = document.getElementById("loading-text");
    loadingText.style.display = "none";
}

// Update the user's latitude and longitude on the screen
function updateLocationDisplay(lat, lon) {
    const locationElement = document.getElementById("user-location");
    locationElement.textContent = `Your Location: Latitude: ${lat.toFixed(6)}, Longitude: ${lon.toFixed(6)}`;
}

// Fetch nearby stops
async function fetchNearbyStops() {
    const lat = map.getCenter().lat;
    const lon = map.getCenter().lng;
    const distance = document.getElementById("distance").value;

    if (!distance) {
        alert("Please enter a walking distance!");
        return;
    }

    updateLocationDisplay(lat, lon); // Display user location
    showLoading(); // Show loading text

    try {
        const response = await axios.get("/api/schedule/nearby", {
            params: { lat, lon, distance },
        });

        const buttons = response.data;
        const container = document.getElementById("routes-container");
        container.innerHTML = "";

        buttons.forEach((route) => {
            const button = document.createElement("button");
            button.textContent = route;
            button.style.margin = "5px";
            container.appendChild(button);
        });
    } catch (error) {
        console.error("Error fetching nearby stops:", error);
    } finally {
        hideLoading(); // Hide loading text
    }
}

document.getElementById("get-stops-btn").addEventListener("click", fetchNearbyStops);
