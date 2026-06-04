#!/usr/bin/env python3
"""Erzeugt aus Reiseparametern eine Route mit POI für Deutschland
und schreibt eine HTML-Datei mit Leaflet- und OpenStreetMap-Darstellung."""

import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

THEME_DESTINATIONS = {
    "städte": [
        {"name": "Berlin", "lat": 52.5200, "lng": 13.4050, "poi": [
            {"name": "Brandenburger Tor", "description": "Symbol der deutschen Einheit."},
            {"name": "Museumsinsel", "description": "Weltkulturerbe mit fünf Museen."}
        ]},
        {"name": "München", "lat": 48.1351, "lng": 11.5820, "poi": [
            {"name": "Marienplatz", "description": "Historischer Marktplatz und Rathaus."},
            {"name": "Englischer Garten", "description": "Großer innerstädtischer Park."}
        ]},
        {"name": "Hamburg", "lat": 53.5511, "lng": 9.9937, "poi": [
            {"name": "Speicherstadt", "description": "Weltgrößtes zusammenhängendes Lagerhausviertel."},
            {"name": "Elbphilharmonie", "description": "Moderne Konzerthalle in der Hafencity."}
        ]},
        {"name": "Köln", "lat": 50.9375, "lng": 6.9603, "poi": [
            {"name": "Kölner Dom", "description": "Gotische Kathedrale und UNESCO-Weltkulturerbe."},
            {"name": "Rheinpromenade", "description": "Spazierwege am Fluss mit Blick auf die Altstadt."}
        ]},
        {"name": "Dresden", "lat": 51.0504, "lng": 13.7373, "poi": [
            {"name": "Zwinger", "description": "Barocke Schlossanlage mit Museen."},
            {"name": "Frauenkirche", "description": "Wiederaufgebaute Landmarke der Stadt."}
        ]},
    ],
    "berge": [
        {"name": "Garmisch-Partenkirchen", "lat": 47.4925, "lng": 11.0950, "poi": [
            {"name": "Zugspitze", "description": "Deutschlands höchster Berg."},
            {"name": "Partnachklamm", "description": "Beeindruckende Schlucht in den Alpen."}
        ]},
        {"name": "Berchtesgaden", "lat": 47.6308, "lng": 13.0021, "poi": [
            {"name": "Königssee", "description": "Klares Gebirgssee-Wasser in alpiner Landschaft."},
            {"name": "Watzmannblick", "description": "Panoramablick auf den Watzmann."}
        ]},
        {"name": "Feldberg (Schwarzwald)", "lat": 47.8722, "lng": 8.0045, "poi": [
            {"name": "Feldberg Gipfel", "description": "Höchster Berg im Schwarzwald."},
            {"name": "Titisee", "description": "Beliebter See für Wanderungen und Erholung."}
        ]},
        {"name": "Harz", "lat": 51.7431, "lng": 10.6177, "poi": [
            {"name": "Brocken", "description": "Höchster Gipfel im Harz."},
            {"name": "Wernigerode Altstadt", "description": "Fachwerk und mittelalterliches Ambiente."}
        ]},
    ],
    "besondere bauten": [
        {"name": "Neuschwanstein", "lat": 47.5576, "lng": 10.7498, "poi": [
            {"name": "Schloss Neuschwanstein", "description": "Märchenschloss von König Ludwig II."}
        ]},
        {"name": "Heidelberg", "lat": 49.3988, "lng": 8.6724, "poi": [
            {"name": "Heidelberger Schloss", "description": "Ruine mit Blick über die Stadt."}
        ]},
        {"name": "Kölner Dom", "lat": 50.9413, "lng": 6.9583, "poi": [
            {"name": "Kölner Dom", "description": "Beeindruckende gotische Kathedrale."}
        ]},
        {"name": "Schloss Sanssouci", "lat": 52.4025, "lng": 13.0358, "poi": [
            {"name": "Schloss Sanssouci", "description": "Preußisches Rokoko-Schloss in Potsdam."}
        ]},
    ],
    "camping": [
        {"name": "Mecklenburger Seenplatte", "lat": 53.5235, "lng": 12.7259, "poi": [
            {"name": "Müritz", "description": "Größter Binnensee Deutschlands."}
        ]},
        {"name": "Eifel", "lat": 50.2700, "lng": 6.6050, "poi": [
            {"name": "Nationalpark Eifel", "description": "Wälder, Seen und Naturcamping."}
        ]},
        {"name": "Sächsische Schweiz", "lat": 50.9167, "lng": 14.1667, "poi": [
            {"name": "Basteibrücke", "description": "Felsbrücke mit Ausblick über Elbsandsteingebirge."}
        ]},
        {"name": "Bayerische Seen", "lat": 47.6679, "lng": 11.4504, "poi": [
            {"name": "Chiemsee", "description": "Bayerisches Meer mit Inseln und Natur."}
        ]},
    ],
}

