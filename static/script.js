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
    const response = await fetch('/api/plan', {
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
  renderMetrics(plan, result.telemetry || {});
  renderMap(plan);
  renderDailyPlan(plan.daily_plan || []);
  renderWeather(plan.weather || {});
  renderFuel(plan.fuel_summary || {}, plan.cost_estimate || {}, plan);
  renderPois(plan.pois || []);
}

function renderMetrics(plan, telemetry) {
  const cost = plan.cost_estimate || {};
  const metrics = [
    [Math.round(plan.route_distance_km || 0), 'km Autoroute'],
    [plan.route_duration_hours || 'n/a', 'h Fahrzeit'],
    [cost.fuel_liters || 'n/a', 'Liter Kraftstoff'],
    [cost.fuel_cost ? `${cost.fuel_cost.toFixed(2)} €` : 'n/a', 'geschätzte Kosten'],
    [telemetry.agent_aufrufe || 0, 'Agent-Aufrufe'],
    [telemetry.laufzeit_sekunden || 'n/a', 'Sekunden Laufzeit'],
  ];
  document.getElementById('resultMetrics').innerHTML = metrics
    .map(([value, label]) => `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`)
    .join('');
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
    </div>
  `).join('');
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
  document.getElementById('weatherCard').innerHTML = lines
    .map(([label, value]) => `<p class="weather-line"><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</p>`)
    .join('');
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
