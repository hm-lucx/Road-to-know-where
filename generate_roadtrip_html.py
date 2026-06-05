#!/usr/bin/env python3
"""Erzeugt eine moderne HTML-Ausgabe fuer einen konkreten Roadtrip-Test."""

import html
import importlib.util
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_PATH = PROJECT_DIR / "Orchestrat MR.py"
OUTPUT_PATH = PROJECT_DIR / "roadtrip_muenchen_4_tage.html"
VERBRAUCH_L_PRO_100KM = 5.0


def lade_orchestrator():
    """Laedt den Orchestrator trotz Leerzeichen im Dateinamen."""
    spec = importlib.util.spec_from_file_location("road_orchestrator", ORCHESTRATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Orchestrator konnte nicht geladen werden: {ORCHESTRATOR_PATH}")

    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def h(value: Any) -> str:
    """Escaped Werte fuer sichere HTML-Ausgabe."""
    return html.escape(str(value))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Berechnet die Luftlinien-Entfernung zwischen zwei Punkten."""
    radius = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def berechne_routendistanz(route_geometry: List[List[float]], route_stops: List[Dict[str, Any]]) -> float:
    """Berechnet eine einfache Streckennaeherung aus Geometrie oder Stopps."""
    punkte = route_geometry
    if len(punkte) < 2:
        punkte = [[stop["lat"], stop["lng"]] for stop in route_stops]

    distanz = 0.0
    for index in range(len(punkte) - 1):
        start = punkte[index]
        ziel = punkte[index + 1]
        distanz += haversine_km(float(start[0]), float(start[1]), float(ziel[0]), float(ziel[1]))
    return round(distanz, 1)


def hole_osrm_autoroute(route_stops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Holt eine echte Autoroute von OSRM und gibt Leaflet-taugliche Punkte zurueck."""
    if len(route_stops) < 2:
        return {"geometry": [], "distance_km": 0.0, "source": "none"}

    koordinaten = ";".join(
        f"{float(stop['lng'])},{float(stop['lat'])}" for stop in route_stops
    )
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{koordinaten}?overview=full&geometries=geojson&steps=false"
    )

    try:
        # curl funktioniert auf diesem Mac stabiler als Python-SSL mit OSRM.
        antwort = subprocess.run(
            ["curl", "-fsSL", url],
            check=True,
            capture_output=True,
            text=True,
            timeout=25,
        )
        daten = json.loads(antwort.stdout)
    except Exception as fehler:
        return {
            "geometry": [],
            "distance_km": None,
            "source": "fallback",
            "error": str(fehler),
        }

    if daten.get("code") != "Ok" or not daten.get("routes"):
        return {
            "geometry": [],
            "distance_km": None,
            "source": "fallback",
            "error": daten.get("message", "OSRM lieferte keine Route"),
        }

    route = daten["routes"][0]
    geometry = route.get("geometry", {}).get("coordinates", [])
    # OSRM liefert [lng, lat], Leaflet erwartet [lat, lng].
    leaflet_geometry = [[lat, lng] for lng, lat in geometry]

    return {
        "geometry": leaflet_geometry,
        "distance_km": round(float(route.get("distance", 0)) / 1000, 1),
        "duration_hours": round(float(route.get("duration", 0)) / 3600, 1),
        "source": "osrm_driving",
    }


def berechne_kraftstoffkosten(distanz_km: float, preis_pro_liter: Optional[float]) -> Dict[str, Any]:
    """Berechnet Verbrauch und Kosten, falls ein E5-Preis vorhanden ist."""
    liter = round(distanz_km * VERBRAUCH_L_PRO_100KM / 100, 1)
    if preis_pro_liter is None:
        return {
            "liter": liter,
            "kosten": None,
            "text": f"ca. {liter:.1f} l E5, Preis nicht verfuegbar",
        }

    kosten = round(liter * float(preis_pro_liter), 2)
    return {
        "liter": liter,
        "kosten": kosten,
        "text": f"ca. {liter:.1f} l E5, etwa {kosten:.2f} EUR",
    }


