# Road to KnowWhere

Webanwendung zur themenbasierten Roadtrip-Planung. Das Frontend sendet
Reiseparameter an ein Flask-Backend. Dort koordiniert der Orchestrator mehrere
Agents fuer Route/POIs, Wetter und Tank-/Kosteninformationen.

## Projektstruktur

- `app.py`: Flask-Backend und API-Endpunkt `/api/plan`
- `Orchestrat MR.py`: zentraler Orchestrator
- `maps&poi.py`: Routen-, POI- und Tagesetappenlogik
- `wetter_agent.py`: Wetterdaten und Wetter-Kachel
- `Tankstelle MR.py`: Tankstellen- und Preislogik
- `templates/index.html`: HTML-Template der Weboberflaeche
- `static/style.css`: Styling
- `static/script.js`: Frontend-Interaktion und Kartenanzeige

## Lokal starten

Abhaengigkeiten installieren:

```bash
python3 -m pip install -r requirements.txt
```

Entwicklungsserver starten:

```bash
python3 app.py
```

Danach im Browser oeffnen:

```text
http://127.0.0.1:5000
```

<<<<<<< HEAD
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

## Backend veröffentlichen

Das Backend läuft als Flask-App und muss separat auf einem öffentlichen Host
bereitgestellt werden, damit die GitHub Pages-Webseite dauerhaft funktioniert.

Die Repo enthält jetzt eine `render.yaml`, `Dockerfile`, `requirements.txt`
und `Procfile`, um das Backend z.B. auf Render.com zu deployen.

Standardmäßig verwendet das Frontend den Endpunkt
`https://road-to-know-where-backend.onrender.com/api/plan`.

1. Erstelle einen Render-Account und verbinde dieses Repository.
2. Aktiviere die `render.yaml`-Konfiguration.
3. Deploye den Service `road-to-know-where-backend`.
4. Stelle sicher, dass der Dienst unter `https://road-to-know-where-backend.onrender.com`
erreichbar ist.

Wenn der Backend-Host anders heißt, kann die Seite als URL-Parameter
`?backend=https://mein-backend.example.com` aufgerufen werden.

## Installation

Repository klonen:
=======
Produktionsstart lokal testen:
>>>>>>> 3f16920 (V6)

```bash
python3 -m gunicorn app:app --bind 0.0.0.0:5000
```

## Environment Variables

Optional fuer echte Tankstellenpreise:

```text
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
```

Ohne diesen Key laeuft die Anwendung weiter, aber Tankstellenpreise koennen
fehlen oder als nicht verfuegbar angezeigt werden.

## Deployment auf Render

Empfohlene Plattform: Render Web Service.

Warum Render:

- passt gut zu Flask-Apps
- kann direkt aus GitHub deployen
- kein Dockerfile notwendig
- Start Command `gunicorn app:app` ist einfach und stabil

Render-Einstellungen:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
```

Environment Variables auf Render:

```text
TANKERKOENIG_API_KEY=dein_tankerkoenig_api_key
```

`PORT` muss nicht manuell gesetzt werden. Render setzt den Port automatisch und
Gunicorn bindet daran.

Schritte:

1. Aenderungen committen und zu GitHub pushen.
2. In Render einen neuen `Web Service` erstellen.
3. GitHub-Repository `Road-to-know-where` verbinden.
4. Runtime `Python` auswaehlen.
5. Build Command und Start Command wie oben setzen.
6. Optional `TANKERKOENIG_API_KEY` als Environment Variable eintragen.
7. Deploy starten.
8. Die von Render erzeugte URL im Browser oeffnen.

Nach dem Deployment testen:

1. Startseite laden.
2. Formular ausfuellen.
3. `Route planen` klicken.
4. Pruefen, ob Route, Karte, Wetter-Kachel, POIs, Kosten und Telemetrie-Kacheln
   angezeigt werden.