KNOWN_START_LOCATIONS = {
    "berlin": {"lat": 52.5200, "lng": 13.4050},
    "hamburg": {"lat": 53.5511, "lng": 9.9937},
    "münchen": {"lat": 48.1351, "lng": 11.5820},
    "koeln": {"lat": 50.9375, "lng": 6.9603},
    "köln": {"lat": 50.9375, "lng": 6.9603},
    "frankfurt": {"lat": 50.1109, "lng": 8.6821},
    "stuttgart": {"lat": 48.7758, "lng": 9.1829},
    "dresden": {"lat": 51.0504, "lng": 13.7373},
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Deine Route mit interaktiver Karte</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
    #wrapper { display: grid; grid-template-columns: 1fr; gap: 20px; }
    #map { height: 60vh; width: 100%%; }
    #panel { padding: 16px; max-width: 1200px; margin: auto; }
    .section { margin-bottom: 20px; }
    .section h2 { margin-bottom: 8px; }
    .poi-card { border: 1px solid #ccc; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    #input-params { list-style: none; padding-left: 0; }
    #input-params li { margin-bottom: 4px; }
    .poi-card a { color: #0066cc; text-decoration: none; }
    .poi-card a:hover { text-decoration: underline; }
    @media (min-width: 1000px) {
      #wrapper { grid-template-columns: 1.4fr 0.8fr; max-height: 100vh; }
      #map { height: 100vh; }
      #panel { margin: 0; max-height: 100vh; overflow-y: auto; }
    }
  </style>
</head>
<body>
  <div id="wrapper">
    <div id="map"></div>
    <div id="panel">
    <div class="section">
      <h1>Reiseplan: <span id="theme-title"></span></h1>
      <p id="summary"></p>
    </div>
    <div class="section">
      <h2>Eingabeparameter</h2>
      <ul id="input-params"></ul>
    </div>
    <div class="section">
      <h2>Etappenziele</h2>
      <ol id="route-list"></ol>
    </div>
    <div class="section">
      <h2>Tag für Tag</h2>
      <div id="daily-plan"></div>
    </div>
    <div class="section">
      <h2>Sehenswürdigkeiten (POI)</h2>
      <div id="poi-list"></div>
    </div>
    <div class="section">
      <h2>Günstige Tankstellen auf der Route</h2>
      <div id="fuel-list"></div>
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script id="trip-data" type="application/json">%s</script>
  <script>
    const tripPlan = JSON.parse(document.getElementById('trip-data').textContent);

    function createListItem(text) {
      const li = document.createElement('li');
      li.textContent = text;
      return li;
    }

    function initTripPanel() {
      document.getElementById('theme-title').textContent = tripPlan.theme;
      document.getElementById('summary').textContent = `Startort: ${tripPlan.start_location} · Dauer: ${tripPlan.duration_days} Tage · Reisezeit pro Tag: ${tripPlan.travel_time_per_day} Stunden`;

      const inputParams = document.getElementById('input-params');
      inputParams.appendChild(createListItem(`Startort: ${tripPlan.start_location}`));
      inputParams.appendChild(createListItem(`Reisethema: ${tripPlan.theme}`));
      inputParams.appendChild(createListItem(`Reisedauer: ${tripPlan.duration_days} Tage`));
      inputParams.appendChild(createListItem(`Reisezeit pro Tag: ${tripPlan.travel_time_per_day} Stunden`));

      const routeList = document.getElementById('route-list');
      tripPlan.route_stops.forEach(stop => routeList.appendChild(createListItem(`${stop.name} (${stop.lat.toFixed(4)}, ${stop.lng.toFixed(4)})`)));

      const dailyPlan = document.getElementById('daily-plan');
      tripPlan.daily_plan.forEach(day => {
        const card = document.createElement('div');
        card.className = 'poi-card';
        const title = document.createElement('h3');
        title.textContent = day.day;
        const content = document.createElement('p');
        content.textContent = day.activities;
        card.appendChild(title);
        card.appendChild(content);
        dailyPlan.appendChild(card);
      });

      const poiList = document.getElementById('poi-list');
      tripPlan.pois.forEach(poi => {
        const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(poi.name + ' ' + poi.location)}`;
        const card = document.createElement('div');
        card.className = 'poi-card';
        card.innerHTML = `<strong>${poi.name}</strong><p>${poi.description}</p><p><em>${poi.location}</em></p><p><a href="${searchUrl}" target="_blank" rel="noopener noreferrer">In Google suchen</a></p>`;
        poiList.appendChild(card);
      });

      const fuelList = document.getElementById('fuel-list');
      if (tripPlan.fuel_stations && tripPlan.fuel_stations.length) {
        tripPlan.fuel_stations.forEach(station => {
          const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(station.name + ' ' + station.location + ' Tankstelle')}`;
          const card = document.createElement('div');
          card.className = 'poi-card';
          card.innerHTML = `<strong>${station.name}</strong><p>${station.location}</p><p>Preis: ${station.price ? station.price.toFixed(2) + ' €' : 'n/a'}</p><p><a href="${searchUrl}" target="_blank" rel="noopener noreferrer">In Google suchen</a></p>`;
          fuelList.appendChild(card);
        });
      } else {
        fuelList.appendChild(createListItem('Keine Tankstellendaten verfügbar.'));
      }
    }

    function initMap() {
      initTripPanel();

      const germanyBounds = L.latLngBounds([[47.2, 5.8], [55.1, 15.2]]);
      const routeGeometry = tripPlan.route_geometry || tripPlan.route_stops.map(stop => [stop.lat, stop.lng]);
      const map = L.map('map', { maxBounds: germanyBounds, maxBoundsViscosity: 0.8 }).fitBounds(germanyBounds);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);

      const routeLine = L.polyline(routeGeometry, { color: 'blue', weight: 5, opacity: 0.7 }).addTo(map);
      map.fitBounds(routeLine.getBounds(), { padding: [40, 40] });

      tripPlan.route_stops.forEach((stop, index) => {
        L.circleMarker([stop.lat, stop.lng], {
          radius: 8,
          color: 'navy',
          fillColor: '#3388ff',
          fillOpacity: 0.9,
        }).addTo(map)
          .bindPopup(`<strong>Etappe ${index + 1}: ${stop.name}</strong>`);
      });

      tripPlan.pois.forEach(poi => {
        const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(poi.name + ' ' + poi.location)}`;
        L.marker([poi.lat, poi.lng], { title: poi.name })
          .addTo(map)
          .bindPopup(`<strong>${poi.name}</strong><br>${poi.description}<br><em>${poi.location}</em><br><a href="${searchUrl}" target="_blank" rel="noopener noreferrer">In Google suchen</a>`);
      });

      tripPlan.fuel_stations.forEach(station => {
        const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(station.name + ' ' + station.location + ' Tankstelle')}`;
        L.circleMarker([station.lat, station.lng], {
          radius: 8,
          color: '#006600',
          fillColor: '#00cc00',
          fillOpacity: 0.9,
        }).addTo(map)
          .bindPopup(`<strong>${station.name}</strong><br>${station.location}<br>Preis: ${station.price ? station.price.toFixed(2) + ' €' : 'n/a'}<br><a href="${searchUrl}" target="_blank" rel="noopener noreferrer">In Google suchen</a>`);
      });
    }

    document.addEventListener('DOMContentLoaded', initMap);
  </script>
