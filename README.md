# Travel Planner AI

Eine Web-App zur Planung von Reisen mit Karten, Sehenswürdigkeiten,
Zwischenstopps, Tankstellen und Ladesäulen.

## Features

- Google Maps Integration
- Routenplanung
- Sehenswürdigkeiten entlang der Strecke
- Tankstellen-Suche
- Ladesäulen für Elektrofahrzeuge
- KI-gestützte Reiseplanung

## Technologie

Frontend:
- Next.js
- TypeScript
- Tailwind CSS

Backend:
- Next.js API Routes

Datenbank:
- PostgreSQL / PostGIS

APIs:
- Google Maps Platform
- Places API
- Directions API

## Lokale Weboberfläche starten

Die aktuelle Demo-Webapp verbindet eine Landingpage mit dem bestehenden Python-Orchestrator.

Abhängigkeiten installieren:

```bash
python3 -m pip install flask
```

Server starten:

```bash
python3 app.py
```

Danach im Browser öffnen:

```text
http://127.0.0.1:5000
```

Der Button "Let's get started" springt zum Formular. Nach "Route planen" sendet
das Frontend die Eingaben an `/api/plan`; dort ruft Flask den Orchestrator auf
und gibt Route, Wetter, POIs, Tankdaten und Kosten an die Website zurück.

## Öffentliche Webseite

Das Projekt enthält jetzt eine statische HTML-Webseite, die sich ohne Backend
im Browser öffnen oder über GitHub Pages hosten lässt.

- Statische Seite: `docs/index.html`
- Alternativ: `index.html` im Projektstamm

Um die Seite mit GitHub Pages zu veröffentlichen, aktiviere in den Repository-
Einstellungen "Pages" und wähle `main` / `docs` als Quelle. Die Seite ist dann
kostenlos und öffentlich erreichbar.

## Installation

Repository klonen:

```bash
git clone https://github.com/USERNAME/travel-planner.git
cd travel-planner
