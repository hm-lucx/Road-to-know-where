#!/usr/bin/env python3
"""Automatische Telemetrieanalyse fuer den Road-to-know-where Orchestrator.

Das Skript fuehrt mehrere Orchestrator-Testlaeufe aus, erstellt Diagramme mit
matplotlib und baut daraus einen HTML-Report fuer die Uni-Auswertung.
"""

import html
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_PATH = PROJECT_DIR / "Orchestrat MR.py"
OLD_REPORT_PATH = PROJECT_DIR / "telemetry_report.md"
CHART_DIR = PROJECT_DIR / "telemetry_charts"
HTML_REPORT_PATH = PROJECT_DIR / "orchestrator_test_report.html"
RAW_DATA_PATH = PROJECT_DIR / "telemetry_runs.json"


def lade_matplotlib():
    """Laedt matplotlib erst bei Bedarf und zeigt sonst eine hilfreiche Meldung."""
    try:
        CHART_DIR.mkdir(exist_ok=True)
        cache_dir = Path(tempfile.gettempdir()) / "road_to_know_where_matplotlib"
        os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ModuleNotFoundError as fehler:
        print("matplotlib ist nicht installiert.")
        print("Installation:")
        print("  python3 -m pip install matplotlib")
        raise SystemExit(1) from fehler