</body>
</html>
"""


def normalize_theme(theme: str) -> str:
    key = theme.strip().lower()
    if key in THEME_DESTINATIONS:
        return key
    if key in ["stadt", "staedte", "staedte", "staedten"]:
        return "städte"
    if key in ["berge", "berg"]:
        return "berge"
    if key in ["bau", "bauten", "besondere bauten", "bauwerke"]:
        return "besondere bauten"
    if key in ["camping", "campingplätze", "zelten"]:
        return "camping"
    return "städte"


def get_start_coordinates(start_location: str) -> Dict[str, float]:
    lookup = start_location.strip().lower()
    if lookup in KNOWN_START_LOCATIONS:
        return KNOWN_START_LOCATIONS[lookup]
    # Fallback: nimm Berlin, wenn kein bekannter Startort gefunden wird.
    return KNOWN_START_LOCATIONS["berlin"]


def distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return math.hypot(a["lat"] - b["lat"], a["lng"] - b["lng"])


def point_to_segment_distance(point: Dict[str, float], a: Dict[str, float], b: Dict[str, float]) -> float:
    if a == b:
        return distance(point, a)
    px = point["lat"]
    py = point["lng"]
    ax = a["lat"]
    ay = a["lng"]
    bx = b["lat"]
    by = b["lng"]
    dx = bx - ax
    dy = by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    closest = {"lat": ax + t * dx, "lng": ay + t * dy}
    return distance(point, closest)


def get_osrm_route_geometry(route_stops: List[Dict[str, Any]]) -> List[List[float]]:
    if len(route_stops) < 2:
        return []
    coords = ";".join(
        f"{stop['lng']},{stop['lat']}" for stop in route_stops
    )
    url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('code') == 'Ok' and data.get('routes'):
                geometry = data['routes'][0]['geometry']['coordinates']
                return [[lat, lng] for lng, lat in geometry]
    except Exception:
        pass
    return [[stop['lat'], stop['lng']] for stop in route_stops]


def load_tanken_data() -> Optional[List[Dict[str, Any]]]:
    try:
        import Tanken as tanken
    except ModuleNotFoundError:
        try:
            import tanken
        except ModuleNotFoundError:
            return None
        else:
            tanken = tanken
    else:
        tanken = tanken

    if hasattr(tanken, 'GAS_STATIONS'):
        return tanken.GAS_STATIONS
    if hasattr(tanken, 'get_tankstellen_data'):
        return tanken.get_tankstellen_data()
    return None


def select_cheapest_tankstellen(route: List[Dict[str, Any]], tanken_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not tanken_data:
        return []

    selected: List[Dict[str, Any]] = []
    route_segments = []
    for i in range(len(route) - 1):
        route_segments.append((route[i], route[i + 1]))

    for start, end in route_segments:
        best = None
        best_score = float('inf')
        for station in tanken_data:
            dist = point_to_segment_distance(station, start, end)
            if dist > 0.8:
                continue
            score = station.get('price', 999.0) + dist * 20
            if score < best_score:
                best_score = score
                best = station
        if best and all(best.get('name') != existing.get('name') for existing in selected):
            selected.append(best)
    return selected


def select_route_stops(start_location: str, theme: str, duration_days: int, travel_time_per_day: int) -> List[Dict[str, Any]]:
    theme_key = normalize_theme(theme)
    candidates = [dest for dest in THEME_DESTINATIONS[theme_key] if dest["name"].strip().lower() != start_location.strip().lower()]
    start_coords = get_start_coordinates(start_location)

    max_stops = min(len(candidates), max(2, duration_days + 1))
    if travel_time_per_day <= 4:
        max_stops = min(max_stops, 3)
    elif travel_time_per_day <= 6:
        max_stops = min(max_stops, 4)
    else:
        max_stops = min(max_stops, 5)

    def scenic_score(dest: Dict[str, Any]) -> float:
        return len(dest.get("poi", [])) * 20 - distance(dest, start_coords) * 8

    selected = sorted(candidates, key=scenic_score, reverse=True)[: max_stops - 1]

    route = [{"name": start_location, **start_coords}]
    current = route[0]
    remaining = selected.copy()
    while remaining:
        next_stop = min(remaining, key=lambda dest: distance(dest, current) - len(dest.get("poi", [])) * 0.4)
        route.append(next_stop)
        remaining.remove(next_stop)
        current = next_stop

    return route


def build_daily_plan(route: List[Dict[str, Any]], travel_time_per_day: int, duration_days: int) -> List[Dict[str, str]]:
    plan = []
    stops = route[1:]
    days = max(1, min(duration_days, len(stops)))
    stops_per_day = max(1, math.ceil(len(stops) / days))

    day = 1
    index = 0
    while index < len(stops):
        current_stops = stops[index:index + stops_per_day]
        route_names = ' → '.join([stop['name'] for stop in current_stops])
        plan.append({
            "day": f"Tag {day}",
            "activities": f"Etappe: {route_names}. Plane genug Zeit für Sehenswürdigkeiten und Pausen; ca. {travel_time_per_day} Stunden Tagesreisezeit."
        })
        index += stops_per_day
        day += 1

    while day <= duration_days:
        plan.append({
            "day": f"Tag {day}",
            "activities": "Ruhetag oder ausführliche Besichtigung vor Ort. Genieße die Umgebung und versuche lokale Highlights." 
        })
        day += 1

    return plan


def collect_pois(route: List[Dict[str, Any]], theme: str) -> List[Dict[str, Any]]:
    pois = []
    route_names = {stop['name'].strip().lower() for stop in route}
    for stop in route[1:]:
        for poi in stop.get("poi", []):
            pois.append({
                "name": poi["name"],
                "description": poi["description"],
                "location": stop["name"],
                "lat": stop["lat"],
                "lng": stop["lng"],
            })

    threshold = 0.35
    theme_key = normalize_theme(theme)
    for candidate in THEME_DESTINATIONS[theme_key]:
        if candidate["name"].strip().lower() in route_names:
            continue
        for i in range(len(route) - 1):
            if point_to_segment_distance(candidate, route[i], route[i + 1]) <= threshold:
                for poi in candidate.get("poi", []):
                    pois.append({
                        "name": poi["name"],
                        "description": f"(Nahe der Route) {poi['description']}",
                        "location": candidate["name"],
                        "lat": candidate["lat"],
                        "lng": candidate["lng"],
                    })
                break

    return pois


def plan_trip(data: Dict[str, Any]) -> Dict[str, Any]:
    start_location = data.get("start_location", "Berlin")
    theme = data.get("theme", "Städte")
    duration_days = int(data.get("duration_days", 3))
    travel_time_per_day = int(data.get("travel_time_per_day", 6))

    route_stops = select_route_stops(start_location, theme, duration_days, travel_time_per_day)
    route_geometry = get_osrm_route_geometry(route_stops)
    daily_plan = build_daily_plan(route_stops, travel_time_per_day, duration_days)
    pois = collect_pois(route_stops, theme)
    tanken_data = load_tanken_data() or []
    fuel_stations = select_cheapest_tankstellen(route_stops, tanken_data)

    return {
        "start_location": start_location,
        "theme": normalize_theme(theme).capitalize(),
        "duration_days": duration_days,
        "travel_time_per_day": travel_time_per_day,
        "route_stops": route_stops,
        "route_geometry": route_geometry,
        "daily_plan": daily_plan,
        "pois": pois,
        "fuel_stations": fuel_stations,
    }


def generate_html(plan: Dict[str, Any], output_path: Path) -> None:
    json_data = json.dumps(plan, ensure_ascii=False, indent=2)
    html = HTML_TEMPLATE % json_data
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML-Datei geschrieben: {output_path.resolve()}")
    print("Öffne die Datei im Browser. Die Karte wird jetzt mit OpenStreetMap/Leaflet dargestellt.")


def prompt_manual_data() -> Dict[str, Any]:
    print("Manuelle Testdaten für die Reiseplanung")
    theme = input("Reisethema (Städte, Berge, besondere Bauten, Camping) [Städte]: ") or "Städte"
    start_location = input("Startort (z.B. Berlin, München, Hamburg) [Berlin]: ") or "Berlin"
    duration_days = input("Reisedauer in Tagen [4]: ") or "4"
    travel_time_per_day = input("Reisezeit pro Tag in Stunden [6]: ") or "6"
    return {
        "theme": theme,
        "start_location": start_location,
        "duration_days": int(duration_days),
        "travel_time_per_day": int(travel_time_per_day),
    }


def load_orchestrator_data() -> Optional[Dict[str, Any]]:
    try:
        import orchestrator

        if hasattr(orchestrator, "TRIP_DATA"):
            return orchestrator.TRIP_DATA
        if hasattr(orchestrator, "get_trip_data"):
            return orchestrator.get_trip_data()
    except ModuleNotFoundError:
        return None
    except Exception as exc:
        print(f"Fehler beim Laden von orchestrator.py: {exc}")
        return None


def main() -> None:
    print("maps&poi.py - Reiseplanung für Deutschland mit interaktiver HTML-Karte")
    data = None

    use_orchestrator = input("Daten aus orchestrator.py verwenden, falls vorhanden? (j/N): ")
    if use_orchestrator.strip().lower() == "j":
        data = load_orchestrator_data()
        if data is None:
            print("Keine Daten aus orchestrator.py gefunden. Nutze manuelle Eingabe.")

    if data is None:
        data = prompt_manual_data()

    plan = plan_trip(data)
    output_file = Path("route_map.html")
    generate_html(plan, output_file)

    print("Teste das Ergebnis, indem du die erzeugte HTML-Datei im Browser öffnest.")


if __name__ == "__main__":
    main()
