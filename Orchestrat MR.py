#!/usr/bin/env python3

import sys
import os

# Import des Tankstellen-Agenten
# Beachte: Dateiname mit Leerzeichen muss so importiert werden
spec = __import__('importlib.util').util.spec_from_file_location(
    "tankstelle", 
    os.path.join(os.path.dirname(__file__), "Tankstelle MR.py")
)
tankstelle = __import__('importlib.util').util.module_from_spec(spec)
spec.loader.exec_module(tankstelle)
cheapest_station = tankstelle.cheapest_station

def orchestrate(city, fuel_type="e5"):
    print(f"🚀 Starte Orchestration für {city}...\n")
    
    # Phase 1: Tankstelle
    print("📍 Suche günstigste Tankstelle...")
    gas_result = cheapest_station(city, fuel_type)
    print(f"✅ Tankstelle gefunden: {gas_result}\n")
    
    # Phase 2: Wetter (SPÄTER hinzufügen)
    # weather_result = get_weather(city)
    
    # Phase 3: Sehenswürdigkeiten (SPÄTER hinzufügen)
    # sights_result = get_sights(city)
    
    # Ergebnis zusammenfassen
    return {
        "city": city,
        "gas_station": gas_result,
        # "weather": weather_result,
        # "sights": sights_result,
    }

if __name__ == "__main__":
    city = input("Welche Stadt? ")
    result = orchestrate(city)
    print(result)