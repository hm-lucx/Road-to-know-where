const urlParams = new URLSearchParams(window.location.search);
const customBackend = (urlParams.get('backend') || '').replace(/\/$/, '');
const DEFAULT_BACKEND = 'https://road-to-know-where-backend.onrender.com';
const API_BASE_URL = customBackend || DEFAULT_BACKEND;
const isGitHubPages = window.location.hostname.endsWith('.github.io');
const useMockBackend = false;

let map;
let routeLayer;
let markerLayer;

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('startButton').addEventListener('click', () => {
    document.getElementById('planner').scrollIntoView({ behavior: 'smooth' });
  });
  document.getElementById('tripForm').addEventListener('submit', handleSubmit);
});

async function handleSubmit(event) {
  event.preventDefault();
  hideError();
  setLoading(true);

  try {
    const payload = readForm();
    const response = await fetch(`${API_BASE_URL}/api/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || 'Die Route konnte nicht geplant werden.');
    }
    renderResult(data.result, data.input);
    document.getElementById('results').classList.remove('hidden');
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

function readForm() {
  const form = document.getElementById('tripForm');
  const formData = new FormData(form);
  return {
    start_location: formData.get('start_location'),
    duration_days: Number(formData.get('duration_days')),
    start_date: formData.get('start_date'),
    travel_time_per_day: Number(formData.get('travel_time_per_day')),
    fuel_type: formData.get('fuel_type'),
    fuel_consumption_l_per_100km: Number(formData.get('fuel_consumption_l_per_100km')),
    budget: formData.get('budget'),
    travel_style: formData.get('travel_style'),
    interests: [formData.get('interest')],
  };
}

function getMockResult(input) {
  const start = input.start_location || 'München';
  const stops = [
    { name: start, lat: 48.137, lng: 11.575 },
    { name: 'Augsburg', lat: 48.366, lng: 10.898 },
    { name: 'Schwäbisch Hall', lat: 49.113, lng: 9.740 },
  ];
  const distance = 210;
  const travelHours = 3.5;
  const consumption = input.fuel_consumption_l_per_100km || 6;
  const liters = Number(((distance * consumption) / 100).toFixed(1));
  const price = 1.92;

  return {
    input,
    result: {
      frontend_plan: {
        route_stops: stops,
        route_geometry: stops.map((stop) => [stop.lat, stop.lng]),
        planning_notes: [
          'Dies ist ein Demo-Plan, weil das Backend auf GitHub Pages nicht verfügbar ist.',
        ],
        route_distance_km: distance,
        route_duration_hours: travelHours,
        fuel_summary: {
          name: 'Demo-Tankstelle',
          address: 'Musterstraße 1, 86150 Augsburg',
          price,
        },
        cost_estimate: {
          fuel_consumption_l_per_100km: consumption,
          fuel_liters: liters,
          fuel_price: price,
          fuel_cost: Number((liters * price).toFixed(2)),
          estimated: true,
        },
        daily_plan: [
          {
            day: 'Tag 1',
            activities: `Start in ${start}, weiter nach Augsburg`,
            type: 'drive',
            drive_time_hours_estimated: 2,
            distance_km_estimated: 120,
            max_travel_time_hours: input.travel_time_per_day || 6,
            within_travel_limit: true,
            hint: 'Leichte Strecke zum Aufwärmen.',
          },
          {
            day: 'Tag 2',
            activities: 'Augsburg → Schwäbisch Hall',
            type: 'drive',
            drive_time_hours_estimated: 1.5,
            distance_km_estimated: 90,
            max_travel_time_hours: input.travel_time_per_day || 6,
            within_travel_limit: true,
            hint: 'Kultureller Stopp unterwegs.',
          },
        ],
        weather: {
          datengrund: 'forecast',
          temperaturspanne: { text: '18–23 °C' },
          anzahl_regentage: 1,
          wetter_risiko: 'gering',
          kritischster_tag: { ort: 'Schwäbisch Hall', grund: 'leichter Regen' },
          packempfehlung: 'Regenjacke einpacken.',
        },
        pois: [
          {
            name: 'Neue Residenz',
            location: 'Augsburg',
            description: 'Historischer Stadtpalast und Gartenanlage.',
            lat: 48.366,
            lng: 10.898,
          },
          {
            name: 'Stadtmauer',
            location: 'Schwäbisch Hall',
            description: 'Mittelalterliche Stadtmauer mit Blick über die Stadt.',
            lat: 49.113,
            lng: 9.740,
          },
        ],
      },
      telemetry: {
        agent_aufrufe: 0,
        laufzeit_sekunden: 0,
      },
    },
  };
}

function setLoading(isLoading) {
  document.getElementById('loading').classList.toggle('hidden', !isLoading);
}

function showError(message) {
  const box = document.getElementById('errorBox');
  box.textContent = message;
  box.classList.remove('hidden');
}

function hideError() {
  document.getElementById('errorBox').classList.add('hidden');
}

function renderResult(result, input) {
  const plan = result.frontend_plan || {};
  const routeStops = plan.route_stops || [];
  const cityNames = routeStops.map((stop) => stop.name).join(' → ');
  document.getElementById('resultTitle').textContent = `${input.duration_days} Tage ab ${input.start_location}`;
  document.getElementById('resultSummary').textContent = cityNames || 'Route wurde geplant.';
  renderPlanningNotes(plan.planning_notes || []);
  renderMetrics(plan, result.telemetry || {});
  renderMap(plan);
  renderDailyPlan(plan.daily_plan || []);
  renderWeather(plan.weather || {});
  renderFuel(plan.fuel_summary || {}, plan.cost_estimate || {}, plan);
  renderPois(plan.pois || []);
}

function renderPlanningNotes(notes) {
  const target = document.getElementById('planningNotes');
  if (!notes.length) {
    target.innerHTML = '';
    return;
  }
  target.innerHTML = notes
    .map((note) => `<p class="notice">${escapeHtml(note)}</p>`)
    .join('');
}

function renderMetrics(plan, telemetry) {
  const cost = plan.cost_estimate || {};
  const tokenValue = telemetry.llm_total_tokens > 0
    ? telemetry.llm_total_tokens
    : telemetry.geschaetzte_payload_tokens;
  const tokenLabel = telemetry.llm_total_tokens > 0 ? 'Tokens' : 'Tokens geschätzt';
  const metrics = [
    [Math.round(plan.route_distance_km || 0), 'km Autoroute'],
    [plan.route_duration_hours || 'n/a', 'h Fahrzeit'],
    [cost.fuel_liters || 'n/a', 'Liter Kraftstoff'],
    [cost.fuel_cost ? `${cost.fuel_cost.toFixed(2)} €` : 'n/a', 'geschätzte Kosten'],
    [telemetry.agent_aufrufe || 0, 'Agent-Aufrufe'],
    [telemetry.laufzeit_sekunden || 'n/a', 'Sekunden Laufzeit'],
    [formatNumber(tokenValue) || 'n/a', tokenLabel],
  ];
  document.getElementById('resultMetrics').innerHTML = metrics
    .map(([value, label]) => `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`)
    .join('');
}

function formatNumber(value) {
  if (value === undefined || value === null || value === '') return '';
  return Number(value).toLocaleString('de-DE');
}

function ensureMap() {
  if (map) return;
  map = L.map('map', { scrollWheelZoom: false }).setView([51, 10], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap',
  }).addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  markerLayer = L.layerGroup().addTo(map);
}

function renderMap(plan) {
  ensureMap();
  routeLayer.clearLayers();
  markerLayer.clearLayers();

  const routeGeometry = plan.route_geometry && plan.route_geometry.length
    ? plan.route_geometry
    : (plan.route_stops || []).map((stop) => [stop.lat, stop.lng]);

  const routeLine = L.polyline(routeGeometry, {
    color: '#d1495b',
    weight: 6,
    opacity: 0.95,
    lineCap: 'round',
    lineJoin: 'round',
  }).addTo(routeLayer);

  (plan.route_stops || []).forEach((stop, index) => {
    const icon = L.divIcon({
      className: '',
      html: `<div class="stop-pin ${index === 0 ? 'start' : ''}"><span>${index + 1}</span></div>`,
      iconSize: [34, 34],
      iconAnchor: [17, 34],
      popupAnchor: [0, -34],
    });
    L.marker([stop.lat, stop.lng], { icon, title: stop.name })
      .addTo(markerLayer)
      .bindPopup(`<strong>${escapeHtml(index + 1)}. ${escapeHtml(stop.name)}</strong>`);
  });

  (plan.pois || []).forEach((poi) => {
    L.marker([poi.lat, poi.lng])
      .addTo(markerLayer)
      .bindPopup(`<strong>${escapeHtml(poi.name)}</strong><br>${escapeHtml(poi.location)}<br>${escapeHtml(poi.description)}`);
  });

  if (routeGeometry.length) {
    map.fitBounds(routeLine.getBounds(), { padding: [42, 42] });
  }
  setTimeout(() => map.invalidateSize(), 150);
}

function renderDailyPlan(days) {
  document.getElementById('dailyPlan').innerHTML = days.map((day) => `
    <div class="day-item">
      <strong>${escapeHtml(day.day)}</strong>
      <p>${escapeHtml(day.activities)}</p>
      <small>${escapeHtml(formatDayMeta(day))}</small>
    </div>
  `).join('');
}

function formatDayMeta(day) {
  const typeLabel = day.type === 'drive' ? 'Fahrtetappe' : day.type === 'local_activity' ? 'Aktivität vor Ort' : 'Ruhetag';
  const driveTime = day.drive_time_hours_estimated ?? 0;
  const distance = day.distance_km_estimated ?? 0;
  const limit = day.max_travel_time_hours ?? 'n/a';
  const status = day.within_travel_limit ? 'innerhalb der Grenze' : 'kritisch';
  return `${typeLabel}: ca. ${driveTime} h, ${distance} km, Limit ${limit} h, ${status}. ${day.hint || ''}`;
}

function renderWeather(weather) {
  const temp = weather.temperaturspanne || {};
  const critical = weather.kritischster_tag || {};
  const lines = [
    ['Datenbasis', weather.datenbasis || 'n/a'],
    ['Temperatur', temp.text || 'n/a'],
    ['Regentage', weather.anzahl_regentage ?? 'n/a'],
    ['Risiko', weather.wetter_risiko || 'n/a'],
    ['Kritischer Tag', critical.ort ? `${critical.ort}: ${critical.grund}` : 'n/a'],
    ['Packempfehlung', weather.packempfehlung || 'n/a'],
  ];
  const basisHint = weather.datenbasis === 'historical_estimate'
    ? '<p class="notice">Wetterdaten sind historische Schätzwerte, weil der Zeitraum außerhalb der Forecast-Spanne liegt.</p>'
    : weather.datenbasis === 'forecast'
      ? '<p class="notice">Wetterdaten stammen aus einer aktuellen Forecast-Abfrage.</p>'
      : '<p class="notice">Wetterdaten sind ein Fallback und sollten später erneut geprüft werden.</p>';
  document.getElementById('weatherCard').innerHTML = lines
    .map(([label, value]) => `<p class="weather-line"><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</p>`)
    .join('') + basisHint;
}

function renderFuel(fuel, cost, plan) {
  const fuelCost = cost.fuel_cost ? `${cost.fuel_cost.toFixed(2)} €` : 'n/a';
  const lines = [
    ['Tankstelle', fuel.name || 'nicht verfügbar'],
    ['Adresse', fuel.address || 'n/a'],
    ['Preis', fuel.price ? `${fuel.price} €/L` : 'n/a'],
    ['Distanz', plan.route_distance_km ? `${plan.route_distance_km} km` : 'n/a'],
    ['Verbrauch', cost.fuel_liters ? `${cost.fuel_liters} l` : 'n/a'],
    ['Kosten', fuelCost],
  ];
  document.getElementById('fuelCard').innerHTML = lines
    .map(([label, value]) => `<p class="fuel-line"><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</p>`)
    .join('');
}

function renderPois(pois) {
  document.getElementById('poiGrid').innerHTML = pois.map((poi) => `
    <article class="poi-item">
      <strong>${escapeHtml(poi.name)}</strong>
      <p>${escapeHtml(poi.location)}</p>
      <p>${escapeHtml(poi.description)}</p>
    </article>
  `).join('');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
