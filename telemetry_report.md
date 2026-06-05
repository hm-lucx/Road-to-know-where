# Telemetry Report: Road-to-know-where Orchestrator

Datum des Testlaufs: 2026-06-05

## Phase 1: Analyse und Baseline

Die ursprüngliche Orchestrator-Datei war `Orchestrat MR.py`. Sie hat aktuell nur den
Tankstellen-Agent angebunden und ruft `cheapest_station(city, fuel_type)` aus
`Tankstelle MR.py` auf. Wetter und Sehenswürdigkeiten waren im Code nur als spätere
Phasen kommentiert.

Angebundene Agents im Projekt:

| Agent-Datei | Status im alten Orchestrator | Wichtige Übergabedaten |
| --- | --- | --- |
| `Tankstelle MR.py` | aktiv | `city`, `fuel_type` |
| `wetter_agent.py` | vorhanden, nicht angebunden | Reiseetappen mit `tag`, `datum`, `startort`, `zielort`, `ziel_lat`, `ziel_lon` |
| `maps&poi.py` | vorhanden, nicht angebunden | `start_location`, `theme`, `duration_days`, `travel_time_per_day` |

Baseline-Test mit `München` und `e5`:

| Metrik | Baseline |
| --- | ---: |
| Laufzeit | 0.8988 s |
| Agent-Aufrufe | 1 |
| Funktionsaufrufe | 504 |
| Eingabedaten | 39 Bytes |
| Ausgabedaten | 176 Bytes |
| LLM Prompt-Tokens | 0 |
| LLM Completion-Tokens | 0 |
| LLM Gesamt-Tokens | 0 |
| Geschätzte Payload-Tokens | 53 |

Hinweis: Im Projekt wurden keine LLM-/OpenAI-Aufrufe gefunden. Tokenwerte sind deshalb
für LLMs echte `0`; die Payload-Tokens sind nur eine grobe Schätzung auf Basis der
serialisierten JSON-Daten.

## Phase 2: Optimierung

Geändert wurde nur der Orchestrator. Die externen Agent-Dateien wurden nicht angepasst.

Verbesserungen:

| Bereich | Änderung |
| --- | --- |
| Struktur | Getrennte Funktionen für Frontend-Input, Agent-Payloads, Agent-Aufrufe und Frontend-Output |
| Agent-Anbindung | Neuer Roadtrip-Pfad mit Maps/POI, Wetter und Tankstelle |
| Rückwärtskompatibilität | `orchestrate(city, fuel_type)` bleibt als Mini-Orchestrator erhalten |
| Telemetrie | Interne `Telemetrie`-Klasse mit Laufzeit, Datenmengen, Agent-Messungen und Fehlern |
| Fehlerbehandlung | Agent-Fehler werden gesammelt; der Orchestrator kann Teilergebnisse zurückgeben |
| Datenweitergabe | Agents bekommen gezielte Payloads statt den kompletten Frontend-Input |
| Testdaten | `beispiel_testdatensatz()` erzeugt eine 3-tägige Reise ab München |

## Phase 3: Nachher-Test und Vergleich

Nachher-Test mit derselben Mini-Eingabe `München` und `e5`:

| Metrik | Vorher | Nachher | Veränderung |
| --- | ---: | ---: | ---: |
| Laufzeit | 0.8988 s | 0.5979 s | -33.48 % |
| Agent-Aufrufe | 1 | 1 | 0 % |
| Funktionsaufrufe | 504 | 516 | +2.38 % |
| Eingabedaten | 39 Bytes | 39 Bytes | 0 % |
| Ausgabedaten | 176 Bytes | 190 Bytes | +7.95 % |
| LLM Gesamt-Tokens | 0 | 0 | 0 % |
| Geschätzte Payload-Tokens | 53 | 57 | +7.55 % |

Die Nachher-Ausgabe ist etwas größer, weil der Orchestrator jetzt ein leeres
`errors`-Feld mitliefert. Das ist absichtlich so, damit das Frontend immer eine
stabile Fehlerstruktur bekommt.

