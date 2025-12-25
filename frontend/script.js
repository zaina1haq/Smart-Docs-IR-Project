// Backend API base URL
const API_BASE_URL = 'http://localhost:8000';

// Leaflet map instance
let map;
let markers = [];

// Start app after the HTML is ready
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    setupEventListeners();
});

// Create and show the Leaflet map
function initializeMap() {
    // Default view (Palestine area)
    map = L.map('map').setView([32.2211, 35.2544], 8);

    // Load OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
}

// Link buttons/inputs to functions
function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const toggleFilters = document.getElementById('toggleFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    const searchType = document.getElementById('searchType');
    const temporalFilters = document.getElementById('temporalFilters');
    const useMyLocation = document.getElementById('useMyLocation');

    // Search button click
    searchBtn.addEventListener('click', performSearch);

    // Search when user presses Enter
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Autocomplete while typing (with debounce to reduce API calls)
    searchInput.addEventListener('input', debounce(handleAutocomplete, 300));

    // Close autocomplete if user clicks outside search box
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) {
            hideAutocomplete();
        }
    });

    // Show/hide advanced filters area
    toggleFilters.addEventListener('click', () => {
        const isHidden = advancedFilters.style.display === 'none';
        advancedFilters.style.display = isHidden ? 'block' : 'none';
        toggleFilters.textContent = isHidden ? '⚙️ Hide Filters' : '⚙️ Advanced Filters';
    });

    // Show date filters only for spatiotemporal search
    searchType.addEventListener('change', (e) => {
        temporalFilters.style.display =
            e.target.value === 'spatiotemporal' ? 'block' : 'none';
    });

    // Get user current location
    useMyLocation.addEventListener('click', getUserLocation);
}

// Delay function calls until user stops typing
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

// Call backend autocomplete endpoint
async function handleAutocomplete(e) {
    const query = e.target.value.trim();

    // Backend needs at least 3 chars for autocomplete
    if (query.length < 3) {
        hideAutocomplete();
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE_URL}/autocomplete?q=${encodeURIComponent(query)}`
        );
        const data = await response.json();

        // Show suggestions only if we have hits
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

// Render autocomplete suggestions
function showAutocomplete(hits) {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.innerHTML = '';

    hits.forEach(hit => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = hit._source.title;

        // Click suggestion -> fill input then run search
        item.addEventListener('click', () => {
            document.getElementById('searchInput').value = hit._source.title;
            hideAutocomplete();
            performSearch();
        });

        autocompleteList.appendChild(item);
    });

    autocompleteList.classList.add('show');
}

// Hide autocomplete list
function hideAutocomplete() {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.classList.remove('show');
}

// Get lat/lon from browser geolocation
function getUserLocation() {
    if (navigator.geolocation) {
        showLoading();

        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Fill inputs with current location
                document.getElementById('latInput').value =
                    position.coords.latitude.toFixed(4);
                document.getElementById('lonInput').value =
                    position.coords.longitude.toFixed(4);

                // Move the map to user location
                map.setView(
                    [position.coords.latitude, position.coords.longitude],
                    10
                );

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

// Build request URL and call backend search endpoint
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

        // Text search endpoint
        if (searchType === 'text') {
            // Optional location boost
            if (lat && lon) {
                params.append('lat', lat);
                params.append('lon', lon);
            }

            // Optional georef boost/filter
            if (georef) {
                params.append('georef', georef);
            }

            url = `${API_BASE_URL}/search?${params}`;
        } else {
            // Spatiotemporal search endpoint
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            // Required fields for spatiotemporal mode
            if (!startDate || !endDate || !georef) {
                alert(
                    'For spatiotemporal search, please provide:\n' +
                    '- Start Date\n- End Date\n- Georeference/Place Name'
                );
                hideLoading();
                return;
            }

            // Use default location if user did not provide one
            const searchLat = lat || '32.2211';
            const searchLon = lon || '35.2544';
            const distance = document.getElementById('distanceInput').value || '500km';

            // Add spatiotemporal parameters
            params.append('start', startDate);
            params.append('end', endDate);
            params.append('lat', searchLat);
            params.append('lon', searchLon);
            params.append('distance', distance);
            params.append('georef', georef);

            url = `${API_BASE_URL}/spatiotemporal?${params}`;
        }

        // Fetch results from backend
        const response = await fetch(url);
        const data = await response.json();

        // Update UI
        displayResults(data);
        updateMap(data);

        hideLoading();
    } catch (error) {
        console.error('Search e
