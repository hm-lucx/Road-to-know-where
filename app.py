#!/usr/bin/env python3
"""Kleine Flask-Webapp als Schnittstelle zum Road-to-know-where Orchestrator."""

import importlib.util
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, make_response, render_template, request
import requests


PROJECT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_PATH = PROJECT_DIR / "Orchestrat MR.py"

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/plan", methods=["OPTIONS"])
def options_api_plan():
    response = make_response()
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def lade_orchestrator():
    """Laedt den bestehenden Orchestrator, ohne dessen Dateinamen zu aendern."""
    spec = importlib.util.spec_from_file_location("road_orchestrator", ORCHESTRATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Orchestrator konnte nicht geladen werden: {ORCHESTRATOR_PATH}")

    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


ORCHESTRATOR = lade_orchestrator()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Berechnet eine Distanznaeherung zwischen zwei Koordinaten."""
    radius = 6371.0
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def berechne_luftlinien_distanz(route_stops: List[Dict[str, Any]]) -> float:
    """Fallback, falls OSRM nicht erreichbar ist."""
    distanz = 0.0
    for index in range(len(route_stops) - 1):
        start = route_stops[index]
        ziel = route_stops[index + 1]
        distanz += haversine_km(
            float(start["lat"]),
            float(start["lng"]),
            float(ziel["lat"]),
            float(ziel["lng"]),
        )
    return round(distanz, 1)


def hole_osrm_route(route_stops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Holt eine echte Autoroute fuer die Kartenanzeige."""
    if len(route_stops) < 2:
        return {"geometry": [], "distance_km": 0.0, "duration_hours": 0.0, "source": "none"}

    koordinaten = ";".join(
        f"{float(stop['lng'])},{float(stop['lat'])}" for stop in route_stops
    )
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{koordinaten}?overview=full&geometries=geojson&steps=false"
    )

    try:
        antwort = requests.get(url, timeout=25)
        antwort.raise_for_status()
        daten = antwort.json()
    except Exception:
        try:
            # Fallback fuer lokale macOS-Setups, bei denen Python/SSL mit OSRM zickt.
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
                "geometry": [[stop["lat"], stop["lng"]] for stop in route_stops],
                "distance_km": berechne_luftlinien_distanz(route_stops),
                "duration_hours": None,
                "source": "fallback",
                "error": str(fehler),
            }
    if daten.get("code") != "Ok" or not daten.get("routes"):
        return {
            "geometry": [[stop["lat"], stop["lng"]] for stop in route_stops],
            "distance_km": berechne_luftlinien_distanz(route_stops),
            "duration_hours": None,
            "source": "fallback",
            "error": daten.get("message", "OSRM lieferte keine Route"),
        }

    route = daten["routes"][0]
    coordinates = route.get("geometry", {}).get("coordinates", [])
    return {
        "geometry": [[lat, lng] for lng, lat in coordinates],
        "distance_km": round(float(route.get("distance", 0)) / 1000, 1),
        "duration_hours": round(float(route.get("duration", 0)) / 3600, 1),
        "source": "osrm_driving",
    }


def normalisiere_payload(daten: Dict[str, Any]) -> Dict[str, Any]:
    """Wandelt Frontend-Werte in das Orchestrator-Format um."""
    interests = daten.get("interests")
    theme = interests[0] if isinstance(interests, list) and interests else "Städte"
    theme = str(daten.get("theme") or theme).strip()

    return {
        "start_location": str(daten.get("start_location") or "München").strip(),
        "theme": theme,
        "duration_days": int(daten.get("duration_days") or 4),
        "travel_time_per_day": int(daten.get("travel_time_per_day") or 6),
        "fuel_type": str(daten.get("fuel_type") or "e5").lower(),
        "start_date": str(daten.get("start_date") or "2026-06-06"),
        "fuel_consumption_l_per_100km": float(daten.get("fuel_consumption_l_per_100km") or 5),
        "budget": daten.get("budget"),
        "travel_style": daten.get("travel_style") or "Ausgewogen",
    }


def ergaenze_frontend_daten(result: Dict[str, Any], eingabe: Dict[str, Any]) -> Dict[str, Any]:
    """Fuegt Routengeometrie und Kosten hinzu, damit das Frontend einfacher rendern kann."""
    plan = result.get("frontend_plan") or {}
    route_stops = plan.get("route_stops") or []
    route = hole_osrm_route(route_stops)
    fuel = plan.get("fuel_summary") or {}
    fuel_price = fuel.get("price")
    consumption = float(eingabe["fuel_consumption_l_per_100km"])
    liters = round(route["distance_km"] * consumption / 100, 1)
    cost = round(liters * float(fuel_price), 2) if fuel_price is not None else None

    plan["route_geometry"] = route["geometry"]
    plan["route_source"] = route["source"]
    plan["route_distance_km"] = route["distance_km"]
    plan["route_duration_hours"] = route["duration_hours"]
    plan["cost_estimate"] = {
        "fuel_consumption_l_per_100km": consumption,
        "fuel_liters": liters,
        "fuel_price": fuel_price,
        "fuel_cost": cost,
        "estimated": True,
    }
    plan.setdefault("planning_notes", [])
    if route["source"] == "fallback":
        plan["planning_notes"].append(
            "Die Autoroute konnte nicht exakt berechnet werden; Distanz und Kosten sind daher grobe Schaetzungen."
        )
    else:
        plan["planning_notes"].append(
            "Die Kartenlinie basiert auf einer OSRM-Autoroute; Kosten bleiben eine Verbrauchs-Schaetzung."
        )
    result["frontend_plan"] = plan
    return result


@app.get("/")
def index():
    """Landingpage und Formular."""
    return render_template("index.html")


@app.post("/api/plan")
def plan_route():
    """API-Endpunkt: Frontend -> Orchestrator -> Frontend."""
    try:
        payload = normalisiere_payload(request.get_json(force=True) or {})
        result = ORCHESTRATOR.orchestrate_trip(payload, include_telemetry=True)
        result = ergaenze_frontend_daten(result, payload)
        return jsonify({"ok": True, "input": payload, "result": result})
    except Exception as fehler:
        return jsonify({
            "ok": False,
            "error": "Die Reise konnte gerade nicht geplant werden. Bitte pruefe die Eingaben und versuche es erneut.",
            "technical_error": str(fehler),
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
