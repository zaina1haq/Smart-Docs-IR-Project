// API base URL for backend requests
const API_BASE_URL = 'http://localhost:8000';

// Leaflet map object
let map;

// Store all map markers so we can remove them later
let markers = [];

// Wait until HTML page is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();          // Create the map
    setupEventListeners();    // Attach UI events
});

// Create and setup the Leaflet map
function initializeMap() {
    // Set default map location (Palestine) and zoom level
    map = L.map('map').setView([32.2211, 35.2544], 8);

    // Load OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
}

// Setup all UI event listeners
function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const toggleFilters = document.getElementById('toggleFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    const searchType = document.getElementById('searchType');
    const temporalFilters = document.getElementById('temporalFilters');
    const useMyLocation = document.getElementById('useMyLocation');

    // Click search button
    searchBtn.addEventListener('click', performSearch);

    // Press Enter to search
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Run autocomplete after typing (with delay)
    searchInput.addEventListener('input', debounce(handleAutocomplete, 300));

    // Hide autocomplete when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) {
            hideAutocomplete();
        }
    });

    // Show or hide advanced filters
    toggleFilters.addEventListener('click', () => {
        const isHidden = advancedFilters.style.display === 'none';
        advancedFilters.style.display = isHidden ? 'block' : 'none';
        toggleFilters.textContent = isHidden ? '⚙️ Hide Filters' : '⚙️ Advanced Filters';
    });

    // Show temporal filters only for spatiotemporal search
    searchType.addEventListener('change', (e) => {
        temporalFilters.style.display = e.target.value === 'spatiotemporal' ? 'block' : 'none';
    });

    // Use browser location
    useMyLocation.addEventListener('click', getUserLocation);
}

// Delay function execution (used for autocomplete)
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

