#!/usr/bin/env python3
"""
Orchestrator für die Travel Planner AI
Koordiniert alle Agenten: Tankstellen, Wetter, Route & POIs
Vollständiger Output mit allen Informationen
"""

import sys
import os
import json
from datetime import datetime, timedelta
import importlib.util

# ==================== IMPORTS ====================

# Import Tankstelle Agent mit Leerzeichen im Namen
spec = importlib.util.spec_from_file_location(
    "tankstelle", 
    os.path.join(os.path.dirname(__file__), "Tankstelle MR.py")
)
tankstelle_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tankstelle_module)
cheapest_station = tankstelle_module.cheapest_station

# Import Maps & POI Agent mit & im Namen
spec = importlib.util.spec_from_file_location(
    "maps_poi", 
    os.path.join(os.path.dirname(__file__), "maps&poi.py")
)
try:
    maps_poi_agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maps_poi_agent)
except Exception as e:
    print(f"Warnung: Maps&POI Agent konnte nicht geladen werden: {e}")
    maps_poi_agent = None

# Import Wetter Agent
try:
    import wetter_agent
except ImportError:
    wetter_agent = None


# ==================== CONFIGURATION ====================

TRAVEL_TIME_PER_DAY_HOURS = 8


# ==================== MAIN ORCHESTRATOR ====================

def get_user_input():
    """Fragt den Nutzer nach Reiseparametern."""
    print("\n" + "="*70)
    print("🚗 TRAVEL PLANNER - INTELLIGENTE REISEPLANUNG MIT KI")
    print("="*70 + "\n")
    
    # Startort
    startort = input("📍 Startort (z.B. München, Berlin, Hamburg): ").strip()
    if not startort:
        startort = "München"
    
    # Reisedauer
    while True:
        try:
            days = int(input("📅 Reisedauer in Tagen (1-30): ").strip())
            if 1 <= days <= 30:
                break
            print("   ❌ Bitte gib eine Zahl zwischen 1 und 30 ein.")
        except ValueError:
            print("   ❌ Bitte gib eine Zahl ein.")
    
    # Reisethema
    print("\n🎨 Reisethema:")
    print("   1) Städte (Standard)")
    print("   2) Berge")
    print("   3) Besondere Bauten")
    print("   4) Camping & Natur")
    theme_choice = input("   Wahl (1-4, default 1): ").strip()
    theme_map = {"1": "Städte", "2": "Berge", "3": "Besondere Bauten", "4": "Camping"}
    theme = theme_map.get(theme_choice, "Städte")
    
    # Kraftstoffart
    print("\n⛽ Kraftstoffart:")
    print("   1) E5 (Standard)")
    print("   2) E10")
    print("   3) Diesel")
    fuel_choice = input("   Wahl (1-3, default 1): ").strip()
    fuel_map = {"1": "e5", "2": "e10", "3": "diesel"}
    fuel_type = fuel_map.get(fuel_choice, "e5")
    
    # Verbrauch pro 100 km
    while True:
        try:
            consumption = float(input("\n📊 Verbrauch pro 100 km (z.B. 7.5): ").strip())
            if 3 <= consumption <= 20:
                break
            print("   ❌ Bitte gib einen Wert zwischen 3 und 20 ein.")
        except ValueError:
            print("   ❌ Bitte gib eine Dezimalzahl ein.")
    
    return {
        "startort": startort,
        "days": days,
        "theme": theme,
        "fuel_type": fuel_type,
        "consumption_per_100km": consumption
    }


def run_tank_agent(startort, fuel_type):
    """Ruft Tankstellen-Agent auf."""
    print("\n   🔍 Suche günstigste Tankstelle am Startort...")
    try:
        result = cheapest_station(startort, fuel_type, radius_km=25)
        print(f"   ✅ Gefunden: {result['name']}")
        return result
    except Exception as e:
        print(f"   ⚠️  Fehler: {e}")
        return {
            "name": "Nicht verfügbar",
            "price": 1.80,
            "fuel_type": fuel_type.upper(),
            "distance_km": 0,
            "address": "Standardpreis",
            "error": str(e)
        }


