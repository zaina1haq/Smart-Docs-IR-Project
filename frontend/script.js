// API Configuration
//(Flask API)
const API_BASE_URL = 'http://localhost:8000';

//Map state Leaflet map instance
let map;

// Keep track of markers so we can clear on new searches
let markers = [];
//after full load
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    setupEventListeners();
});

function initializeMap() {
    // Default view centered on Palestine area for map
    map = L.map('map').setView([32.2211, 35.2544], 8);

    // OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
}

// Event listeners setup

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const toggleFilters = document.getElementById('toggleFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    const searchType = document.getElementById('searchType');
    const temporalFilters = document.getElementById('temporalFilters');
    const useMyLocation = document.getElementById('useMyLocation');

    // Manual search trigger
    searchBtn.addEventListener('click', performSearch);

    // Allow pressing Enter to search
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Autocomplete (debounced to reduce API calls)
    searchInput.addEventListener('input', debounce(handleAutocomplete, 300));

    // Hide autocomplete when clicking outside search box
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) {
            hideAutocomplete();
        }
    });

    // Toggle advanced filters UI
    toggleFilters.addEventListener('click', () => {
        const isHidden = advancedFilters.style.display === 'none';
        advancedFilters.style.display = isHidden ? 'block' : 'none';
        toggleFilters.textContent = isHidden ? '⚙️ Hide Filters' : '⚙️ Advanced Filters';
    });

    // Show temporal filters only for spatiotemporal search
    searchType.addEventListener('change', (e) => {
        temporalFilters.style.display =
            e.target.value === 'spatiotemporal' ? 'block' : 'none';
    });

    // Auto-fill lat/lon using browser geolocation use my location
    useMyLocation.addEventListener('click', getUserLocation);
}

// Utility: debounce after user stops the action


// Prevents firing a function too often //used for autocomplete//
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Autocomplete logic

