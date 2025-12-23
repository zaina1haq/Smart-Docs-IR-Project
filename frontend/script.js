const results = document.getElementById("results");
const modal = document.getElementById("analytics-modal");
const modalTitle = document.getElementById("modal-title");
const modalBody = document.getElementById("modal-body");

const queryInput = document.getElementById("query");
const autocompleteBox = document.getElementById("autocomplete-box");

let autocompleteTimer = null;

/* =========================
   SPLASH
   ========================= */
window.onload = () => {
  setTimeout(() => {
    document.getElementById("splash").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
  }, 2200);
};

/* =========================
   AUTOCOMPLETE (AFTER 3 CHARS)
   ========================= */
queryInput.addEventListener("input", () => {
  const q = queryInput.value.trim();

  clearTimeout(autocompleteTimer);

  if (q.length < 3) {
    autocompleteBox.classList.add("hidden");
    autocompleteBox.innerHTML = "";
    return;
  }

  autocompleteTimer = setTimeout(async () => {
    try {
      const res = await fetch(
        `http://localhost:5000/api/autocomplete?q=${encodeURIComponent(q)}&size=10`
      );
      const data = await res.json();

      if (!data.suggestions || data.suggestions.length === 0) {
        autocompleteBox.classList.add("hidden");
        return;
      }

      autocompleteBox.innerHTML = "";
      data.suggestions.forEach(item => {
        const div = document.createElement("div");
        div.innerHTML = item.highlight?.[0] || item.title;
        div.onclick = () => {
          queryInput.value = item.title;
          autocompleteBox.classList.add("hidden");
          search(); // auto-search on select
        };
        autocompleteBox.appendChild(div);
      });

      autocompleteBox.classList.remove("hidden");
    } catch (e) {
      autocompleteBox.classList.add("hidden");
    }
  }, 250); // debounce
});

/* Hide autocomplete when clicking outside */
document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrapper")) {
    autocompleteBox.classList.add("hidden");
  }
});

/* =========================
   SEARCH — 100% MATCH BACKEND
   ========================= */
async function search() {
  results.innerHTML = "";

  const query = queryInput.value.trim();
  const temporalExpression = document.getElementById("date").value;
  const dateFrom = document.getElementById("date-from").value;
  const dateTo = document.getElementById("date-to").value;
  const georef = document.getElementById("georef").value.trim();
  const lat = document.getElementById("lat").value.trim();
  const lon = document.getElementById("lon").value.trim();
  const radius = document.getElementById("radius")?.value;

  if (!query && !temporalExpression && !georef && !lat && !lon) {
    results.innerHTML = "<p>Please enter at least one search field.</p>";
    return;
  }

  const body = {
    query: query || "*",
    temporal_expression: temporalExpression || null,
    georeference: georef || null,
    size: 10,
    use_semantic: true
  };

  if (dateFrom) body.date_from = dateFrom;
  if (dateTo) body.date_to = dateTo;
  if (lat) body.lat = parseFloat(lat);
  if (lon) body.lon = parseFloat(lon);
  if (radius) body.radius_km = parseFloat(radius);

  try {
    const response = await fetch("http://localhost:5000/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    const data = await response.json();

    if (!data.results || data.results.length === 0) {
      results.innerHTML = "<p>No documents found.</p>";
      return;
    }

    data.results.forEach(doc => {
      results.innerHTML += `
        <div class="result">
          <h4>${doc.title || "Untitled Document"}</h4>
          <p>${doc.content_snippet || ""}</p>
          <small>
            📅 ${doc.date || "Unknown date"}<br/>
            🌍 ${(doc.places || []).join(", ") || "N/A"}
          </small>
        </div>
      `;
    });

  } catch (err) {
    console.error(err);
    results.innerHTML = "<p>Search failed. Backend not responding.</p>";
  }
}

/* =========================
   ANALYTICS
   ========================= */
async function openAnalytics(type) {
  modal.classList.remove("hidden");

  let endpoint = "";
  if (type === "countries") endpoint = "/api/analytics/top-georeferences";
  if (type === "time") endpoint = "/api/analytics/temporal-distribution";

  modalTitle.innerText =
    type === "countries" ? "Top Geo References" :
    type === "time" ? "Documents Over Time" :
    "Analytics";

  try {
    const res = await fetch(`http://localhost:5000${endpoint}`);
    const data = await res.json();
    modalBody.innerText = JSON.stringify(data, null, 2);
  } catch {
    modalBody.innerText = "Failed to load analytics.";
  }
}

function closeModal() {
  modal.classList.add("hidden");
}