def list_items(items: List[str]) -> str:
    return "\n".join(f"<li>{item}</li>" for item in items)


def stop_cards(route_stops: List[Dict[str, Any]]) -> str:
    cards = []
    for index, stop in enumerate(route_stops, start=1):
        poi_count = len(stop.get("poi", []))
        cards.append(
            f"""
            <article class="stop-card">
              <span class="badge">Stopp {index}</span>
              <h3>{h(stop.get("name", "Unbekannter Ort"))}</h3>
              <p>{h(stop.get("lat", ""))}, {h(stop.get("lng", ""))}</p>
              <small>{poi_count} POI-Vorschlaege</small>
            </article>
            """
        )
    return "\n".join(cards)


def daily_cards(daily_plan: List[Dict[str, Any]], weather_days: List[Dict[str, Any]]) -> str:
    cards = []
    wetter_lookup = {tag.get("tag"): tag for tag in weather_days}

    for index, day in enumerate(daily_plan, start=1):
        weather = wetter_lookup.get(index, {})
        weather_text = weather.get("wetterbeschreibung", "Wetterdaten nicht verfuegbar")
        temp_min = weather.get("temperatur_min")
        temp_max = weather.get("temperatur_max")
        temp_text = "Temperatur n/a"
        if temp_min is not None and temp_max is not None:
            temp_text = f"{temp_min:g} bis {temp_max:g} °C"

        cards.append(
            f"""
            <article class="day-card">
              <div class="day-top">
                <span class="day-number">Tag {index}</span>
                <span class="weather-pill">{h(weather_text)}</span>
              </div>
              <h3>{h(day.get("day", f"Tag {index}"))}</h3>
              <p>{h(day.get("activities", ""))}</p>
              <div class="metric-row">
                <span>{h(temp_text)}</span>
                <span>{h(weather.get("niederschlag_mm", "n/a"))} mm Regen</span>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def poi_cards(pois: List[Dict[str, Any]]) -> str:
    cards = []
    for poi in pois:
        maps_query = f"{poi.get('name', '')} {poi.get('location', '')}"
        cards.append(
            f"""
            <article class="poi-card">
              <span>{h(poi.get("location", ""))}</span>
              <h3>{h(poi.get("name", ""))}</h3>
              <p>{h(poi.get("description", ""))}</p>
              <a href="https://www.google.com/search?q={h(maps_query)}" target="_blank" rel="noopener noreferrer">Mehr ansehen</a>
            </article>
            """
        )
    return "\n".join(cards)


def erzeuge_html(orchestrator_result: Dict[str, Any]) -> str:
    input_data = orchestrator_result["input"]
    plan = orchestrator_result["frontend_plan"]
    route_stops = plan.get("route_stops", [])
    autoroute = hole_osrm_autoroute(route_stops)
    route_geometry = autoroute.get("geometry") or plan.get("route_geometry", [])
    daily_plan = plan.get("daily_plan", [])
    pois = plan.get("pois", [])
    weather = plan.get("weather") or {}
    weather_days = weather.get("tagesuebersicht", [])
    fuel = plan.get("fuel_summary") or {}
    telemetry = orchestrator_result.get("telemetry", {})

    distanz_km = autoroute.get("distance_km") or berechne_routendistanz(route_geometry, route_stops)
    kosten = berechne_kraftstoffkosten(distanz_km, fuel.get("price"))
    plan_fuer_karte = {
        **plan,
        "route_geometry": route_geometry,
        "route_source": autoroute.get("source"),
        "route_distance_km": distanz_km,
        "route_duration_hours": autoroute.get("duration_hours"),
    }
    trip_json = json.dumps(plan_fuer_karte, ensure_ascii=False).replace("</", "<\\/")

    hero_route = " -> ".join(stop.get("name", "") for stop in route_stops)
    fuel_price = fuel.get("price")
    fuel_price_text = f"{float(fuel_price):.3f} EUR/L" if fuel_price is not None else "nicht verfuegbar"
    route_source_text = "OSRM-Autoroute" if autoroute.get("source") == "osrm_driving" else "Fallback-Route"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Road-to-know-where | 4 Tage ab München</title>
  <link rel="preconnect" href="https://unpkg.com">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {{
      --ink: #17202a;
      --muted: #657386;
      --panel: #ffffff;
      --line: #dce3ea;
      --brand: #0e6f7c;
      --brand-dark: #124d57;
      --accent: #d1495b;
      --soft: #f4f7f9;
      --gold: #f2b84b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--soft);
    }}
    .hero {{
      min-height: 78vh;
      display: grid;
      grid-template-columns: minmax(320px, 0.78fr) minmax(420px, 1.22fr);
      background: linear-gradient(120deg, rgba(14, 111, 124, 0.92), rgba(18, 77, 87, 0.96));
      color: white;
    }}
    .hero-copy {{
      padding: 48px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 22px;
    }}
    .eyebrow {{
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
      color: #aee5e5;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(42px, 6vw, 72px);
      line-height: 0.96;
      letter-spacing: 0;
    }}
    .lead {{
      font-size: 18px;
      line-height: 1.55;
      max-width: 660px;
      color: #e4f3f4;
    }}
    .hero-stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      max-width: 620px;
    }}
    .stat {{
      border: 1px solid rgba(255,255,255,0.24);
      padding: 14px 16px;
      background: rgba(255,255,255,0.08);
      backdrop-filter: blur(10px);
      border-radius: 8px;
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 2px;
    }}
    .stat span {{ color: #d6eff0; font-size: 13px; }}
    #map {{
      min-height: 78vh;
      width: 100%;
      border-left: 1px solid rgba(255,255,255,0.16);
    }}
    .stop-pin {{
      width: 34px;
      height: 34px;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      background: var(--accent);
      border: 3px solid #ffffff;
      box-shadow: 0 8px 18px rgba(23, 32, 42, 0.28);
      display: grid;
      place-items: center;
    }}
    .stop-pin.start {{
      background: var(--gold);
    }}
    .stop-pin span {{
      transform: rotate(45deg);
      color: white;
      font-size: 13px;
      font-weight: 900;
      line-height: 1;
    }}
    .stop-pin.start span {{
      color: #17202a;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 34px 22px 54px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 18px;
      margin: 18px 0;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 30px;
    }}
    .section-head p {{
      margin: 0;
      color: var(--muted);
      max-width: 560px;
    }}
    .grid {{
      display: grid;
      gap: 16px;
    }}
    .grid-4 {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .grid-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .grid-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .panel, .day-card, .poi-card, .stop-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 10px 24px rgba(31, 45, 61, 0.06);
    }}
    .panel h3, .day-card h3, .poi-card h3, .stop-card h3 {{
      margin: 8px 0 8px;
      font-size: 20px;
    }}
    .panel p, .day-card p, .poi-card p, .stop-card p {{
      color: var(--muted);
      margin: 0;
      line-height: 1.55;
    }}
    .badge, .day-number, .weather-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 5px 9px;
      border-radius: 999px;
      background: #e7f4f5;
      color: var(--brand-dark);
      font-size: 12px;
      font-weight: 800;
    }}
    .weather-pill {{
      background: #fff2d2;
      color: #7a4d00;
    }}
    .day-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .metric-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--brand-dark);
      font-weight: 700;
      margin-top: 16px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
    .highlight {{
      border-top: 5px solid var(--accent);
    }}
    .poi-card span {{
      font-size: 12px;
      font-weight: 800;
      color: var(--accent);
      text-transform: uppercase;
    }}
    .poi-card a {{
      display: inline-block;
      color: var(--brand);
      font-weight: 800;
      margin-top: 14px;
      text-decoration: none;
    }}
    .summary {{
      background: #17202a;
      color: white;
      border-radius: 8px;
      padding: 24px;
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
      align-items: center;
    }}
    .summary p {{ color: #d5dee7; }}
    .summary ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    .summary li {{
      border-bottom: 1px solid rgba(255,255,255,0.16);
      padding-bottom: 10px;
    }}
    footer {{
      color: var(--muted);
      text-align: center;
      padding: 26px;
    }}
    @media (max-width: 920px) {{
      .hero {{ grid-template-columns: 1fr; }}
      #map {{ min-height: 52vh; border-left: 0; }}
      .grid-4, .grid-3, .grid-2, .summary {{ grid-template-columns: 1fr; }}
      .hero-copy {{ padding: 34px 22px; }}
    }}
  </style>
</head>
<body>
  <section class="hero">
    <div class="hero-copy">
      <div class="eyebrow">Road-to-know-where Testlauf</div>
      <h1>4 Tage Städte-Roadtrip ab München</h1>
      <p class="lead">Professionelle HTML-Ausgabe aus dem Orchestrator: Tagesetappen, Wetter, Sehenswürdigkeiten, Tankstelle und einfache Kostenabschätzung für E5 bei 5 l/100 km.</p>
      <div class="hero-stats">
        <div class="stat"><strong>{len(daily_plan)}</strong><span>geplante Reisetage</span></div>
        <div class="stat"><strong>{distanz_km:.0f} km</strong><span>geschätzte Routendistanz</span></div>
        <div class="stat"><strong>{kosten["liter"]:.1f} l</strong><span>E5-Verbrauch</span></div>
        <div class="stat"><strong>{h(fuel_price_text)}</strong><span>ermittelter E5-Preis</span></div>
        <div class="stat"><strong>Auto</strong><span>{h(route_source_text)}</span></div>
      </div>
    </div>
    <div id="map"></div>
  </section>

  <main>
    <section>
      <div class="section-head">
        <h2>Reiseüberblick</h2>
        <p>{h(hero_route)}</p>
      </div>
      <div class="grid grid-4">
        <article class="panel highlight"><h3>Start</h3><p>{h(input_data.get("start_location"))}</p></article>
        <article class="panel"><h3>Interesse</h3><p>{h(input_data.get("theme"))}</p></article>
        <article class="panel"><h3>Kraftstoff</h3><p>E5, {VERBRAUCH_L_PRO_100KM:g} l/100 km</p></article>
        <article class="panel"><h3>Status</h3><p>{h(orchestrator_result.get("status"))}, {telemetry.get("agent_aufrufe", 0)} Agent-Aufrufe</p></article>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Etappen</h2>
        <p>Die Stopps kommen aus dem Städte-Fokus; die Linie in der Karte ist eine Autoroute über OSRM.</p>
      </div>
      <div class="grid grid-4">
        {stop_cards(route_stops)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Tag für Tag</h2>
        <p>Jede Tageskarte kombiniert Etappenplanung und Wetterdaten.</p>
      </div>
      <div class="grid grid-2">
        {daily_cards(daily_plan, weather_days)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Wetter-Kachel</h2>
        <p>{h(weather.get("gesamtbewertung", "Keine Wetterbewertung verfügbar."))}</p>
      </div>
      <div class="grid grid-3">
        <article class="panel"><h3>Temperatur</h3><p>{h((weather.get("temperaturspanne") or {}).get("text", "n/a"))}</p></article>
        <article class="panel"><h3>Regentage</h3><p>{h(weather.get("anzahl_regentage", "n/a"))}</p></article>
        <article class="panel"><h3>Empfehlung</h3><p>{h(weather.get("packempfehlung", "n/a"))}</p></article>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Tank- und Kosteninformationen</h2>
        <p>Die Kosten sind eine Näherung aus Routendistanz, Verbrauch und gefundenem E5-Preis.</p>
      </div>
      <div class="grid grid-3">
        <article class="panel"><h3>Günstige Tankstelle</h3><p>{h(fuel.get("name", "nicht verfügbar"))}<br>{h(fuel.get("address", ""))}</p></article>
        <article class="panel"><h3>E5-Preis</h3><p>{h(fuel_price_text)}</p></article>
        <article class="panel"><h3>Geschätzte Kosten</h3><p>{h(kosten["text"])}</p></article>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Sehenswürdigkeiten</h2>
        <p>Städte-Highlights entlang der geplanten Route.</p>
      </div>
      <div class="grid grid-3">
        {poi_cards(pois)}
      </div>
    </section>

    <section class="summary">
      <div>
        <h2>Finale Zusammenfassung</h2>
        <p>Der Orchestrator hat die Nutzereingaben verarbeitet, drei spezialisierte Agents aufgerufen und eine HTML-fähige Ausgabe erzeugt. Diese Seite ist der Browser-Test der gesamten Softwarekette.</p>
      </div>
      <ul>
        <li>Route: {h(hero_route)}</li>
        <li>Wetterrisiko: {h(weather.get("wetter_risiko", "n/a"))}</li>
        <li>POIs: {len(pois)} Vorschläge</li>
        <li>Laufzeit: {h(telemetry.get("laufzeit_sekunden", "n/a"))} Sekunden</li>
      </ul>
    </section>
  </main>

  <footer>Generiert mit Road-to-know-where Orchestrator.</footer>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script id="trip-data" type="application/json">{trip_json}</script>
  <script>
    const tripPlan = JSON.parse(document.getElementById('trip-data').textContent);
    const routeGeometry = tripPlan.route_geometry && tripPlan.route_geometry.length
      ? tripPlan.route_geometry
      : tripPlan.route_stops.map(stop => [stop.lat, stop.lng]);

    const map = L.map('map', {{ scrollWheelZoom: false }});
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }}).addTo(map);

    const routeLine = L.polyline(routeGeometry, {{
      color: '#d1495b',
      weight: 6,
      opacity: 0.95,
      lineJoin: 'round',
      lineCap: 'round'
    }}).addTo(map);
    map.fitBounds(routeLine.getBounds(), {{ padding: [42, 42] }});

    tripPlan.route_stops.forEach((stop, index) => {{
      const pin = L.divIcon({{
        className: '',
        html: `<div class="stop-pin ${{index === 0 ? 'start' : ''}}"><span>${{index + 1}}</span></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 34],
        popupAnchor: [0, -34]
      }});
      L.marker([stop.lat, stop.lng], {{ icon: pin, title: stop.name }})
        .addTo(map)
        .bindPopup(`<strong>${{index + 1}}. ${{stop.name}}</strong><br>${{index === 0 ? 'Start' : 'Stopp'}}`);
    }});

    tripPlan.pois.forEach(poi => {{
      L.marker([poi.lat, poi.lng]).addTo(map)
        .bindPopup(`<strong>${{poi.name}}</strong><br>${{poi.location}}<br>${{poi.description}}`);
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    orchestrator = lade_orchestrator()
    input_data = {
        "start_location": "München",
        "theme": "Städte",
        "duration_days": 4,
        "travel_time_per_day": 6,
        "fuel_type": "e5",
        "start_date": "2026-06-06",
        "fuel_consumption_l_per_100km": VERBRAUCH_L_PRO_100KM,
    }

    result = orchestrator.orchestrate_trip(input_data, include_telemetry=True)
    OUTPUT_PATH.write_text(erzeuge_html(result), encoding="utf-8")

    print("Roadtrip-HTML erzeugt:")
    print(f"  {OUTPUT_PATH.resolve()}")
    print(f"Status: {result.get('status')}")
    print(f"Agent-Aufrufe: {result.get('telemetry', {}).get('agent_aufrufe')}")
    print(f"Laufzeit: {result.get('telemetry', {}).get('laufzeit_sekunden')} Sekunden")


if __name__ == "__main__":
    main()