def run_wetter_agent(startort, days):
    """Ruft Wetter-Agent mit vollständigen Funktionen auf."""
    print("   🔍 Hole Wetterdaten und Packliste...")
    
    if wetter_agent is None:
        print("   ⚠️  Wetter-Agent nicht verfügbar")
        return None
    
    try:
        # Baue Reise-Etappen für Wetter-Agent
        reise_etappen = []
        start_date = datetime.now()
        
        for day in range(1, days + 1):
            current_date = start_date + timedelta(days=day-1)
            reise_etappen.append({
                "tag": day,
                "datum": current_date.strftime("%Y-%m-%d"),
                "zielort": startort,
                "ziel_lat": 48.1351,  # München Default
                "ziel_lon": 11.5820,
            })
        
        # Rufe Wetter-Kachel auf (hat alles drin: Packliste, Risiko, etc.)
        wetter_kachel = wetter_agent.erstelle_wetter_kachel(reise_etappen)
        print(f"   ✅ Wetterdaten abrufen (Risiko: {wetter_kachel.get('wetter_risiko', 'N/A')})")
        return wetter_kachel
    except Exception as e:
        print(f"   ⚠️  Fehler bei Wetter: {e}")
        return None


def run_route_agent(startort, theme, days, weather_data=None, gas_station=None):
    """Ruft Route & POI Agent auf und generiert HTML-Karte."""
    print("   🔍 Plane Route mit Sehenswürdigkeiten...")
    
    if maps_poi_agent is None:
        print("   ⚠️  Route-Agent nicht verfügbar")
        return None
    
    try:
        # Rufe plan_trip auf mit allen Parametern INKL. Wetter und Tank
        trip_data = {
            "start_location": startort,
            "theme": theme,
            "duration_days": days,
            "travel_time_per_day": TRAVEL_TIME_PER_DAY_HOURS,
            "weather_data": weather_data,
            "gas_station": gas_station,
        }
        
        plan = maps_poi_agent.plan_trip(trip_data)
        print(f"   ✅ Route geplant ({len(plan.get('route_stops', []))} Stopps)")
        
        # Generiere HTML-Karte
        from pathlib import Path
        html_output = Path("route_map.html")
        maps_poi_agent.generate_html(plan, html_output)
        print(f"   ✅ Interaktive Karte gespeichert: {html_output}")
        
        return plan
    except Exception as e:
        print(f"   ⚠️  Fehler bei Route: {e}")
        return None


def calculate_fuel_costs(gas_station, route_plan, consumption_per_100km):
    """Berechnet Treibstoffkosten basierend auf echten Routendaten."""
    try:
        # Versuche echte Distanz aus Route zu bekommen
        geometry = route_plan.get("route_geometry", []) if route_plan else []
        
        # Fallback: Geschätzte Distanz
        if not geometry:
            estimated_distance = 500  # Durchschnitt pro Tag
        else:
            # Vereinfachte Berechnung: Anzahl Punkte * ~1km durchschnitt
            estimated_distance = len(geometry) 
        
        price_per_liter = gas_station.get("price", 1.80)
        liters_needed = (estimated_distance / 100.0) * consumption_per_100km
        total_costs = liters_needed * price_per_liter
        
        return {
            "estimated_distance_km": estimated_distance,
            "consumption_per_100km": consumption_per_100km,
            "liters_needed": round(liters_needed, 2),
            "price_per_liter": price_per_liter,
            "total_fuel_costs": round(total_costs, 2),
            "currency": "€"
        }
    except Exception as e:
        return {
            "error": str(e),
            "estimated_distance_km": 0,
            "total_fuel_costs": 0
        }


def format_weather_output(weather_data):
    """Formatiert Wetterdaten für Ausgabe."""
    if not weather_data:
        return "🌤️ Wetterdaten nicht verfügbar"
    
    output = "\n🌤️ WETTER & PACKLISTE:\n"
    output += f"   Datenbasis:        {weather_data.get('datenbasis', 'N/A')}\n"
    output += f"   Temperaturspanne:  {weather_data.get('temperaturspanne', {}).get('text', 'N/A')}\n"
    output += f"   Regentage:         {weather_data.get('anzahl_regentage', 0)}\n"
    output += f"   Wetterrisiko:      {weather_data.get('wetter_risiko', 'N/A').upper()}\n"
    output += f"\n   📦 Packliste:\n"
    output += f"      {weather_data.get('packempfehlung', 'N/A')}\n"
    
    # Tagesuebersicht
    if weather_data.get('tagesuebersicht'):
        output += f"\n   Tagesuebersicht:\n"
        for day in weather_data['tagesuebersicht'][:5]:  # Max 5 Tage
            output += f"      Tag {day.get('tag')}: {day.get('ort')} - "
            output += f"{day.get('temperatur_min')}°C bis {day.get('temperatur_max')}°C, "
            output += f"{day.get('wetterbeschreibung')}\n"
    
    return output


