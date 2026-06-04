#!/usr/bin/env python3

import os
import sys

try:
    import requests
except ImportError:
    print("Fehler: Das Python-Paket 'requests' ist nicht installiert.")
    print("Installiere es mit: python3 -m pip install requests")
    sys.exit(1)

TANKERKOENIG_API_KEY = os.environ.get("TANKERKOENIG_API_KEY", "c13ba621-f734-46ef-a52b-83fd9cccc99c")
DEFAULT_FUEL_PRICE = 1.80


def geocode_city(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{city_name}, Germany", "format": "json", "limit": 1}
    headers = {"User-Agent": "TankstellenAgent/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Stadt nicht gefunden: {city_name}")
    return float(data[0]["lat"]), float(data[0]["lon"])


def cheapest_station(city_name, radius_km=25):
    lat, lon = geocode_city(city_name)
    url = "https://creativecommons.tankerkoenig.de/json/list.php"
    params = {
        "lat": lat,
        "lng": lon,
        "rad": int(radius_km),
        "sort": "price",
        "type": "e5",
        "apikey": TANKERKOENIG_API_KEY,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok") or not data.get("stations"):
        raise ValueError("Keine Tankstellen gefunden")

    stations_with_price = [s for s in data["stations"] if s.get("price") is not None and s["price"] > 0]
    if not stations_with_price:
        raise ValueError("Keine Preisdaten verfügbar")

    cheapest = min(stations_with_price, key=lambda s: s["price"])
    return {
        "name": cheapest.get("name"),
        "price": cheapest.get("price"),
        "distance_km": round(cheapest.get("dist", 0), 1),
        "address": f'{cheapest.get("street", "")}, {cheapest.get("place", "")}',
    }


def get_fuel_price_for_trip(start_city=None, bundesland=None):
    """
    Versucht den aktuellen E5-Preis zu ermitteln.
    Gibt den Preis zurück oder den Standardwert falls die API nicht erreichbar ist.
    """
    city = start_city or _get_central_city(bundesland)
    if not city:
        return DEFAULT_FUEL_PRICE, "Standardpreis (kein Standort)"

    try:
        station = cheapest_station(city)
        price = station["price"]
        label = f"{station['name']} ({city}, {price:.2f} €/L)"
        return price, label
    except Exception as e:
        return DEFAULT_FUEL_PRICE, f"Standardpreis 1.80 €/L (Tankerkönig: {e})"


def _get_central_city(bundesland):
    """Gibt eine zentrale Stadt für ein Bundesland zurück."""
    mapping = {
        "bayern": "München",
        "nordrhein-westfalen": "Köln",
        "nrw": "Köln",
        "baden-württemberg": "Stuttgart",
        "niedersachsen": "Hannover",
        "hessen": "Frankfurt",
        "sachsen": "Dresden",
        "rheinland-pfalz": "Mainz",
        "berlin": "Berlin",
        "hamburg": "Hamburg",
        "schleswig-holstein": "Kiel",
        "mecklenburg-vorpommern": "Schwerin",
        "sachsen-anhalt": "Magdeburg",
        "thüringen": "Erfurt",
        "saarland": "Saarbrücken",
        "brandenburg": "Potsdam",
        "bremen": "Bremen",
        "allgäu": "Kempten",
        "oberbayern": "München",
        "schwarzwald": "Freiburg",
        "bodensee": "Konstanz",
    }
    if not bundesland:
        return None
    return mapping.get(bundesland.lower().strip().replace(" ", "-"))


if __name__ == "__main__":
    city = input("Welche Stadt möchtest du prüfen? ")
    try:
        result = cheapest_station(city)
        print(f"Günstigste Tankstelle: {result['name']}")
        print(f"  Preis E5: {result['price']:.3f} €/L")
        print(f"  Entfernung: {result['distance_km']} km")
        print(f"  Adresse: {result['address']}")
    except Exception as e:
        print("Fehler:", e)
        sys.exit(1)
cd /Users/milanrickhoff/Documents/GitHub/Road-to-know-where
git status
git add "Tankstelle MR.py"
git commit -m "Add gas station finder"
git push origin Tankstelle-MR
