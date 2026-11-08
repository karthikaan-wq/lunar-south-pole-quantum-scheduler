// MOCK DATA ONLY. Nothing here comes from NASA.

const MOCK_REGIONS = [
  "Connecting Ridge",
  "Malapert Massif",
  "Shackleton Rim"
];

// A tiny seeded random number generator.
// It makes the fake data consistent every time.
function makeRng(seed) {
  let a = seed;

  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;

    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;

    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Generate fake lander and rover location candidates.
function makeCatalog() {
  const rng = makeRng(42);
  const catalog = [];

  for (let i = 1; i <= 8; i++) {
    catalog.push(makeLocation("L", i, "lander", rng));
  }

  for (let i = 1; i <= 12; i++) {
    catalog.push(makeLocation("R", i, "rover", rng));
  }

  return catalog;
}

function makeLocation(prefix, n, type, rng) {
  return {
    id: prefix + "-" + String(n).padStart(2, "0"),
    type: type,
    lat: -88 - rng() * 1.5,
    lon: 100 + rng() * 60,
    sun_pct: 30 + rng() * 60,
    earth_pct: 20 + rng() * 60
  };
}

const MOCK_CATALOG = makeCatalog();

// Two example missions for the dashboard.
const MOCK_MISSIONS = [
  {
    name: "Demo mission A",
    region: "Connecting Ridge",
    landers: 2,
    rovers: 3,
    created: "2026-11-01"
  },
  {
    name: "Demo mission B",
    region: "Malapert Massif",
    landers: 1,
    rovers: 2,
    created: "2026-11-05"
  }
];

// Convert true/false flags into [start, end) index pairs.
function findRuns(flags) {
  const runs = [];
  let start = null;

  for (let i = 0; i < flags.length; i++) {
    if (flags[i] && start === null) {
      start = i;
    }

    if (!flags[i] && start !== null) {
      runs.push([start, i]);
      start = null;
    }
  }

  if (start !== null) {
    runs.push([start, flags.length]);
  }

  return runs;
}

function formatTime(date) {
  return date.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

// Generate pretend mission results.
function makeMockResults(config, assets) {
  const stepMinutes = 30;

  const totalSteps = Math.round(
    (config.durationDays * 24 * 60) / stepMinutes
  );

  const start = new Date(
    config.startDate + "T" + config.startTime + ":00Z"
  );

  const landers = assets.filter((a) => a.type === "lander");

  const earthSeries = {};
  const commWindows = [];
  const sunWindows = [];

  landers.forEach((lander, index) => {
    const series = [];

    for (let s = 0; s < totalSteps; s++) {
      const days = (s * stepMinutes) / (60 * 24);

      const elevation =
        2 + 6.7 * Math.sin(
          (2 * Math.PI * days) / 27.3 + index
        );

      series.push({
        time: new Date(
          start.getTime() + s * stepMinutes * 60000
        ),
        elevation: elevation
      });
    }

    earthSeries[lander.name] = series;

    const usable = series.map(
      (p) => p.elevation >= config.minElevation
    );

    findRuns(usable).forEach(([a, b]) => {
      const part = series.slice(a, b);

      commWindows.push({
        asset: lander.name,
        start: formatTime(part[0].time),
        end: formatTime(part[part.length - 1].time),
        maxElevation: Math.max(
          ...part.map((p) => p.elevation)
        ).toFixed(1)
      });
    });
  });

  assets.forEach((asset, index) => {
    const sunny = [];

    for (let s = 0; s < totalSteps; s++) {
      const days = (s * stepMinutes) / (60 * 24);

      sunny.push(
        Math.sin(
          (2 * Math.PI * days) / 29.53 + index * 0.9
        ) > -0.2
      );
    }

    findRuns(sunny).forEach(([a, b]) => {
      sunWindows.push({
        asset: asset.name,
        start: formatTime(
          new Date(start.getTime() + a * stepMinutes * 60000)
        ),
        end: formatTime(
          new Date(start.getTime() + (b - 1) * stepMinutes * 60000)
        )
      });
    });
  });

  return {
    earthSeries,
    commWindows,
    sunWindows
  };
}