#!/usr/bin/env python3
"""Zentraler Orchestrator fuer Road-to-know-where.

Der Orchestrator nimmt Frontend-Daten entgegen, ruft die passenden Agents auf
und baut daraus eine HTML-faehige Datenstruktur. Die Agent-Dateien bleiben
bewusst eigenstaendig; diese Datei koordiniert nur die Uebergaben.
"""

import argparse
import importlib.util
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_FUEL_TYPE = "e5"


def lade_agent_modul(dateiname: str, modulname: str) -> ModuleType:
    """Laedt auch Agent-Dateien mit Leerzeichen oder Sonderzeichen im Namen."""
    pfad = PROJECT_DIR / dateiname
    spec = importlib.util.spec_from_file_location(modulname, pfad)
    if spec is None or spec.loader is None:
        raise ImportError(f"Agent-Modul konnte nicht geladen werden: {pfad}")

    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


tankstelle_agent = lade_agent_modul("Tankstelle MR.py", "tankstelle_agent")
maps_poi_agent = lade_agent_modul("maps&poi.py", "maps_poi_agent")
wetter_agent = lade_agent_modul("wetter_agent.py", "wetter_agent")


def json_bytes(daten: Any) -> int:
    """Misst die Groesse einer Datenstruktur als UTF-8-JSON."""
    return len(json.dumps(daten, ensure_ascii=False, default=str).encode("utf-8"))


def schaetze_tokens(daten: Any) -> int:
    """Sehr grobe Token-Schaetzung: ca. 4 Zeichen pro Token."""
    text = json.dumps(daten, ensure_ascii=False, default=str)
    return math.ceil(len(text) / 4)


@dataclass
class AgentMessung:
    """Telemetrie fuer einen einzelnen Agent-Aufruf."""

    agent: str
    laufzeit_sekunden: float
    input_bytes: int
    output_bytes: int
    status: str
    fehler: Optional[str] = None