def lade_orchestrator():
    """Importiert den Orchestrator trotz Leerzeichen im Dateinamen."""
    spec = importlib.util.spec_from_file_location("road_orchestrator", ORCHESTRATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Orchestrator konnte nicht geladen werden: {ORCHESTRATOR_PATH}")

    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def json_text(daten: Any) -> str:
    return json.dumps(daten, ensure_ascii=False, default=str)


def json_bytes(daten: Any) -> int:
    return len(json_text(daten).encode("utf-8"))


def schaetze_tokens(daten: Any) -> int:
    """Schaetzt Tokens ueber die einfache Faustregel: 1 Token ~= 4 Zeichen."""
    return math.ceil(len(json_text(daten)) / 4)


def basis_input(reisetage: int) -> Dict[str, Any]:
    """Erzeugt denselben Testdatensatz mit unterschiedlicher Reisedauer."""
    return {
        "start_location": "München",
        "theme": "Städte",
        "duration_days": reisetage,
        "travel_time_per_day": 6,
        "fuel_type": "e5",
        "start_date": "2026-06-06",
    }


def zaehle_funktionsaufrufe(funktion):
    """Zaehlt Projekt-Funktionsaufrufe mit dem Python-Profiler."""
    zaehler = {"calls": 0}
    projekt_pfad = str(PROJECT_DIR)
    alter_profiler = sys.getprofile()

    def profiler(frame, event, arg):
        if event == "call" and str(Path(frame.f_code.co_filename).resolve()).startswith(projekt_pfad):
            zaehler["calls"] += 1
        return profiler

    sys.setprofile(profiler)
    try:
        ergebnis = funktion()
    finally:
        sys.setprofile(alter_profiler)

    return ergebnis, zaehler["calls"]


def fuehre_szenario_aus(orchestrator, reisetage: int) -> Dict[str, Any]:
    """Fuehrt einen Orchestrator-Lauf aus und extrahiert die Telemetrie."""
    eingabe = basis_input(reisetage)
    start = time.perf_counter()
    fehler = None

    try:
        ergebnis, funktionsaufrufe = zaehle_funktionsaufrufe(
            lambda: orchestrator.orchestrate_trip(eingabe, include_telemetry=True)
        )
    except Exception as exc:
        ergebnis = {"status": "error", "error": str(exc)}
        funktionsaufrufe = 0
        fehler = str(exc)

    laufzeit = time.perf_counter() - start
    telemetry = ergebnis.get("telemetry", {})
    plan = ergebnis.get("frontend_plan", {})
    agent_messungen = telemetry.get("agent_messungen", [])
    output_bytes = telemetry.get("output_bytes", json_bytes(ergebnis))
    input_bytes = telemetry.get("input_bytes", json_bytes(eingabe))

    # Es gibt aktuell keine LLM-Aufrufe. Fuer die Report-Grafik schaetzen wir
    # den Datenumfang trotzdem als Tokennaeherung, damit Skalierung sichtbar wird.
    prompt_tokens = schaetze_tokens(eingabe)
    completion_tokens = max(0, schaetze_tokens(ergebnis) - prompt_tokens)
    total_tokens = prompt_tokens + completion_tokens

    return {
        "reisetage": reisetage,
        "status": ergebnis.get("status", "unknown"),
        "laufzeit_sekunden": round(float(telemetry.get("laufzeit_sekunden", laufzeit)), 4),
        "agent_aufrufe": int(telemetry.get("agent_aufrufe", len(agent_messungen))),
        "funktionsaufrufe": int(telemetry.get("funktionsaufrufe") or funktionsaufrufe),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tokens_sind_geschaetzt": True,
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "agent_messungen": agent_messungen,
        "route_stops": len(plan.get("route_stops", [])),
        "daily_plan_days": len(plan.get("daily_plan", [])),
        "poi_count": len(plan.get("pois", [])),
        "weather_days": len((plan.get("weather") or {}).get("tagesuebersicht", [])),
        "errors": telemetry.get("fehler", []),
        "error": fehler,
        "result": ergebnis,
    }


def parse_float(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def lese_vorher_nachher_daten() -> Optional[Dict[str, float]]:
    """Liest vorhandene Vorher-/Nachher-Werte aus telemetry_report.md."""
    if not OLD_REPORT_PATH.exists():
        return None

    text = OLD_REPORT_PATH.read_text(encoding="utf-8")
    laufzeit = re.search(r"\| Laufzeit \| ([0-9.]+) s \| ([0-9.]+) s \|", text)
    tokens = re.search(r"\| Geschätzte Payload-Tokens \| ([0-9.]+) \| ([0-9.]+) \|", text)

    if not laufzeit and not tokens:
        return None

    daten: Dict[str, float] = {}
    if laufzeit:
        daten["runtime_before"] = parse_float(laufzeit.group(1)) or 0.0
        daten["runtime_after"] = parse_float(laufzeit.group(2)) or 0.0
    if tokens:
        daten["tokens_before"] = parse_float(tokens.group(1)) or 0.0
        daten["tokens_after"] = parse_float(tokens.group(2)) or 0.0
    return daten


def speichere_liniendiagramm(plt, xwerte, ywerte, titel, ylabel, dateiname):
    plt.figure(figsize=(8, 4.8))
    plt.plot(xwerte, ywerte, marker="o", linewidth=2.2, color="#1f77b4")
    plt.title(titel)
    plt.xlabel("Anzahl Reisetage")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.3)
    plt.xticks(xwerte)
    plt.tight_layout()
    pfad = CHART_DIR / dateiname
    plt.savefig(pfad, dpi=150)
    plt.close()
    return pfad


def speichere_balkendiagramm(plt, labels, werte, titel, ylabel, dateiname, farben=None):
    plt.figure(figsize=(7, 4.8))
    plt.bar(labels, werte, color=farben or ["#4c78a8", "#f58518"])
    plt.title(titel)
    plt.ylabel(ylabel)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    pfad = CHART_DIR / dateiname
    plt.savefig(pfad, dpi=150)
    plt.close()
    return pfad


def speichere_agent_stapel(plt, messwerte: List[Dict[str, Any]]):
    """Erzeugt ein gestapeltes Diagramm fuer Agent-Laufzeiten."""
    agenten = sorted(
        {
            messung["agent"]
            for lauf in messwerte
            for messung in lauf.get("agent_messungen", [])
        }
    )
    tage = [lauf["reisetage"] for lauf in messwerte]
    bottoms = [0.0 for _ in tage]
    farben = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]

    plt.figure(figsize=(8, 4.8))
    for index, agent in enumerate(agenten):
        werte = []
        for lauf in messwerte:
            agent_summe = sum(
                float(messung.get("laufzeit_sekunden", 0))
                for messung in lauf.get("agent_messungen", [])
                if messung.get("agent") == agent
            )
            werte.append(agent_summe)
        plt.bar([str(tag) for tag in tage], werte, bottom=bottoms, label=agent, color=farben[index % len(farben)])
        bottoms = [unten + wert for unten, wert in zip(bottoms, werte)]

    plt.title("Laufzeitanteile je Agent")
    plt.xlabel("Anzahl Reisetage")
    plt.ylabel("Laufzeit in Sekunden")
    plt.grid(axis="y", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    pfad = CHART_DIR / "agent_runtime_stacked.png"
    plt.savefig(pfad, dpi=150)
    plt.close()
    return pfad


def erzeuge_diagramme(messwerte: List[Dict[str, Any]], vorher_nachher: Optional[Dict[str, float]]) -> List[Path]:
    """Erstellt alle PNG-Diagramme im Ordner telemetry_charts."""
    plt = lade_matplotlib()
    CHART_DIR.mkdir(exist_ok=True)

    tage = [lauf["reisetage"] for lauf in messwerte]
    charts = [
        speichere_liniendiagramm(
            plt,
            tage,
            [lauf["laufzeit_sekunden"] for lauf in messwerte],
            "Laufzeitvergleich nach Reisetagen",
            "Laufzeit in Sekunden",
            "runtime_by_days.png",
        ),
        speichere_liniendiagramm(
            plt,
            tage,
            [lauf["total_tokens"] for lauf in messwerte],
            "Geschätzter Tokenverbrauch nach Reisetagen",
            "Gesamt-Tokens (geschätzt)",
            "tokens_by_days.png",
        ),
        speichere_agent_stapel(plt, messwerte),
    ]

    if vorher_nachher:
        if "tokens_before" in vorher_nachher and "tokens_after" in vorher_nachher:
            charts.append(
                speichere_balkendiagramm(
                    plt,
                    ["Vorher", "Nachher"],
                    [vorher_nachher["tokens_before"], vorher_nachher["tokens_after"]],
                    "Vorher-/Nachher-Vergleich Token-Nutzung",
                    "Payload-Tokens (geschätzt)",
                    "before_after_tokens.png",
                )
            )
        if "runtime_before" in vorher_nachher and "runtime_after" in vorher_nachher:
            charts.append(
                speichere_balkendiagramm(
                    plt,
                    ["Vorher", "Nachher"],
                    [vorher_nachher["runtime_before"], vorher_nachher["runtime_after"]],
                    "Vorher-/Nachher-Vergleich Laufzeit",
                    "Laufzeit in Sekunden",
                    "before_after_runtime.png",
                    farben=["#e45756", "#54a24b"],
                )
            )

    return charts


def format_sekunden(wert: float) -> str:
    return f"{wert:.4f}"


def html_tabelle_messwerte(messwerte: List[Dict[str, Any]]) -> str:
    zeilen = []
    for lauf in messwerte:
        zeilen.append(
            "<tr>"
            f"<td>{lauf['reisetage']}</td>"
            f"<td>{format_sekunden(lauf['laufzeit_sekunden'])}</td>"
            f"<td>{lauf['agent_aufrufe']}</td>"
            f"<td>{lauf['funktionsaufrufe']}</td>"
            f"<td>{lauf['total_tokens']} <span class=\"muted\">geschätzt</span></td>"
            f"<td>{lauf['input_bytes']}</td>"
            f"<td>{lauf['output_bytes']}</td>"
            f"<td>{lauf['daily_plan_days']}</td>"
            f"<td>{lauf['weather_days']}</td>"
            f"<td>{html.escape(lauf['status'])}</td>"
            "</tr>"
        )
    return "\n".join(zeilen)


def html_agent_tabelle(messwerte: List[Dict[str, Any]]) -> str:
    zeilen = []
    for lauf in messwerte:
        for messung in lauf.get("agent_messungen", []):
            zeilen.append(
                "<tr>"
                f"<td>{lauf['reisetage']}</td>"
                f"<td>{html.escape(str(messung.get('agent', '')))}</td>"
                f"<td>{format_sekunden(float(messung.get('laufzeit_sekunden', 0)))}</td>"
                f"<td>{messung.get('input_bytes', 0)}</td>"
                f"<td>{messung.get('output_bytes', 0)}</td>"
                f"<td>{html.escape(str(messung.get('status', '')))}</td>"
                "</tr>"
            )
    return "\n".join(zeilen)


def chart_img(path: Path, alt: str) -> str:
    rel = path.relative_to(PROJECT_DIR)
    return f'<figure><img src="{html.escape(str(rel))}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>'


def liste_items(items: List[str]) -> str:
    return "".join(f"<li>{html.escape(str(item))}</li>" for item in items)


def erzeuge_roadtrip_html(plan: Dict[str, Any]) -> str:
    """Baut eine einfache HTML-Ausgabe fuer den Funktionstest."""
    eingabe = plan.get("input", {})
    frontend_plan = plan.get("frontend_plan", {})
    weather = frontend_plan.get("weather") or {}
    fuel = frontend_plan.get("fuel_summary") or {}
    route = frontend_plan.get("daily_plan", [])
    pois = frontend_plan.get("pois", [])

    route_items = liste_items([f"{tag.get('day')}: {tag.get('activities')}" for tag in route])
    weather_items = liste_items(
        [
            f"Datenbasis: {weather.get('datenbasis', 'n/a')}",
            f"Temperaturspanne: {(weather.get('temperaturspanne') or {}).get('text', 'n/a')}",
            f"Wetterrisiko: {weather.get('wetter_risiko', 'n/a')}",
            f"Packempfehlung: {weather.get('packempfehlung', 'n/a')}",
        ]
    )
    fuel_items = liste_items(
        [
            f"Tankstelle: {fuel.get('name', 'nicht verfügbar')}",
            f"Preis: {fuel.get('price', 'n/a')} €/L",
            f"Entfernung: {fuel.get('distance_km', 'n/a')} km",
            f"Adresse: {fuel.get('address', 'n/a')}",
        ]
    )
    poi_items = liste_items(
        [
            f"{poi.get('name')} in {poi.get('location')}: {poi.get('description')}"
            for poi in pois[:10]
        ]
    )

    return f"""
    <section>
      <h2>Funktionstest: Beispiel-Roadtrip</h2>
      <p>Dieser Abschnitt zeigt, dass der Orchestrator eine HTML-fähige Ausgabe für das Frontend erzeugt.</p>
      <h3>Nutzereingaben</h3>
      <ul>
        <li>Startort: {html.escape(str(eingabe.get('start_location', '')))}</li>
        <li>Thema: {html.escape(str(eingabe.get('theme', '')))}</li>
        <li>Reisetage: {html.escape(str(eingabe.get('duration_days', '')))}</li>
        <li>Kraftstoff: {html.escape(str(eingabe.get('fuel_type', '')))}</li>
      </ul>
      <h3>Geplante Tagesetappen</h3>
      <ol>{route_items}</ol>
      <h3>Wetter-Kachel</h3>
      <ul>{weather_items}</ul>
      <h3>Tank-/Kosteninformationen</h3>
      <ul>{fuel_items}</ul>
      <h3>POI-Informationen</h3>
      <ul>{poi_items}</ul>
      <h3>Finale Zusammenfassung</h3>
      <p>{html.escape(str(weather.get('gesamtbewertung', 'Keine Zusammenfassung verfügbar.')))}</p>
    </section>
    """


def bewerte_trends(messwerte: List[Dict[str, Any]], vorher_nachher: Optional[Dict[str, float]]) -> str:
    erster = messwerte[0]
    letzter = messwerte[-1]
    runtime_delta = letzter["laufzeit_sekunden"] - erster["laufzeit_sekunden"]
    token_delta = letzter["total_tokens"] - erster["total_tokens"]

    optimierung = "Vorher-/Nachher-Daten wurden gefunden und im Report visualisiert."
    if vorher_nachher and "runtime_before" in vorher_nachher and "runtime_after" in vorher_nachher:
        veraenderung = vorher_nachher["runtime_after"] - vorher_nachher["runtime_before"]
        optimierung += f" Der frühere Mini-Test veränderte sich um {veraenderung:.4f} Sekunden."
    elif not vorher_nachher:
        optimierung = "Es wurden keine Vorher-/Nachher-Daten gefunden."

    return f"""
    <section>
      <h2>Interpretation</h2>
      <p>Bei mehr Reisetagen verändert sich die Laufzeit um {runtime_delta:.4f} Sekunden zwischen dem kleinsten und größten Szenario. Da externe APIs beteiligt sind, schwankt dieser Wert auch durch Netzwerk und Antwortzeiten.</p>
      <p>Der geschätzte Tokenverbrauch verändert sich um {token_delta} Tokens. Es handelt sich ausdrücklich um eine Schätzung über Textlänge: ungefähr 1 Token pro 4 Zeichen. Echte LLM-Tokens liegen nicht vor, weil aktuell keine LLM-API im Orchestrator genutzt wird.</p>
      <p>{html.escape(optimierung)}</p>
      <p>Technische Schlussfolgerung: Der Orchestrator ist jetzt messbar und erzeugt strukturierte Frontend-Daten. Die Agent-Laufzeiten zeigen, welche Teile bei späteren Optimierungen zuerst betrachtet werden sollten.</p>
      <p>Grenzen der Messwerte: API-Latenzen, Tagesdaten beim Wetter, Tankstellenpreise und OSRM-Fallbacks können Ergebnisse verändern. Für wissenschaftlich stabilere Messungen wären mehrere Wiederholungen und API-Mocking sinnvoll.</p>
    </section>
    """


def erzeuge_html_report(
    messwerte: List[Dict[str, Any]],
    charts: List[Path],
    vorher_nachher: Optional[Dict[str, float]],
    beispiel_result: Dict[str, Any],
) -> None:
    chart_html = "\n".join(chart_img(path, path.stem.replace("_", " ")) for path in charts)
    before_after_text = "Vorher-/Nachher-Daten aus telemetry_report.md wurden gefunden."
    if not vorher_nachher:
        before_after_text = "Es wurden keine Vorher-/Nachher-Daten gefunden."

    dokument = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Road-to-know-where – Orchestrator Test Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; line-height: 1.5; color: #222; background: #f6f7f9; }}
    header {{ background: #18324a; color: white; padding: 28px 36px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; background: white; }}
    h1, h2, h3 {{ margin-top: 0; }}
    section {{ margin-bottom: 32px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 14px 0 24px; font-size: 14px; }}
    th, td {{ border: 1px solid #d8dee6; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    img {{ max-width: 100%; border: 1px solid #d8dee6; background: white; }}
    figure {{ margin: 0 0 24px; }}
    figcaption {{ font-size: 13px; color: #555; margin-top: 6px; }}
    .muted {{ color: #666; font-size: 12px; }}
    .notice {{ background: #fff7db; border: 1px solid #e8cf7a; padding: 12px 14px; }}
  </style>
</head>
<body>
  <header>
    <h1>Road-to-know-where – Orchestrator Test Report</h1>
  </header>
  <main>
    <section>
      <h2>Überblick</h2>
      <p>Getestet wurde der aktuelle Orchestrator mit automatisierten Roadtrip-Szenarien für 1, 3, 5 und 7 Reisetage. Für alle Szenarien wurden dieselben Nutzereingaben verwendet; nur die Reisedauer wurde verändert.</p>
      <p>Erhoben wurden Laufzeit, Agent-Aufrufe, Funktionsaufrufe, Agent-Laufzeiten, Eingabe- und Ausgabegrößen sowie geschätzte Tokenwerte.</p>
      <p class="notice">Tokenhinweis: Es wurden keine echten LLM-Token gemessen. Die Werte sind <strong>geschätzt</strong> mit der Regel: ungefähr 1 Token pro 4 Zeichen.</p>
      <p>{html.escape(before_after_text)}</p>
    </section>

    <section>
      <h2>Messwerte</h2>
      <table>
        <thead>
          <tr>
            <th>Reisetage</th>
            <th>Laufzeit (s)</th>
            <th>Agent-Aufrufe</th>
            <th>Funktionsaufrufe</th>
            <th>Gesamt-Tokens</th>
            <th>Input-Größe (Bytes)</th>
            <th>Output-Größe (Bytes)</th>
            <th>Plan-Tage</th>
            <th>Wettertage</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {html_tabelle_messwerte(messwerte)}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Agent-Laufzeiten</h2>
      <table>
        <thead>
          <tr>
            <th>Reisetage</th>
            <th>Agent</th>
            <th>Laufzeit (s)</th>
            <th>Input Bytes</th>
            <th>Output Bytes</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {html_agent_tabelle(messwerte)}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Diagramme</h2>
      {chart_html}
    </section>

    {bewerte_trends(messwerte, vorher_nachher)}
    {erzeuge_roadtrip_html(beispiel_result)}
  </main>
</body>
</html>
"""
    HTML_REPORT_PATH.write_text(dokument, encoding="utf-8")


def main() -> None:
    print("Starte Orchestrator-Telemetrieanalyse...")
    orchestrator = lade_orchestrator()
    vorher_nachher = lese_vorher_nachher_daten()

    messwerte = []
    for reisetage in [1, 3, 5, 7]:
        print(f"- Testlauf fuer {reisetage} Reisetag(e)")
        messwerte.append(fuehre_szenario_aus(orchestrator, reisetage))

    RAW_DATA_PATH.write_text(json.dumps(messwerte, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    charts = erzeuge_diagramme(messwerte, vorher_nachher)

    beispiel_result = next((lauf["result"] for lauf in messwerte if lauf["reisetage"] == 3), messwerte[0]["result"])
    erzeuge_html_report(messwerte, charts, vorher_nachher, beispiel_result)

    print()
    print("Erzeugte Dateien:")
    print(f"- {RAW_DATA_PATH.name}")
    print(f"- {CHART_DIR.name}/")
    for chart in charts:
        print(f"  - {chart.relative_to(PROJECT_DIR)}")
    print(f"- {HTML_REPORT_PATH.name}")
    print()
    print("Report im Browser öffnen:")
    print(f"  {HTML_REPORT_PATH.resolve()}")


if __name__ == "__main__":
    main()