// Handle autocomplete API request
async function handleAutocomplete(e) {
    const query = e.target.value.trim();

    // Do not search if less than 3 characters
    if (query.length < 3) {
        hideAutocomplete();
        return;
    }

    try {
        // Call backend autocomplete endpoint
        const response = await fetch(`${API_BASE_URL}/autocomplete?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        // Show results if any exist
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

// Display autocomplete suggestions
function showAutocomplete(hits) {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.innerHTML = '';

    // Create clickable suggestion for each hit
    hits.forEach(hit => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = hit._source.title;
        item.addEventListener('click', () => {
            document.getElementById('searchInput').value = hit._source.title;
            hideAutocomplete();
            performSearch();
        });
        autocompleteList.appendChild(item);
    });

    autocompleteList.classList.add('show');
}

// Hide autocomplete dropdown
function hideAutocomplete() {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.classList.remove('show');
}

// Get user current location from browser
function getUserLocation() {
    if (navigator.geolocation) {
        showLoading();
        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Fill latitude and longitude inputs
                document.getElementById('latInput').value = position.coords.latitude.toFixed(4);
                document.getElementById('lonInput').value = position.coords.longitude.toFixed(4);

                // Move map to user location
                map.setView([position.coords.latitude, position.coords.longitude], 10);
                hideLoading();
                alert('Location set successfully!');
            },
            (error) => {
                hideLoading();
                alert('Unable to get your location. Please enter manually.');
                console.error('Geolocation error:', error);
            }
        );
    } else {
        alert('Geolocation is not supported by your browser.');
    }
}

// Main search function
async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();

    // Query is required
    if (!query) {
        alert('Please enter a search query');
        return;
    }

    const searchType = document.getElementById('searchType').value;
    const lat = document.getElementById('latInput').value;
    const lon = document.getElementById('lonInput').value;
    const georef = document.getElementById('georefInput').value.trim();

    showLoading();
    hideAutocomplete();

    try {
        let url;
        let params = new URLSearchParams({ q: query });

        // Normal text search
        if (searchType === 'text') {
            if (lat && lon) {
                params.append('lat', lat);
                params.append('lon', lon);
            }
            if (georef) {
                params.append('georef', georef);
            }
            url = `${API_BASE_URL}/search?${params}`;
        }
        // Spatiotemporal search
        else {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            // Required fields check
            if (!startDate || !endDate || !georef) {
                alert('For spatiotemporal search, please provide required fields');
                hideLoading();
                return;
            }

            // Default location if none provided
            const searchLat = lat || '32.2211';
            const searchLon = lon || '35.2544';
            const distance = document.getElementById('distanceInput').value || '500km';

            params.append('start', startDate);
            params.append('end', endDate);
            params.append('lat', searchLat);
            params.append('lon', searchLon);
            params.append('distance', distance);
            params.append('georef', georef);

            url = `${API_BASE_URL}/spatiotemporal?${params}`;
        }

        // Call backend search
        const response = await fetch(url);
        const data = await response.json();

        displayResults(data);   // Show results list
        updateMap(data);       // Update markers on map
        hideLoading();
    } catch (error) {
        console.error('Search error:', error);
        hideLoading();
        alert('Search failed. Please make sure the backend is running.');
    }
}

// Display search results cards
function displayResults(data) {
    const resultsContainer = document.getElementById('results');
    const resultCount = document.getElementById('resultCount');

    // No results case
    if (!data.hits || data.hits.hits.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
        resultCount.textContent = '';
        return;
    }

    const hits = data.hits.hits;
    resultCount.textContent = `${hits.length} results found`;

    // Build HTML for each result
    resultsContainer.innerHTML = hits.map((hit, index) => {
        const source = hit._source;
        const score = hit._score.toFixed(2);

        const date = source.date ? new Date(source.date).toLocaleDateString() : 'N/A';

        const authors = source.authors && source.authors.length > 0
            ? source.authors.map(a => `${a.first} ${a.last}`).join(', ')
            : 'Unknown';

        const location = source.geopoint
            ? `${source.geopoint.lat.toFixed(4)}, ${source.geopoint.lon.toFixed(4)}`
            : 'N/A';

        const fullContent = source.content || 'No content available';
        const truncatedContent = fullContent.length > 300 ? fullContent.substring(0, 300) + '...' : fullContent;
        const needsReadMore = fullContent.length > 300;

        const georeferences = source.georeferences && source.georeferences.length > 0
            ? source.georeferences.map(g =>
                `<span class="tag georeference">📍 ${g.name}</span>`
              ).join('')
            : '';

        const temporalExpressions = source.temporalExpressions && source.temporalExpressions.length > 0
            ? source.temporalExpressions.slice(0, 3).map(t =>
                `<span class="tag temporal">📅 ${t.text}</span>`
              ).join('')
            : '';

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
                    <span class="content-full" style="display: none;">${fullContent}</span>
                </div>
                ${needsReadMore ? `<button class="read-more-btn" onclick="toggleReadMore(${index})">Read More</button>` : ''}
                <div class="result-tags">
                    ${georeferences}
                    ${temporalExpressions}
                </div>
            </div>
        `;
    }).join('');
}

// Toggle full content visibility
function toggleReadMore(index) {
    const contentDiv = document.getElementById(`content-${index}`);
    const preview = contentDiv.querySelector('.content-preview');
    const full = contentDiv.querySelector('.content-full');
    const button = contentDiv.parentElement.querySelector('.read-more-btn');

    if (full.style.display === 'none') {
        preview.style.display = 'none';
        full.style.display = 'inline';
        button.textContent = 'Read Less';
    } else {
        preview.style.display = 'inline';
        full.style.display = 'none';
        button.textContent = 'Read More';
    }
}

// Update map markers based on results
function updateMap(data) {
    // Remove old markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    if (!data.hits || data.hits.hits.length === 0) return;

    const bounds = [];

    data.hits.hits.forEach((hit) => {
        const source = hit._source;

        // Add marker only if geopoint exists
        if (source.geopoint && source.geopoint.lat && source.geopoint.lon) {
            const lat = source.geopoint.lat;
            const lon = source.geopoint.lon;

            const marker = L.marker([lat, lon]).addTo(map);

            const popupContent = `
                <div class="popup-title">${source.title || 'Untitled'}</div>
                <div class="popup-info">
                    📅 ${source.date ? new Date(source.date).toLocaleDateString() : 'N/A'}<br>
                    📊 Score: ${hit._score.toFixed(2)}
                </div>
            `;

            marker.bindPopup(popupContent);
            markers.push(marker);
            bounds.push([lat, lon]);
        }
    });

    // Zoom map to fit all markers
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Show loading spinner
function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'block';
}

// Hide loading spinner
function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}