@dataclass
class Telemetrie:
    """Einfache interne Telemetrie fuer Uni-Auswertung und Debugging."""

    startzeit: float = field(default_factory=time.perf_counter)
    agent_aufrufe: int = 0
    funktionsaufrufe: int = 0
    agent_messungen: List[AgentMessung] = field(default_factory=list)
    fehler: List[Dict[str, str]] = field(default_factory=list)

    def agent_starten(
        self,
        agent_name: str,
        funktion: Callable[..., Any],
        payload: Dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Ruft einen Agent auf, misst Laufzeit und sammelt Fehler zentral."""
        self.agent_aufrufe += 1
        start = time.perf_counter()

        try:
            ergebnis = funktion(*args, **kwargs)
            self.agent_messungen.append(
                AgentMessung(
                    agent=agent_name,
                    laufzeit_sekunden=time.perf_counter() - start,
                    input_bytes=json_bytes(payload),
                    output_bytes=json_bytes(ergebnis),
                    status="ok",
                )
            )
            return ergebnis
        except Exception as fehler:  # Agenten duerfen den ganzen Plan nicht sprengen.
            meldung = str(fehler)
            self.fehler.append({"agent": agent_name, "meldung": meldung})
            self.agent_messungen.append(
                AgentMessung(
                    agent=agent_name,
                    laufzeit_sekunden=time.perf_counter() - start,
                    input_bytes=json_bytes(payload),
                    output_bytes=0,
                    status="error",
                    fehler=meldung,
                )
            )
            return None

    def zusammenfassung(self, eingabe: Any, ausgabe: Any) -> Dict[str, Any]:
        """Erstellt eine kompakte, frontend- und report-taugliche Auswertung."""
        geschaetzte_payload_tokens = schaetze_tokens(eingabe) + schaetze_tokens(ausgabe)
        return {
            "laufzeit_sekunden": round(time.perf_counter() - self.startzeit, 4),
            "agent_aufrufe": self.agent_aufrufe,
            "funktionsaufrufe": self.funktionsaufrufe,
            "input_bytes": json_bytes(eingabe),
            "output_bytes": json_bytes(ausgabe),
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "llm_total_tokens": 0,
            "token_hinweis": "Keine LLM-Aufrufe gefunden; Werte sind 0. Payload-Tokens sind geschaetzt.",
            "geschaetzte_payload_tokens": geschaetzte_payload_tokens,
            "agent_messungen": [messung.__dict__ for messung in self.agent_messungen],
            "fehler": self.fehler,
        }


def normalisiere_frontend_input(frontend_input: Dict[str, Any]) -> Dict[str, Any]:
    """Setzt Defaults und haelt nur die Werte, die der Orchestrator braucht."""
    start_location = str(frontend_input.get("start_location") or frontend_input.get("city") or "Berlin").strip()
    theme = str(frontend_input.get("theme") or "Städte").strip()
    duration_days = max(1, int(frontend_input.get("duration_days", 3)))
    travel_time_per_day = max(1, int(frontend_input.get("travel_time_per_day", 6)))
    fuel_type = str(frontend_input.get("fuel_type") or DEFAULT_FUEL_TYPE).strip().lower()
    start_date = str(frontend_input.get("start_date") or date.today().isoformat())

    return {
        "start_location": start_location,
        "theme": theme,
        "duration_days": duration_days,
        "travel_time_per_day": travel_time_per_day,
        "fuel_type": fuel_type,
        "start_date": start_date,
    }


def payload_fuer_route(reise_input: Dict[str, Any]) -> Dict[str, Any]:
    """Gibt dem Maps/POI-Agent nur die Routenparameter, nicht den ganzen Input."""
    return {
        "start_location": reise_input["start_location"],
        "theme": reise_input["theme"],
        "duration_days": reise_input["duration_days"],
        "travel_time_per_day": reise_input["travel_time_per_day"],
    }


def baue_wetter_etappen(plan: Dict[str, Any], startdatum_text: str, dauer_tage: int) -> List[Dict[str, Any]]:
    """Wandelt Route-Stops in die schlanke Wetter-Agent-Schnittstelle um."""
    route_stops = plan.get("route_stops") or []
    daily_plan = plan.get("daily_plan") or []
    if len(route_stops) < 1:
        return []

    startdatum = datetime.strptime(startdatum_text, "%Y-%m-%d").date()
    etappen = []
    stop_lookup = {stop["name"]: stop for stop in route_stops}
    letzter_stop = route_stops[0]

    for index in range(1, dauer_tage + 1):
        tag_plan = daily_plan[index - 1] if index - 1 < len(daily_plan) else {}
        zielname = tag_plan.get("destination")
        ziel = stop_lookup.get(zielname) if zielname else None

        if ziel is None and index < len(route_stops):
            ziel = route_stops[index]
        if ziel is None:
            ziel = letzter_stop

        etappen.append(
            {
                "tag": index,
                "datum": (startdatum + timedelta(days=index - 1)).isoformat(),
                "startort": letzter_stop["name"],
                "zielort": ziel["name"],
                "ziel_lat": ziel["lat"],
                "ziel_lon": ziel["lng"],
            }
        )
        letzter_stop = ziel

    return etappen


def erstelle_fallback_wetter_kachel(reise_input: Dict[str, Any], route_plan: Optional[Dict[str, Any]], meldung: str) -> Dict[str, Any]:
    """Erstellt eine vollstaendige Wetter-Kachel, wenn der Wetter-Agent ausfaellt."""
    route_stops = (route_plan or {}).get("route_stops") or [{"name": reise_input["start_location"]}]
    ort = route_stops[-1].get("name", reise_input["start_location"])
    return {
        "titel": "Wetterprognose fuer deine Reise",
        "datenbasis": "fallback_estimate",
        "temperaturspanne": {
            "temperatur_min": None,
            "temperatur_max": None,
            "text": "Keine belastbaren Temperaturwerte verfuegbar",
        },
        "anzahl_regentage": 0,
        "kritischster_tag": {
            "tag": None,
            "datum": None,
            "ort": ort,
            "grund": "Wetterdaten konnten nur als Fallback bewertet werden",
        },
        "gesamtbewertung": f"Wetterdaten wurden als Fallback ausgegeben: {meldung}",
        "wetter_risiko": "mittel",
        "packempfehlung": "Plane wetterflexibel: Regenjacke, warme Schicht und bequeme Schuhe einpacken.",
        "tagesuebersicht": [],
    }


def normalisiere_wetter_kachel(wetter_kachel: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sichert Pflichtfelder und einfache Aliasnamen fuer Frontend und Tests ab."""
    daten = dict(wetter_kachel or {})
    temperaturspanne = daten.get("temperaturspanne") or {
        "temperatur_min": None,
        "temperatur_max": None,
        "text": "Keine belastbaren Temperaturwerte verfuegbar",
    }
    anzahl_regentage = daten.get("anzahl_regentage", daten.get("regentage", 0))
    wetter_risiko = daten.get("wetter_risiko", daten.get("risiko", "mittel"))
    kritischster_tag = daten.get("kritischster_tag") or {
        "tag": None,
        "datum": None,
        "ort": "Route",
        "grund": "Keine kritischen Wetterdaten erkannt",
    }

    daten["titel"] = daten.get("titel") or "Wetterprognose fuer deine Reise"
    daten["datenbasis"] = daten.get("datenbasis") or "fallback_estimate"
    daten["temperaturspanne"] = temperaturspanne
    daten["anzahl_regentage"] = anzahl_regentage
    daten["regentage"] = anzahl_regentage
    daten["kritischster_tag"] = kritischster_tag
    daten["wetter_risiko"] = wetter_risiko
    daten["risiko"] = wetter_risiko
    daten["packempfehlung"] = daten.get("packempfehlung") or (
        "Plane wetterflexibel: Regenjacke, warme Schicht und bequeme Schuhe einpacken."
    )
    daten["tagesuebersicht"] = daten.get("tagesuebersicht") or []
    return daten


def baue_frontend_output(
    reise_input: Dict[str, Any],
    route_plan: Optional[Dict[str, Any]],
    wetter_kachel: Optional[Dict[str, Any]],
    tankstelle: Optional[Dict[str, Any]],
    telemetrie: Telemetrie,
) -> Dict[str, Any]:
    """Fuehrt Agent-Ergebnisse zu einer stabilen Ausgabe fuer das Frontend zusammen."""
    route_plan = route_plan or {}
    frontend_plan = {
        **route_plan,
        "weather": normalisiere_wetter_kachel(wetter_kachel),
        "fuel_summary": tankstelle,
        "errors": telemetrie.fehler,
    }

    return {
        "status": "ok" if not telemetrie.fehler else "partial",
        "input": reise_input,
        "frontend_plan": frontend_plan,
    }


def orchestrate_trip(frontend_input: Dict[str, Any], include_telemetry: bool = False) -> Dict[str, Any]:
    """Hauptfunktion fuer das Frontend: komplette Roadtrip-Planung koordinieren."""
    telemetrie = Telemetrie()
    reise_input = normalisiere_frontend_input(frontend_input)

    route_payload = payload_fuer_route(reise_input)
    route_plan = telemetrie.agent_starten(
        "maps_poi",
        maps_poi_agent.plan_trip,
        route_payload,
        route_payload,
    )

    wetter_kachel = None
    if route_plan:
        wetter_etappen = baue_wetter_etappen(
            route_plan,
            reise_input["start_date"],
            reise_input["duration_days"],
        )
        if wetter_etappen:
            wetter_kachel = telemetrie.agent_starten(
                "wetter",
                wetter_agent.erstelle_wetter_kachel,
                {"reise_etappen": wetter_etappen},
                wetter_etappen,
            )
    if wetter_kachel is None:
        wetter_kachel = erstelle_fallback_wetter_kachel(
            reise_input,
            route_plan,
            "Der Wetter-Agent hat keine Daten geliefert.",
        )

    tank_payload = {
        "city": reise_input["start_location"],
        "fuel_type": reise_input["fuel_type"],
    }
    tankstelle = telemetrie.agent_starten(
        "tankstelle",
        tankstelle_agent.cheapest_station,
        tank_payload,
        reise_input["start_location"],
        reise_input["fuel_type"],
    )

    ausgabe = baue_frontend_output(
        reise_input=reise_input,
        route_plan=route_plan,
        wetter_kachel=wetter_kachel,
        tankstelle=tankstelle,
        telemetrie=telemetrie,
    )

    if include_telemetry:
        ausgabe["telemetry"] = telemetrie.zusammenfassung(reise_input, ausgabe)

    return ausgabe


def orchestrate(city: str, fuel_type: str = DEFAULT_FUEL_TYPE, include_telemetry: bool = False) -> Dict[str, Any]:
    """Rueckwaertskompatibler Mini-Orchestrator fuer die alte Konsolen-Nutzung."""
    telemetrie = Telemetrie()
    eingabe = {"city": city, "fuel_type": fuel_type}
    tankstelle = telemetrie.agent_starten(
        "tankstelle",
        tankstelle_agent.cheapest_station,
        eingabe,
        city,
        fuel_type,
    )
    ausgabe = {
        "city": city,
        "gas_station": tankstelle,
        "errors": telemetrie.fehler,
    }

    if include_telemetry:
        ausgabe["telemetry"] = telemetrie.zusammenfassung(eingabe, ausgabe)

    return ausgabe


def beispiel_testdatensatz() -> Dict[str, Any]:
    """Kleiner 3-Tage-Datensatz fuer reproduzierbare Orchestrator-Tests."""
    return {
        "start_location": "München",
        "theme": "Städte",
        "duration_days": 3,
        "travel_time_per_day": 6,
        "fuel_type": "e5",
        "start_date": "2026-06-06",
    }


def zaehle_projekt_funktionsaufrufe(funktion: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Zaehlt Funktionsaufrufe aus Projektdateien per Python-Profiler."""
    zaehler = {"calls": 0}
    projekt_pfad = str(PROJECT_DIR)

    def profiler(frame: Any, event: str, arg: Any) -> Any:
        if event == "call" and os.path.abspath(frame.f_code.co_filename).startswith(projekt_pfad):
            zaehler["calls"] += 1
        return profiler

    vorheriger_profiler = sys.getprofile()
    sys.setprofile(profiler)
    try:
        ergebnis = funktion()
    finally:
        sys.setprofile(vorheriger_profiler)

    if "telemetry" in ergebnis:
        ergebnis["telemetry"]["funktionsaufrufe"] = zaehler["calls"]
    return ergebnis


def testlauf_roadtrip() -> Dict[str, Any]:
    """Fuehrt den 3-Tage-Beispieltest inklusive Telemetrie aus."""
    return zaehle_projekt_funktionsaufrufe(
        lambda: orchestrate_trip(beispiel_testdatensatz(), include_telemetry=True)
    )


def testlauf_legacy(city: str = "München", fuel_type: str = DEFAULT_FUEL_TYPE) -> Dict[str, Any]:
    """Fuehrt denselben Mini-Test wie der alte Orchestrator aus."""
    return zaehle_projekt_funktionsaufrufe(
        lambda: orchestrate(city, fuel_type=fuel_type, include_telemetry=True)
    )


def drucke_json(daten: Dict[str, Any]) -> None:
    print(json.dumps(daten, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Road-to-know-where Orchestrator")
    parser.add_argument("--test", action="store_true", help="3-Tage-Testdatensatz mit Telemetrie ausfuehren")
    parser.add_argument("--city", help="Alten Mini-Orchestrator fuer eine Stadt ausfuehren")
    parser.add_argument("--fuel-type", default=DEFAULT_FUEL_TYPE, help="Kraftstoffart: e5, e10 oder diesel")
    args = parser.parse_args()

    if args.test:
        drucke_json(testlauf_roadtrip())
        return

    city = args.city or input("Welche Stadt? ").strip()
    drucke_json(testlauf_legacy(city, args.fuel_type))


if __name__ == "__main__":
    main()
