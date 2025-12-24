// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// Map initialization
let map;
let markers = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    setupEventListeners();
});

// Initialize Leaflet map
function initializeMap() {
    map = L.map('map').setView([32.2211, 35.2544], 8);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
}

// Setup all event listeners
function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const toggleFilters = document.getElementById('toggleFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    const searchType = document.getElementById('searchType');
    const temporalFilters = document.getElementById('temporalFilters');
    const useMyLocation = document.getElementById('useMyLocation');

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    searchInput.addEventListener('input', debounce(handleAutocomplete, 300));
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) {
            hideAutocomplete();
        }
    });

    toggleFilters.addEventListener('click', () => {
        const isHidden = advancedFilters.style.display === 'none';
        advancedFilters.style.display = isHidden ? 'block' : 'none';
        toggleFilters.textContent = isHidden ? '⚙️ Hide Filters' : '⚙️ Advanced Filters';
    });

    searchType.addEventListener('change', (e) => {
        temporalFilters.style.display = e.target.value === 'spatiotemporal' ? 'block' : 'none';
    });

    useMyLocation.addEventListener('click', getUserLocation);
}

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

async function handleAutocomplete(e) {
    const query = e.target.value.trim();
    
    if (query.length < 3) {
        hideAutocomplete();
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/autocomplete?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
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

function showAutocomplete(hits) {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.innerHTML = '';
    
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

function hideAutocomplete() {
    const autocompleteList = document.getElementById('autocompleteList');
    autocompleteList.classList.remove('show');
}

function getUserLocation() {
    if (navigator.geolocation) {
        showLoading();
        navigator.geolocation.getCurrentPosition(
            (position) => {
                document.getElementById('latInput').value = position.coords.latitude.toFixed(4);
                document.getElementById('lonInput').value = position.coords.longitude.toFixed(4);
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

async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();
    
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

        if (searchType === 'text') {
            if (lat && lon) {
                params.append('lat', lat);
                params.append('lon', lon);
            }
            if (georef) {
                params.append('georef', georef);
            }
            url = `${API_BASE_URL}/search?${params}`;
        } else {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            if (!startDate || !endDate || !georef) {
                alert('For spatiotemporal search, please provide:\n- Start Date (required)\n- End Date (required)\n- Georeference/Place Name (required)\n\nNote: Location (lat/lon) is optional');
                hideLoading();
                return;
            }

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

        const response = await fetch(url);
        const data = await response.json();

        displayResults(data);
        updateMap(data);
        hideLoading();
    } catch (error) {
        console.error('Search error:', error);
        hideLoading();
        alert('Search failed. Please make sure the backend is running.');
    }
}

function displayResults(data) {
    const resultsContainer = document.getElementById('results');
    const resultCount = document.getElementById('resultCount');
    
    if (!data.hits || data.hits.hits.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
        resultCount.textContent = '';
        return;
    }

    const hits = data.hits.hits;
    resultCount.textContent = `${hits.length} results found`;

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

function updateMap(data) {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    if (!data.hits || data.hits.hits.length === 0) return;

    const bounds = [];

    data.hits.hits.forEach((hit, index) => {
        const source = hit._source;
        
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

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}