Hinweis: Ein späterer Kontrolllauf nach der Import-Robustheitskorrektur lag bei
1.2348 s. Die Laufzeit hängt stark von externen APIs ab und sollte deshalb nicht
als isolierter Code-Effekt interpretiert werden.

Zusätzlicher 3-Tage-Roadtrip-Test:

| Metrik | Wert |
| --- | ---: |
| Laufzeit | 1.3429 s |
| Agent-Aufrufe | 3 |
| Funktionsaufrufe | 1085 |
| Eingabedaten | 143 Bytes |
| Ausgabedaten | 3769 Bytes |
| LLM Gesamt-Tokens | 0 |
| Geschätzte Payload-Tokens | 973 |

Agent-Aufteilung im 3-Tage-Test:

| Agent | Laufzeit | Input | Output | Status |
| --- | ---: | ---: | ---: | --- |
| Maps/POI | 0.0862 s | 96 Bytes | 2200 Bytes | ok |
| Wetter | 0.7062 s | 378 Bytes | 1196 Bytes | ok |
| Tankstelle | 0.5441 s | 39 Bytes | 139 Bytes | ok |

Datenreduktion durch gezielte Payloads im 3-Tage-Test:

| Agent | Statt komplettem Frontend-Input | Tatsächlicher Payload | Reduktion |
| --- | ---: | ---: | ---: |
| Maps/POI | 143 Bytes | 96 Bytes | -32.87 % |
| Tankstelle | 143 Bytes | 39 Bytes | -72.73 % |

Für den Wetter-Agent ist der Payload größer als der Frontend-Input, weil der
Orchestrator dort erst echte Etappen mit Koordinaten erzeugt. Das ist notwendige
Arbeitsinformation und keine unnötige Weitergabe.

## Bewertung

Verbessert wurde vor allem die Orchestrator-Rolle: Die Datei ist jetzt nicht mehr
nur ein Tankstellen-Aufruf, sondern eine zentrale Steuerungseinheit mit klarer
Eingabe-Normalisierung, Agent-Koordination, Fehlerbehandlung und strukturierter
Frontend-Ausgabe.

Nicht verändert wurden die Agent-Implementierungen selbst, die externe API-Nutzung
und die fachliche Logik der bestehenden Agent-Funktionen.

Weiteres Potenzial:

| Thema | Potenzial |
| --- | --- |
| API-Caching | Wetter- und Tankstellenantworten könnten für wiederholte Tests gecacht werden |
| HTML-Ausgabe | Der Orchestrator könnte optional `maps&poi.generate_html()` aufrufen |
| Tests | Ein separater Unit-Test ohne echte Web-APIs wäre stabiler für CI/Abgaben |
| OSRM-Transparenz | Der Maps-Agent verschluckt OSRM-Fehler aktuell intern; Telemetrie sieht nur den Fallback |

Risiken:

| Risiko | Einschätzung |
| --- | --- |
| Externe APIs | Laufzeiten und Ergebnisse können je nach Netz und Tagesdaten schwanken |
| Dateinamen mit Leerzeichen/Sonderzeichen | Dynamisches Laden funktioniert, ist aber empfindlicher als normale Python-Modulnamen |
| Frontend-Vertrag | Neue Ausgabe enthält mehr Struktur; Frontend muss `frontend_plan` lesen |

## Erneut ausführen

Mini-Test wie vorher:

```bash
python3 -B "Orchestrat MR.py" --city München --fuel-type e5
```

3-Tage-Roadtrip-Test mit Telemetrie:

```bash
python3 -B "Orchestrat MR.py" --test
```

Interpretation für die Uni-Auswertung: Die wichtigste Verbesserung ist nicht nur
die reine Laufzeit, sondern die Messbarkeit. Der Orchestrator macht jetzt sichtbar,
welcher Agent wie lange braucht, wie groß die Datenübergaben sind und ob ein Fehler
isoliert behandelt wurde. Dadurch kann das Team später gezielt optimieren, statt
nur subjektiv zu bewerten, ob die Anwendung "schnell genug" wirkt.
