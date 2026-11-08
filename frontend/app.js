// ---------- STATE ----------
const state = {
  config: null,
  assets: [],
  results: null
};

const el = (id) => document.getElementById(id);

// ---------- SCREEN NAVIGATION ----------
function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.hidden = s.id !== id;
  });

  window.scrollTo(0, 0);
}

// ---------- DASHBOARD ----------
el("btn-open-dashboard").onclick = () => {
  renderMissions();
  showScreen("screen-dashboard");
};

el("btn-new-mission").onclick = () => showScreen("screen-config");
el("btn-back-dashboard").onclick = () => showScreen("screen-dashboard");

function renderMissions() {
  const rows = MOCK_MISSIONS.map((m) =>
    `<tr>
      <td>${m.name}</td>
      <td>${m.region}</td>
      <td>${m.landers}</td>
      <td>${m.rovers}</td>
      <td>${m.created}</td>
    </tr>`
  ).join("");

  el("mission-table").innerHTML =
    `<tr>
      <th>Name</th>
      <th>Region</th>
      <th>Landers</th>
      <th>Rovers</th>
      <th>Created</th>
    </tr>${rows}`;
}

// ---------- MISSION CONFIGURATION ----------
el("config-region").innerHTML = MOCK_REGIONS.map(
  (r) => `<option>${r}</option>`
).join("");

el("btn-config-next").onclick = () => {
  const landers = Number(el("config-landers").value);
  const rovers = Number(el("config-rovers").value);
  const startDate = el("config-date").value;
  const startTime = el("config-time").value;
  const durationDays = Number(el("config-duration").value);
  const minElevation = Number(el("config-minel").value);

  const problems = [];

  if (!Number.isInteger(landers) || landers < 1 || landers > 5) {
    problems.push("Landers must be a whole number from 1 to 5.");
  }

  if (!Number.isInteger(rovers) || rovers < 0 || rovers > 10) {
    problems.push("Rovers must be a whole number from 0 to 10.");
  }

  if (!startDate) problems.push("Choose a start date.");
  if (!startTime) problems.push("Choose a start time.");

  if (!(durationDays >= 1 && durationDays <= 30)) {
    problems.push("Duration must be from 1 to 30 days.");
  }

  if (!(minElevation >= 0 && minElevation <= 20)) {
    problems.push("Minimum antenna elevation must be from 0 to 20 degrees.");
  }

  el("config-errors").innerHTML = problems
    .map((p) => `<li>${p}</li>`)
    .join("");

  if (problems.length > 0) return;

  state.config = {
    landers,
    rovers,
    orbiters: 0,
    startDate,
    startTime,
    durationDays,
    minElevation,
    region: el("config-region").value
  };

  buildAssetForm();
  showScreen("screen-assets");
};

// ---------- ASSET LOCATION ASSIGNMENT ----------
function buildAssetForm() {
  state.assets = [];

  for (let i = 1; i <= state.config.landers; i++) {
    state.assets.push({
      name: "Lander-" + i,
      type: "lander",
      locationId: "",
      assignedLander: ""
    });
  }

  for (let i = 1; i <= state.config.rovers; i++) {
    state.assets.push({
      name: "Rover-" + i,
      type: "rover",
      locationId: "",
      assignedLander: ""
    });
  }

  el("asset-list").innerHTML = state.assets.map((a, i) => {
    const lander = a.type === "rover"
      ? `<select data-kind="lander" data-index="${i}"></select>`
      : "";

    return `
      <div class="row">
        <label>${a.name}</label>
        <select data-kind="location" data-index="${i}"></select>
        ${lander}
      </div>
    `;
  }).join("");

  document.querySelectorAll("#asset-list select").forEach((s) => {
    s.onchange = onAssetChange;
  });

  refreshAssetOptions();
}

function onAssetChange(event) {
  const index = Number(event.target.dataset.index);

  if (event.target.dataset.kind === "location") {
    state.assets[index].locationId = event.target.value;
  } else {
    state.assets[index].assignedLander = event.target.value;
  }

  refreshAssetOptions();
}

function refreshAssetOptions() {
  const chosenIds = state.assets
    .map((a) => a.locationId)
    .filter((id) => id !== "");

  const landerNames = state.assets
    .filter((a) => a.type === "lander")
    .map((a) => a.name);

  document.querySelectorAll("#asset-list select").forEach((select) => {
    const asset = state.assets[Number(select.dataset.index)];

    if (select.dataset.kind === "location") {
      const takenByOthers = chosenIds.filter(
        (id) => id !== asset.locationId
      );

      const options = MOCK_CATALOG.filter(
        (c) =>
          c.type === asset.type &&
          !takenByOthers.includes(c.id)
      );

      select.innerHTML =
        `<option value="">Choose a location</option>` +
        options.map((c) => `
          <option value="${c.id}">
            ${c.id} | lat ${c.lat.toFixed(2)}, lon ${c.lon.toFixed(2)}
            | Sun ${c.sun_pct.toFixed(0)}%
            | Earth ${c.earth_pct.toFixed(0)}%
          </option>
        `).join("");

      select.value = asset.locationId;

    } else {
      select.innerHTML =
        `<option value="">Assigned lander</option>` +
        landerNames.map((n) => `<option>${n}</option>`).join("");

      select.value = asset.assignedLander;
    }
  });

  const complete = state.assets.every(
    (a) =>
      a.locationId !== "" &&
      (a.type === "lander" || a.assignedLander !== "")
  );

  el("btn-generate").disabled = !complete;
}