def format_route_output(route_data):
    """Formatiert Routendaten für Ausgabe."""
    if not route_data:
        return "🗺️ Routendaten nicht verfügbar"
    
    output = "\n🗺️ ROUTE & SEHENSWÜRDIGKEITEN:\n"
    output += f"   Theme:             {route_data.get('theme', 'N/A')}\n"
    output += f"   Stopps:            {len(route_data.get('route_stops', []))}\n"
    output += f"   Tagespläne:        {len(route_data.get('daily_plan', []))}\n"
    output += f"   POIs:              {len(route_data.get('pois', []))}\n"
    
    # Erste Route-Stopps
    if route_data.get('route_stops'):
        output += f"\n   Route:\n"
        for i, stop in enumerate(route_data.get('route_stops', [])[:5]):
            output += f"      {i+1}. {stop.get('name', 'N/A')} ({stop.get('lat')}, {stop.get('lng')})\n"
    
    # Sehenswürdigkeiten
    if route_data.get('pois'):
        output += f"\n   Top Sehenswürdigkeiten:\n"
        for poi in route_data.get('pois', [])[:5]:
            output += f"      • {poi.get('name', 'N/A')}: {poi.get('description', 'N/A')}\n"
    
    return output


def generate_full_summary(user_input, gas_station, weather, route, fuel_costs):
    """Erstellt vollständigen, detaillierten Reiseplan."""
    summary = "\n" + "="*70
    summary += "\n✈️  VOLLSTÄNDIGER REISEPLAN"
    summary += "\n" + "="*70 + "\n"
    
    # Eingaben
    summary += "📋 REISEPARAMETER:\n"
    summary += f"   Startort:          {user_input['startort']}\n"
    summary += f"   Dauer:             {user_input['days']} Tage\n"
    summary += f"   Theme:             {user_input['theme']}\n"
    summary += f"   Kraftstoff:        {user_input['fuel_type'].upper()}\n"
    summary += f"   Verbrauch:         {user_input['consumption_per_100km']} L/100km\n"
    
    # Tankstelle
    summary += "\n" + "-"*70 + "\n"
    summary += "🚗 TANKSTELLE AM STARTORT:\n"
    summary += f"   Name:              {gas_station.get('name', 'N/A')}\n"
    summary += f"   Preis:             {gas_station.get('price', 'N/A')} €/L\n"
    summary += f"   Entfernung:        {gas_station.get('distance_km', 'N/A')} km\n"
    summary += f"   Adresse:           {gas_station.get('address', 'N/A')}\n"
    
    # Kosten
    summary += "\n" + "-"*70 + "\n"
    summary += "💰 TREIBSTOFFKOSTEN:\n"
    summary += f"   Distanz:           {fuel_costs.get('estimated_distance_km', 'N/A')} km\n"
    summary += f"   Liter benötigt:    {fuel_costs.get('liters_needed', 'N/A')} L\n"
    summary += f"   Preis pro Liter:   {fuel_costs.get('price_per_liter', 'N/A')} €\n"
    summary += f"   GESAMTKOSTEN:      💰 {fuel_costs.get('total_fuel_costs', 'N/A')} €\n"
    
    # Wetter & Packliste
    summary += "\n" + "-"*70
    summary += format_weather_output(weather)
    
    # Route & POIs
    summary += "\n" + "-"*70
    summary += format_route_output(route)
    
    summary += "\n" + "="*70 + "\n"
    
    return summary


def main():
    """Hauptfunktion des Orchestrators."""
    try:
        print("\n" + "🔄 Starte Agenten...")
        
        # 1. Nutzer-Input
        user_input = get_user_input()
        
        print("\n" + "-"*70)
        print("⏳ Verarbeite alle Agenten...\n")
        
        # 2. Agenten aufrufen
        gas_station = run_tank_agent(user_input["startort"], user_input["fuel_type"])
        weather = run_wetter_agent(user_input["startort"], user_input["days"])
        route = run_route_agent(user_input["startort"], user_input["theme"], user_input["days"], weather, gas_station)
        
        # 3. Kosten berechnen
        fuel_costs = calculate_fuel_costs(gas_station, route, user_input["consumption_per_100km"])
        
        # 4. Vollständiger Reiseplan
        print("\n" + "-"*70)
        summary = generate_full_summary(user_input, gas_station, weather, route, fuel_costs)
        print(summary)
        
        # 5. Speichern nur als Text
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_txt = f"reiseplan_{timestamp}.txt"
        with open(filename_txt, "w", encoding="utf-8") as f:
            f.write(summary)
        
        print(f"💾 Reiseplan gespeichert:")
        print(f"   • Text:  {filename_txt}")
        print(f"   • HTML:  route_map.html (Interaktive Karte)\n")
        print(f"🌐 Öffne 'route_map.html' im Browser um deine Route zu sehen!\n")
        
    except KeyboardInterrupt:
        print("\n\n❌ Reiseplanung abgebrochen.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fehler im Orchestrator: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