async function handleAutocomplete(e) {
    const query = e.target.value.trim();

    // Backend autocomplete requires at least 3 chars
    if (query.length < 3) {
        hideAutocomplete();
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE_URL}/autocomplete?q=${encodeURIComponent(query)}`
        );
        const data = await response.json();

        // Elasticsearch-style response
        if (data.hits && data.hits.hits.length > 0) {
            showAutocomplete(data.hits.hits);
        } else {
            hideAutocomplete();
        }
    } catch (error) {
        console.error('Autocomplete error:', error);
        hideAutocomplete();
    }
}

// show autocomplete suggestions
function showAutocomplete(hits) {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.innerHTML = '';
//takes those results and builds the dropdown list
    hits.forEach(hit => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = hit._source.title;

        // Clicking suggestion fills input and searches
        item.addEventListener('click', () => {
            document.getElementById('searchInput').value = hit._source.title;
            hideAutocomplete();
            performSearch();
        });

        autocompleteList.appendChild(item);
    });

    autocompleteList.classList.add('show');
}

function hideAutocomplete() {
    document.getElementById('autocompleteList').classList.remove('show');
}

// Geolocation
function getUserLocation() {
    // If the browser does not support location feature, stop here
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser.');
        return;
    }

    // Show loading spinner while we are waiting for the location
    showLoading();

    // Ask the browser for the current location
    navigator.geolocation.getCurrentPosition(
        (position) => {
            // Put the user's latitude and longitude into the input fields
            document.getElementById('latInput').value =
                position.coords.latitude.toFixed(4);
            document.getElementById('lonInput').value =
                position.coords.longitude.toFixed(4);

            // Move the map to the user's location and zoom in a bit
            map.setView(
                [position.coords.latitude, position.coords.longitude],
                10
            );

            // Hide loading spinner and show success message
            hideLoading();
            alert('Location set successfully!');
        },
        (error) => {
            // If location fails, hide spinner and tell user to enter manually
            hideLoading();
            alert('Unable to get your location. Please enter manually.');
            console.error('Geolocation error:', error);
        }
    );
}


// Main search logic

async function performSearch() {
    // Read the search query text from the input
    const query = document.getElementById('searchInput').value.trim();

    // Query is required (we do not send request if it is empty)
    if (!query) {
        alert('Please enter a search query');
        return;
    }

    // Read selected search type (text or spatiotemporal)
    const searchType = document.getElementById('searchType').value;

    // Read optional filters from inputs
    const lat = document.getElementById('latInput').value;
    const lon = document.getElementById('lonInput').value;
    const georef = document.getElementById('georefInput').value.trim();

    // Show spinner and close autocomplete list
    showLoading();
    hideAutocomplete();

    try {
        let url;

        // Build query parameters starting with the required q
        let params = new URLSearchParams({ q: query });

        // =========================
        // 1) TEXT SEARCH (/search)
        // =========================
        if (searchType === 'text') {
            // If user provided lat/lon, send them to backend for location boosting
            if (lat && lon) {
                params.append('lat', lat);
                params.append('lon', lon);
            }

            // If user provided a place name filter/boost, send it too
            if (georef) {
                params.append('georef', georef);
            }

            // Build final URL for backend
            url = `${API_BASE_URL}/search?${params}`;
        }

        // ======================================
        // 2) SPATIOTEMPORAL SEARCH (/spatiotemporal)
        // ======================================
        else {
            // Read required date range fields
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            // For spatiotemporal search, we require start, end, and place name
            if (!startDate || !endDate || !georef) {
                alert(
                    'For spatiotemporal search, please provide:\n' +
                    '- Start Date\n- End Date\n- Place name'
                );
                hideLoading();
                return;
            }

            // If user did not enter lat/lon, use default center point
            const searchLat = lat || '32.2211';
            const searchLon = lon || '35.2544';

            // Distance has a default value if empty
            const distance =
                document.getElementById('distanceInput').value || '500km';

            // Add spatiotemporal parameters to the request
            params.append('start', startDate);
            params.append('end', endDate);
            params.append('lat', searchLat);
            params.append('lon', searchLon);
            params.append('distance', distance);
            params.append('georef', georef);

            // Build final URL for backend
            url = `${API_BASE_URL}/spatiotemporal?${params}`;
        }

        // Call backend and parse JSON response
        const response = await fetch(url);
        const data = await response.json();

        // Update UI with results and map markers
        displayResults(data);
        updateMap(data);

        // Done loading
        hideLoading();
    } catch (error) {
        // If request fails, hide spinner and show error message
        console.error('Search error:', error);
        hideLoading();
        alert('Search failed. Please make sure the backend is running.');
    }
}

// Results rendering
function displayResults(data) {
    // Where we will show the result cards
    const resultsContainer = document.getElementById('results');

    // Small text that shows how many results we got
    const resultCount = document.getElementById('resultCount');

    // If backend returned no hits, show "No results"
    if (!data.hits || data.hits.hits.length === 0) {
        resultsContainer.innerHTML =
            '<div class="empty-state"><p>No results found</p></div>';
        resultCount.textContent = '';
        return;
    }

    // Elasticsearch-style results array
    const hits = data.hits.hits;

    // Show number of results on the page
    resultCount.textContent = `${hits.length} results found`;

    // Convert each hit into a result card HTML
    resultsContainer.innerHTML = hits.map((hit, index) => {
        const source = hit._source;           // document fields (title, content, date, ...)
        const score = hit._score.toFixed(2);  // ranking score from ES

        // Format document date (if missing, show N/A)
        const date = source.date
            ? new Date(source.date).toLocaleDateString()
            : 'N/A';

        // Combine authors into one string (if missing, show Unknown)
        const authors =
            source.authors && source.authors.length > 0
                ? source.authors.map(a => `${a.first} ${a.last}`).join(', ')
                : 'Unknown';

        // Show geopoint if exists (lat/lon), otherwise N/A
        const location = source.geopoint
            ? `${source.geopoint.lat.toFixed(4)}, ${source.geopoint.lon.toFixed(4)}`
            : 'N/A';

        // Show only first 300 chars, and allow "Read More" if content is long
        const fullContent = source.content || 'No content available';
        const truncatedContent =
            fullContent.length > 300
                ? fullContent.substring(0, 300) + '...'
                : fullContent;
        const needsReadMore = fullContent.length > 300;

        // Build georeference tags if they exist
        const georeferences =
            source.georeferences && source.georeferences.length > 0
                ? source.georeferences
                      .map(g => `<span class="tag georeference">📍 ${g.name}</span>`)
                      .join('')
                : '';

        // Build temporal tags  if they exist (show max 3)
        const temporalExpressions =
            source.temporalExpressions && source.temporalExpressions.length > 0
                ? source.temporalExpressions
                      .slice(0, 3)
                      .map(t => `<span class="tag temporal">📅 ${t.text}</span>`)
                      .join('')
                : '';

        // Return one result card HTML
        return `
            <div class="result-card">
                <span class="result-score">Score: ${score}</span>
                <h3>${source.title || 'Untitled Document'}</h3>

                <div class="result-meta">
                    <span>👤 ${authors}</span>
                    <span>📅 ${date}</span>
                    <span>📍 ${location}</span>
                </div>

                <div class="result-content" id="content-${index}">
                    <span class="content-preview">${truncatedContent}</span>
                    <span class="content-full" style="display: none;">
                        ${fullContent}
                    </span>
                </div>

                ${needsReadMore
                    ? `<button class="read-more-btn"
                        onclick="toggleReadMore(${index})">Read More</button>`
                    : ''}

                <div class="result-tags">
                    ${georeferences}
                    ${temporalExpressions}
                </div>
            </div>
        `;
    }).join('');
}
// Toggle content expansion (Read More / Read Less)
function toggleReadMore(index) {
    // Get the content container for this result card
    const contentDiv = document.getElementById(`content-${index}`);

    // Short preview text (first 300 chars)
    const preview = contentDiv.querySelector('.content-preview');

    // Full content text (hidden by default)
    const full = contentDiv.querySelector('.content-full');

    // The button under the card (Read More / Read Less)
    const button =
        contentDiv.parentElement.querySelector('.read-more-btn');

    // If full content is hidden, show it
    if (full.style.display === 'none') {
        preview.style.display = 'none';
        full.style.display = 'inline';
        button.textContent = 'Read Less';
    }
    // Otherwise, go back to preview
    else {
        preview.style.display = 'inline';
        full.style.display = 'none';
        button.textContent = 'Read More';
    }
}

// ==============================
// Map update
// ==============================

function updateMap(data) {
    // Remove old markers from the map (so new search does not mix with old search)
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    // If there are no results, do nothing
    if (!data.hits || data.hits.hits.length === 0) return;

    // Collect marker positions so we can zoom to them later
    const bounds = [];

    data.hits.hits.forEach(hit => {
        const source = hit._source;

        // Add marker only if the document has a valid geopoint (lat/lon)
        if (source.geopoint && source.geopoint.lat && source.geopoint.lon) {
            const lat = source.geopoint.lat;
            const lon = source.geopoint.lon;

            // Create marker and add it to the map
            const marker = L.marker([lat, lon]).addTo(map);

            // Popup shows basic document info when user clicks marker
            marker.bindPopup(`
                <div class="popup-title">${source.title || 'Untitled'}</div>
                <div class="popup-info">
                    📅 ${source.date
                        ? new Date(source.date).toLocaleDateString()
                        : 'N/A'}<br>
                    📊 Score: ${hit._score.toFixed(2)}
                </div>
            `);

            // Save marker so we can remove it on the next search
            markers.push(marker);

            // Save marker position for map zoom fitting
            bounds.push([lat, lon]);
        }
    });

    // If we added at least one marker,allow zoom map to show all of them
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

function showLoading() {
    // Show spinner while waiting for backend response
    document.getElementById('loadingSpinner').style.display = 'block';
}

function hideLoading() {
    // Hide spinner after results are ready
    document.getElementById('loadingSpinner').style.display = 'none';
}