el("btn-assets-back").onclick = () => {
  showScreen("screen-config");
};

// ---------- PROCESSING SCREEN ----------
const PROCESSING_STEPS = [
  "Loading mission settings",
  "Calculating Earth geometry (mock)",
  "Checking terrain obstruction (mock)",
  "Finding communication windows (mock)",
  "Finding sunlight windows (mock)",
  "Preparing results"
];

el("btn-generate").onclick = () => {
  showScreen("screen-processing");

  let step = 0;

  el("progress-bar").style.width = "0%";

  const timer = setInterval(() => {
    el("progress-bar").style.width =
      Math.round(((step + 1) / PROCESSING_STEPS.length) * 100) + "%";

    el("progress-text").textContent = PROCESSING_STEPS[step];

    step++;

    if (step === PROCESSING_STEPS.length) {
      clearInterval(timer);

      state.results = makeMockResults(
        state.config,
        state.assets
      );

      setTimeout(() => {
        renderResults();
        showScreen("screen-results");
      }, 400);
    }
  }, 600);
};

// ---------- RESULTS ----------
function renderResults() {
  const r = state.results;
  const c = state.config;

  el("summary").innerHTML =
    `<div class="card"><b>${c.region}</b><br>region</div>` +
    `<div class="card"><b>${c.landers}</b><br>landers</div>` +
    `<div class="card"><b>${c.rovers}</b><br>rovers</div>` +
    `<div class="card"><b>${c.durationDays} days</b><br>duration</div>` +
    `<div class="card"><b>${r.commWindows.length}</b><br>communication windows</div>`;

  drawEarthChart();

  el("comm-table").innerHTML =
    `<tr>
      <th>Lander</th>
      <th>Start</th>
      <th>End</th>
      <th>Max elevation</th>
    </tr>` +
    r.commWindows.map((w) => `
      <tr>
        <td>${w.asset}</td>
        <td>${w.start}</td>
        <td>${w.end}</td>
        <td>${w.maxElevation}°</td>
      </tr>
    `).join("");

  el("sun-table").innerHTML =
    `<tr>
      <th>Asset</th>
      <th>Start</th>
      <th>End</th>
    </tr>` +
    r.sunWindows.map((w) => `
      <tr>
        <td>${w.asset}</td>
        <td>${w.start}</td>
        <td>${w.end}</td>
      </tr>
    `).join("");
}

// ---------- EARTH ELEVATION CHART ----------
function drawEarthChart() {
  const canvas = el("earth-chart");
  const ctx = canvas.getContext("2d");

  const W = canvas.width;
  const H = canvas.height;
  const pad = 40;

  ctx.clearRect(0, 0, W, H);

  const minEl = -10;
  const maxEl = 12;

  const y = (value) =>
    H - pad - ((value - minEl) / (maxEl - minEl)) * (H - 2 * pad);

  const colours = [
    "#2f5d8a",
    "#b5532f",
    "#3b8a4f",
    "#7a4fa0",
    "#a08a2f"
  ];

  ctx.strokeStyle = "#999";
  ctx.fillStyle = "#555";
  ctx.font = "12px sans-serif";

  [-10, -5, 0, 5, 10].forEach((v) => {
    ctx.beginPath();
    ctx.moveTo(pad, y(v));
    ctx.lineTo(W - 10, y(v));
    ctx.stroke();

    ctx.fillText(v + "°", 6, y(v) + 4);
  });

  // Minimum antenna elevation line.
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = "#c00";

  ctx.beginPath();
  ctx.moveTo(pad, y(state.config.minElevation));
  ctx.lineTo(W - 10, y(state.config.minElevation));
  ctx.stroke();

  ctx.setLineDash([]);

  // Draw each lander's simulated Earth elevation.
  Object.entries(state.results.earthSeries).forEach(
    ([name, series], i) => {
      ctx.strokeStyle = colours[i % colours.length];
      ctx.beginPath();

      series.forEach((p, k) => {
        const x =
          pad + (k / (series.length - 1)) * (W - pad - 10);

        if (k === 0) {
          ctx.moveTo(x, y(p.elevation));
        } else {
          ctx.lineTo(x, y(p.elevation));
        }
      });

      ctx.stroke();

      ctx.fillStyle = colours[i % colours.length];
      ctx.fillText(name, pad + 10 + i * 90, 16);
    }
  );
}

el("btn-new-from-results").onclick = () => {
  showScreen("screen-config");
};

// ---------- START THE WEBSITE ----------
showScreen("screen-landing");