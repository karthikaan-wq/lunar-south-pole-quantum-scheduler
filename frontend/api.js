
// ---------- API CONFIGURATION ----------

// Use FastAPI only when the website is served locally
// from the backend at http://127.0.0.1:8000.
const API_ENABLED =
  (window.location.hostname === "127.0.0.1" ||
   window.location.hostname === "localhost") &&
  window.location.port === "8000";

const API_BASE_URL = "";

// ---------- API REQUEST HELPER ----------

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(API_BASE_URL + endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });

  if (!response.ok) {
    let message = `API error: ${response.status}`;

    try {
      const errorData = await response.json();
      message = Array.isArray(errorData.detail)
        ? errorData.detail.join(" ")
        : errorData.detail || message;
    } catch {
      // Keep the default error message.
    }

    throw new Error(message);
  }

  return response.json();
}

// ---------- LOAD BACKEND CATALOG ----------

async function apiGetCatalog() {
  return apiRequest("/api/catalog");
}

// ---------- GENERATE MISSION ----------

async function apiGenerateMission(config, assets) {
  const requestData = {
    config: {
      landers: config.landers,
      rovers: config.rovers,
      orbiters: config.orbiters,
      start_date: config.startDate,
      start_time: config.startTime,
      duration_days: config.durationDays,
      min_elevation_deg: config.minElevation,
      region: config.region
    },

    assets: assets.map((asset) => ({
      name: asset.name,
      type: asset.type,
      location_id: asset.locationId,
      assigned_lander:
        asset.type === "rover"
          ? asset.assignedLander
          : null
    }))
  };

  return apiRequest("/api/generate", {
    method: "POST",
    body: JSON.stringify(requestData)
  });
}

// ---------- CONVERT BACKEND RESULTS ----------

function normalizeApiResults(data) {
  const series = data.earth_series.map((point) => ({
    time: new Date(point.time + "Z"),
    elevation: point.elevation_deg,
    visible: point.visible
  }));

  function formatApiTime(value) {
    return new Date(value + "Z")
      .toISOString()
      .slice(0, 16)
      .replace("T", " ") + " UTC";
  }

  const commWindows = data.comm_windows.map((window) => {
    const point = data.earth_series.find(
      (p) => p.time === window.start
    );

    const start = new Date(window.start);
    const end = new Date(
      start.getTime() + window.duration_hours * 3600000
    );

    return {
      asset: "Mission-wide (mock)",
      start: formatApiTime(start),
      end: formatApiTime(end),
      maxElevation: point
        ? point.elevation_deg.toFixed(1)
        : "N/A"
    };
  });

  const sunWindows = data.sun_windows.map((window) => {
    const start = new Date(window.start);
    const end = new Date(
      start.getTime() + window.duration_hours * 3600000
    );

    return {
      asset: "Mission-wide (mock)",
      start: formatApiTime(start),
      end: formatApiTime(end)
    };
  });

  return {
    earthSeries: {
      "Mission-wide (mock)": series
    },
    commWindows,
    sunWindows,
    source: data.source,
    warning: data.warning
  };
}
