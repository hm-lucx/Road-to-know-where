from datetime import date, datetime, timedelta
from statistics import mean

import requests


FORECAST_TAGE = 16
REGENTAG_SCHWELLE_MM = 1.0
HOHER_NIEDERSCHLAG_MM = 8.0
SEHR_KALT_SCHWELLE_C = 3.0
KUEHL_SCHWELLE_C = 8.0
HISTORISCHE_JAHRE = 5

MONATSNAMEN = {
    "januar": 1,
    "februar": 2,
    "maerz": 3,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


# Grobe Aussengrenze Deutschlands als Polygon aus Laengen- und Breitengraden.
# Das ist keine amtliche Grenze, verhindert aber typische Fehlrouten ins Ausland,
# ohne dass der Agent dafuer eine weitere API oder Bibliothek braucht.
DEUTSCHLAND_GRENZPOLYGON = [
    (5.87, 47.27),
    (6.84, 47.52),
    (7.59, 47.58),
    (8.23, 47.62),
    (9.53, 47.54),
    (10.45, 47.56),
    (11.37, 47.40),
    (12.20, 47.55),
    (13.03, 47.65),
    (13.84, 48.76),
    (13.77, 50.30),
    (14.99, 51.00),
    (14.72, 52.10),
    (14.55, 53.70),
    (13.90, 54.45),
    (12.60, 54.48),
    (11.10, 54.93),
    (8.70, 54.90),
    (8.20, 55.05),
    (7.00, 53.75),
    (6.70, 52.60),
    (5.95, 51.85),
    (6.10, 50.75),
    (6.35, 49.45),
    (6.10, 48.95),
    (5.87, 47.27),
]


# Open-Meteo liefert Wettercodes nach dem WMO-Standard. Diese Tabelle macht
# daraus kurze deutsche Beschreibungen fuer das Frontend.
WETTERBESCHREIBUNGEN = {
    0: "Klarer Himmel",
    1: "Ueberwiegend klar",
    2: "Teilweise bewoelkt",
    3: "Bedeckt",
    45: "Nebel",
    48: "Reifnebel",
    51: "Leichter Nieselregen",
    53: "Maessiger Nieselregen",
    55: "Starker Nieselregen",
    56: "Leichter gefrierender Nieselregen",
    57: "Starker gefrierender Nieselregen",
    61: "Leichter Regen",
    63: "Maessiger Regen",
    65: "Starker Regen",
    66: "Leichter gefrierender Regen",
    67: "Starker gefrierender Regen",
    71: "Leichter Schneefall",
    73: "Maessiger Schneefall",
    75: "Starker Schneefall",
    77: "Schneegriesel",
    80: "Leichte Regenschauer",
    81: "Maessige Regenschauer",
    82: "Starke Regenschauer",
    85: "Leichte Schneeschauer",
    86: "Starke Schneeschauer",
    95: "Gewitter",
    96: "Gewitter mit leichtem Hagel",
    99: "Gewitter mit starkem Hagel",
}


# Schlechte Wettercodes bekommen mehr Punkte. So kann der Agent den
# kritischsten Reisetag auch dann finden, wenn nicht nur Regen relevant ist.
WETTERCODE_RISIKOPUNKTE = {
    0: 0,
    1: 0,
    2: 1,
    3: 1,
    45: 2,
    48: 2,
    51: 2,
    53: 3,
    55: 4,
    56: 5,
    57: 6,
    61: 3,
    63: 4,
    65: 6,
    66: 6,
    67: 7,
    71: 4,
    73: 5,
    75: 7,
    77: 4,
    80: 3,
    81: 4,
    82: 6,
    85: 4,
    86: 6,
    95: 7,
    96: 8,
    99: 9,
}


def wettercode_uebersetzen(wettercode):
    """Uebersetzt einen Open-Meteo-Wettercode in einen deutschen Text."""
    if wettercode is None:
        return "Keine Wetterbeschreibung verfuegbar"
    return WETTERBESCHREIBUNGEN.get(wettercode, "Unbekannte Wetterlage")


def parse_datum(datums_text):
    """Wandelt ein Datum im Format YYYY-MM-DD in ein Datumsobjekt um."""
    try:
        return datetime.strptime(datums_text, "%Y-%m-%d").date()
    except ValueError as fehler:
        raise ValueError(
            f"Das Datum '{datums_text}' ist ungueltig. Erwartet wird YYYY-MM-DD."
        ) from fehler


def validiere_reise_etappe(etappe):
    """Prueft, ob eine Tagesetappe alle Daten enthaelt, die der Agent braucht."""
    pflichtfelder = ["tag", "datum", "zielort", "ziel_lat", "ziel_lon"]
    fehlende_felder = [feld for feld in pflichtfelder if feld not in etappe]

    if fehlende_felder:
        raise ValueError(
            f"In einer Reiseetappe fehlen Pflichtfelder: {', '.join(fehlende_felder)}"
        )

    parse_datum(etappe["datum"])
    validiere_zielort_in_deutschland(etappe)


def validiere_zielort_in_deutschland(etappe):
    """Bricht ab, wenn der Zielort der Etappe ausserhalb Deutschlands liegt."""
    breitengrad = float(etappe["ziel_lat"])
    laengengrad = float(etappe["ziel_lon"])

    if not liegt_in_deutschland(breitengrad, laengengrad):
        raise ValueError(
            f"Der Zielort '{etappe['zielort']}' liegt ausserhalb Deutschlands "
            f"({breitengrad}, {laengengrad}). Bitte gib nur deutsche Zielorte an."
        )


def liegt_in_deutschland(breitengrad, laengengrad):
    """Prueft anhand eines einfachen Grenzpolygons, ob Koordinaten in Deutschland liegen."""
    if not (47.0 <= breitengrad <= 55.2 and 5.5 <= laengengrad <= 15.5):
        return False

    return punkt_liegt_im_polygon(
        x_wert=laengengrad,
        y_wert=breitengrad,
        polygon=DEUTSCHLAND_GRENZPOLYGON,
    )


def punkt_liegt_im_polygon(x_wert, y_wert, polygon):
    """Prueft mit dem Strahlverfahren, ob ein Punkt innerhalb eines Polygons liegt."""
    liegt_innerhalb = False
    vorheriger_punkt = polygon[-1]

    for aktueller_punkt in polygon:
        x1, y1 = vorheriger_punkt
        x2, y2 = aktueller_punkt

        schneidet_kante = (y1 > y_wert) != (y2 > y_wert)
        if schneidet_kante:
            schnittpunkt_x = (x2 - x1) * (y_wert - y1) / (y2 - y1) + x1
            if x_wert < schnittpunkt_x:
                liegt_innerhalb = not liegt_innerhalb

        vorheriger_punkt = aktueller_punkt

    return liegt_innerhalb


def ist_forecast_verfuegbar(reisedatum):
    """Entscheidet, ob ein Datum im normalen Open-Meteo-Forecast-Zeitraum liegt."""
    heute = date.today()
    letzter_forecast_tag = heute + timedelta(days=FORECAST_TAGE - 1)
    return heute <= reisedatum <= letzter_forecast_tag


def sende_open_meteo_anfrage(api_adresse, parameter):
    """Sendet eine Anfrage an Open-Meteo und gibt die JSON-Antwort zurueck."""
    try:
        antwort = requests.get(api_adresse, params=parameter, timeout=20)
        antwort.raise_for_status()
    except requests.RequestException as fehler:
        raise requests.RequestException(
            f"Open-Meteo konnte nicht erreicht werden: {fehler}"
        ) from fehler

    try:
        return antwort.json()
    except ValueError as fehler:
        raise ValueError("Open-Meteo hat keine gueltige JSON-Antwort geliefert.") from fehler


def suche_deutsche_stadt(stadtname):
    """Sucht eine Stadt in Deutschland und liefert Name und Koordinaten zurueck."""
    api_adresse = "https://geocoding-api.open-meteo.com/v1/search"

    for suchbegriff in erstelle_stadtnamen_varianten(stadtname):
        parameter = {
            "name": suchbegriff,
            "count": 10,
            "language": "de",
            "format": "json",
        }

        daten = sende_open_meteo_anfrage(api_adresse, parameter)
        treffer = daten.get("results") or []
        deutsche_treffer = [
            treffer_daten
            for treffer_daten in treffer
            if treffer_daten.get("country_code") == "DE"
            and liegt_in_deutschland(
                float(treffer_daten["latitude"]),
                float(treffer_daten["longitude"]),
            )
        ]

        if deutsche_treffer:
            bester_treffer = deutsche_treffer[0]
            return {
                "name": bester_treffer["name"],
                "breitengrad": float(bester_treffer["latitude"]),
                "laengengrad": float(bester_treffer["longitude"]),
                "bundesland": bester_treffer.get("admin1"),
            }

    raise ValueError(
        f"Fuer '{stadtname}' wurde kein passender Ort in Deutschland gefunden."
    )


def erstelle_stadtnamen_varianten(stadtname):
    """Erstellt Suchvarianten, damit Eingaben wie Muenchen und Nuernberg funktionieren."""
    varianten = [stadtname.strip()]
    ersetzter_name = (
        stadtname.strip()
        .replace("ae", "ä")
        .replace("oe", "ö")
        .replace("ue", "ü")
        .replace("Ae", "Ä")
        .replace("Oe", "Ö")
        .replace("Ue", "Ü")
        .replace("ss", "ß")
    )

    if ersetzter_name not in varianten:
        varianten.append(ersetzter_name)

    return varianten


def hole_forecast_wetter(etappe):
    """Holt echte Vorhersagedaten fuer den Zielort einer Tagesetappe."""
    api_adresse = "https://api.open-meteo.com/v1/forecast"
    parameter = {
        "latitude": etappe["ziel_lat"],
        "longitude": etappe["ziel_lon"],
        "start_date": etappe["datum"],
        "end_date": etappe["datum"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "timezone": "auto",
    }

    daten = sende_open_meteo_anfrage(api_adresse, parameter)
    return extrahiere_einen_wettertag(daten, etappe, "forecast")


def hole_historische_wetter_schaetzung(etappe):
    """Schaetzt Wetterwerte aus historischen Daten derselben Kalenderdaten.

    Fuer weit entfernte Reisedaten gibt es keine echte Tagesvorhersage. Deshalb
    fragt diese Funktion die letzten Jahre fuer denselben Monat und Tag ab und
    bildet daraus einfache Durchschnittswerte.
    """
    reisedatum = parse_datum(etappe["datum"])
    historische_wettertage = []

    for jahr in range(date.today().year - HISTORISCHE_JAHRE, date.today().year):
        try:
            historisches_datum = reisedatum.replace(year=jahr)
        except ValueError:
            # Der 29. Februar existiert nicht in jedem Jahr. Solche Jahre werden
            # ausgelassen, statt den gesamten Agenten abbrechen zu lassen.
            continue

        try:
            historischer_wettertag = hole_historischen_einzelwert(etappe, historisches_datum)
            historische_wettertage.append(historischer_wettertag)
        except (requests.RequestException, ValueError):
            continue

    if not historische_wettertage:
        return erstelle_nicht_verfuegbaren_wettertag(
            etappe,
            "historische Wetterdaten konnten nicht ausreichend ermittelt werden",
        )

    wettercodes = [
        wettertag["wettercode"]
        for wettertag in historische_wettertage
        if wettertag["wettercode"] is not None
    ]
    geschaetzter_wettercode = finde_haeufigsten_wettercode(wettercodes)

    return {
        "tag": etappe["tag"],
        "datum": etappe["datum"],
        "ort": etappe["zielort"],
        "temperatur_min": runde_wert(
            mean(wettertag["temperatur_min"] for wettertag in historische_wettertage)
        ),
        "temperatur_max": runde_wert(
            mean(wettertag["temperatur_max"] for wettertag in historische_wettertage)
        ),
        "niederschlag_mm": runde_wert(
            mean(wettertag["niederschlag_mm"] for wettertag in historische_wettertage)
        ),
        "wettercode": geschaetzter_wettercode,
        "wetterbeschreibung": wettercode_uebersetzen(geschaetzter_wettercode),
        "datenbasis": "historical_estimate",
        "meldung": "Schaetzung aus historischen Wetterwerten derselben Kalenderdaten",
    }


def hole_historischen_einzelwert(etappe, historisches_datum):
    """Holt einen einzelnen historischen Tageswert aus der Open-Meteo Archive API."""
    api_adresse = "https://archive-api.open-meteo.com/v1/archive"
    datum_text = historisches_datum.isoformat()
    parameter = {
        "latitude": etappe["ziel_lat"],
        "longitude": etappe["ziel_lon"],
        "start_date": datum_text,
        "end_date": datum_text,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "timezone": "auto",
    }

    daten = sende_open_meteo_anfrage(api_adresse, parameter)
    return extrahiere_einen_wettertag(daten, etappe, "historical_estimate")


def extrahiere_einen_wettertag(api_daten, etappe, datenbasis):
    """Liest die benoetigten Tageswerte aus einer Open-Meteo-Antwort."""
    tagesdaten = api_daten.get("daily")
    if not tagesdaten:
        raise ValueError("In der Open-Meteo-Antwort fehlen Tagesdaten.")

    temperatur_max = lese_ersten_wert(tagesdaten, "temperature_2m_max")
    temperatur_min = lese_ersten_wert(tagesdaten, "temperature_2m_min")
    niederschlag = lese_ersten_wert(tagesdaten, "precipitation_sum")
    wettercode = lese_ersten_wert(tagesdaten, "weather_code")

    if temperatur_max is None or temperatur_min is None or niederschlag is None:
        raise ValueError("In der Open-Meteo-Antwort fehlen wichtige Wetterwerte.")

    return {
        "tag": etappe["tag"],
        "datum": etappe["datum"],
        "ort": etappe["zielort"],
        "temperatur_min": runde_wert(temperatur_min),
        "temperatur_max": runde_wert(temperatur_max),
        "niederschlag_mm": runde_wert(niederschlag),
        "wettercode": wettercode,
        "wetterbeschreibung": wettercode_uebersetzen(wettercode),
        "datenbasis": datenbasis,
        "meldung": None,
    }


def lese_ersten_wert(tagesdaten, feldname):
    """Liest den ersten Wert eines Open-Meteo-Feldes, falls er vorhanden ist."""
    werte = tagesdaten.get(feldname)
    if not werte:
        return None
    return werte[0]


def runde_wert(wert):
    """Rundet Zahlen auf eine Nachkommastelle und laesst fehlende Werte unveraendert."""
    if wert is None:
        return None
    return round(float(wert), 1)


def finde_haeufigsten_wettercode(wettercodes):
    """Findet den haeufigsten Wettercode; bei Gleichstand gewinnt der kritischere Code."""
    if not wettercodes:
        return None

    return max(
        set(wettercodes),
        key=lambda code: (wettercodes.count(code), WETTERCODE_RISIKOPUNKTE.get(code, 1)),
    )


def ermittle_wetter_fuer_etappe(etappe):
    """Ermittelt Wetterdaten fuer eine Etappe und waehlt die passende Datenbasis."""
    validiere_reise_etappe(etappe)
    reisedatum = parse_datum(etappe["datum"])

    if ist_forecast_verfuegbar(reisedatum):
        try:
            return hole_forecast_wetter(etappe)
        except (requests.RequestException, ValueError) as fehler:
            return erstelle_nicht_verfuegbaren_wettertag(
                etappe,
                f"Forecast-Daten konnten nicht ermittelt werden: {fehler}",
            )

    return hole_historische_wetter_schaetzung(etappe)


def erstelle_nicht_verfuegbaren_wettertag(etappe, meldung):
    """Erstellt einen Tagesdatensatz, wenn keine Wetterdaten verfuegbar sind."""
    return {
        "tag": etappe.get("tag"),
        "datum": etappe.get("datum"),
        "ort": etappe.get("zielort"),
        "temperatur_min": None,
        "temperatur_max": None,
        "niederschlag_mm": None,
        "wettercode": None,
        "wetterbeschreibung": "Keine Wetterdaten verfuegbar",
        "datenbasis": "unavailable",
        "meldung": meldung,
    }


def berechne_temperaturspanne(tagesuebersicht):
    """Berechnet die niedrigste und hoechste Temperatur der gesamten Reise."""
    tiefstwerte = [
        tag["temperatur_min"]
        for tag in tagesuebersicht
        if tag["temperatur_min"] is not None
    ]
    hoechstwerte = [
        tag["temperatur_max"]
        for tag in tagesuebersicht
        if tag["temperatur_max"] is not None
    ]

    if not tiefstwerte or not hoechstwerte:
        return {
            "temperatur_min": None,
            "temperatur_max": None,
            "text": "Keine Temperaturdaten verfuegbar",
        }

    temperatur_min = runde_wert(min(tiefstwerte))
    temperatur_max = runde_wert(max(hoechstwerte))

    return {
        "temperatur_min": temperatur_min,
        "temperatur_max": temperatur_max,
        "text": f"Zwischen {temperatur_min:g} und {temperatur_max:g} °C",
    }


def zaehle_regentage(tagesuebersicht):
    """Zaehlt Tage mit relevantem Niederschlag."""
    return sum(
        1
        for tag in tagesuebersicht
        if tag["niederschlag_mm"] is not None
        and tag["niederschlag_mm"] >= REGENTAG_SCHWELLE_MM
    )


def berechne_tagesrisiko_punkte(wettertag):
    """Berechnet einfache Risikopunkte fuer einen Reisetag."""
    punkte = 0
    niederschlag = wettertag["niederschlag_mm"]
    temperatur_min = wettertag["temperatur_min"]
    wettercode = wettertag["wettercode"]

    if niederschlag is not None:
        punkte += niederschlag * 1.5
        if niederschlag >= HOHER_NIEDERSCHLAG_MM:
            punkte += 5

    if temperatur_min is not None:
        if temperatur_min <= SEHR_KALT_SCHWELLE_C:
            punkte += 6
        elif temperatur_min <= KUEHL_SCHWELLE_C:
            punkte += 3

    punkte += WETTERCODE_RISIKOPUNKTE.get(wettercode, 1)
    return punkte


def finde_kritischsten_tag(tagesuebersicht):
    """Findet den Reisetag mit dem unguenstigsten Wetter."""
    verfuegbare_tage = [
        tag for tag in tagesuebersicht if tag["datenbasis"] != "unavailable"
    ]

    if not verfuegbare_tage:
        return {
            "tag": None,
            "datum": None,
            "ort": None,
            "grund": "Keine Wetterdaten verfuegbar",
        }

    kritischster_tag = max(verfuegbare_tage, key=berechne_tagesrisiko_punkte)

    return {
        "tag": kritischster_tag["tag"],
        "datum": kritischster_tag["datum"],
        "ort": kritischster_tag["ort"],
        "grund": ermittle_kritischen_grund(kritischster_tag),
    }


def ermittle_kritischen_grund(wettertag):
    """Beschreibt kurz, warum ein Tag als kritisch gilt."""
    niederschlag = wettertag["niederschlag_mm"]
    temperatur_min = wettertag["temperatur_min"]
    wettercode = wettertag["wettercode"]

    if niederschlag is not None and niederschlag >= HOHER_NIEDERSCHLAG_MM:
        return "Hoher erwarteter Niederschlag"
    if wettercode in {95, 96, 99}:
        return "Moegliche Gewitterlage"
    if wettercode in {71, 73, 75, 85, 86}:
        return "Moeglicher Schneefall"
    if temperatur_min is not None and temperatur_min <= SEHR_KALT_SCHWELLE_C:
        return "Sehr niedrige Temperatur"
    if niederschlag is not None and niederschlag >= REGENTAG_SCHWELLE_MM:
        return "Erwarteter Niederschlag"
    return "Vergleichsweise unguenstigste Wetterlage"


def bewerte_wetterrisiko(tagesuebersicht, anzahl_regentage):
    """Leitet aus Regen, Kaelte und Wettercodes eine einfache Risikostufe ab."""
    verfuegbare_tage = [
        tag for tag in tagesuebersicht if tag["datenbasis"] != "unavailable"
    ]

    if not verfuegbare_tage:
        return "hoch"

    hoechster_niederschlag = max(
        tag["niederschlag_mm"] or 0 for tag in verfuegbare_tage
    )
    niedrigste_temperatur = min(
        tag["temperatur_min"] for tag in verfuegbare_tage if tag["temperatur_min"] is not None
    )
    kritische_codes = {65, 67, 75, 82, 86, 95, 96, 99}
    hat_kritischen_code = any(
        tag["wettercode"] in kritische_codes for tag in verfuegbare_tage
    )

    if (
        anzahl_regentage >= 3
        or hoechster_niederschlag >= HOHER_NIEDERSCHLAG_MM
        or niedrigste_temperatur <= SEHR_KALT_SCHWELLE_C
        or hat_kritischen_code
    ):
        return "hoch"

    if anzahl_regentage >= 1 or niedrigste_temperatur <= KUEHL_SCHWELLE_C:
        return "mittel"

    return "niedrig"


def ermittle_datenbasis(tagesuebersicht):
    """Fasst die Datenbasis aller Tage zu einem Kachelwert zusammen."""
    datenbasen = {tag["datenbasis"] for tag in tagesuebersicht}

    if not datenbasen or datenbasen == {"unavailable"}:
        return "unavailable"
    if datenbasen == {"forecast"}:
        return "forecast"
    if datenbasen == {"historical_estimate"}:
        return "historical_estimate"
    return "mixed"


def erstelle_gesamtbewertung(tagesuebersicht, anzahl_regentage, wetter_risiko, datenbasis):
    """Erstellt eine kurze, freundliche Zusammenfassung fuer Reisende."""
    verfuegbare_tage = [
        tag for tag in tagesuebersicht if tag["datenbasis"] != "unavailable"
    ]

    if not verfuegbare_tage:
        return "Fuer diese Reise konnten aktuell keine belastbaren Wetterdaten ermittelt werden."

    erster_tag = verfuegbare_tage[0]
    letzter_tag = verfuegbare_tage[-1]
    datenbasis_text = {
        "forecast": "Die Werte basieren auf einer echten Wettervorhersage.",
        "historical_estimate": "Die Werte sind eine Schaetzung aus historischen Wetterdaten.",
        "mixed": "Die Reise enthaelt echte Vorhersagen und historische Schaetzungen.",
        "unavailable": "Die Wetterdaten sind nur eingeschraenkt verfuegbar.",
    }[datenbasis]

    if wetter_risiko == "niedrig":
        lage_text = (
            f"Die Reise wirkt wetterseitig entspannt: von {erster_tag['ort']} bis "
            f"{letzter_tag['ort']} sind kaum relevante Niederschlaege erkennbar."
        )
    elif wetter_risiko == "mittel":
        lage_text = (
            f"Die Wetterlage ist insgesamt gut planbar, aber {anzahl_regentage} "
            f"Reisetag(e) koennen feucht oder kuehl werden."
        )
    else:
        lage_text = (
            f"Die Reise hat erhoehtes Wetterrisiko, besonders rund um "
            f"{finde_kritischsten_tag(tagesuebersicht)['ort']}."
        )

    return f"{lage_text} {datenbasis_text}"


def erstelle_packempfehlung(tagesuebersicht, anzahl_regentage, wetter_risiko):
    """Erzeugt eine kurze praktische Packempfehlung."""
    kritischster_tag = finde_kritischsten_tag(tagesuebersicht)

    if wetter_risiko == "hoch":
        if kritischster_tag["tag"] is None:
            return (
                "Aktuell sind keine belastbaren Wetterdaten verfuegbar. "
                "Pruefe die Reise spaeter erneut und plane vorerst wetterflexibel."
            )

        return (
            "Packe Regenjacke, warme Schichten und wetterfeste Schuhe ein. "
            f"Plane fuer Tag {kritischster_tag['tag']} eine flexible Alternative."
        )

    if wetter_risiko == "mittel":
        if anzahl_regentage > 0:
            return "Packe eine leichte Regenjacke ein und halte einzelne Stopps flexibel."
        return "Packe eine waermere Schicht fuer kuehlere Morgen oder Abende ein."

    return "Leichte Kleidung reicht wahrscheinlich aus; eine duenne Jacke ist als Reserve sinnvoll."


def bereinige_tagesuebersicht_fuer_frontend(tagesuebersicht):
    """Entfernt interne Felder, die das Frontend nicht direkt anzeigen muss."""
    sichtbare_felder = [
        "tag",
        "datum",
        "ort",
        "temperatur_min",
        "temperatur_max",
        "niederschlag_mm",
        "wetterbeschreibung",
        "datenbasis",
    ]

    return [
        {feld: wettertag[feld] for feld in sichtbare_felder}
        for wettertag in tagesuebersicht
    ]


def erstelle_wetter_kachel(reise_etappen):
    """Erstellt eine kompakte Wetter-Kachel fuer eine komplette Roadtrip-Reise."""
    if not reise_etappen:
        raise ValueError("Die Liste der Reiseetappen darf nicht leer sein.")

    tagesuebersicht = [
        ermittle_wetter_fuer_etappe(etappe) for etappe in reise_etappen
    ]
    datenbasis = ermittle_datenbasis(tagesuebersicht)
    temperaturspanne = berechne_temperaturspanne(tagesuebersicht)
    anzahl_regentage = zaehle_regentage(tagesuebersicht)
    kritischster_tag = finde_kritischsten_tag(tagesuebersicht)
    wetter_risiko = bewerte_wetterrisiko(tagesuebersicht, anzahl_regentage)

    return {
        "titel": "Wetterprognose fuer deine Reise",
        "datenbasis": datenbasis,
        "temperaturspanne": temperaturspanne,
        "anzahl_regentage": anzahl_regentage,
        "kritischster_tag": kritischster_tag,
        "gesamtbewertung": erstelle_gesamtbewertung(
            tagesuebersicht,
            anzahl_regentage,
            wetter_risiko,
            datenbasis,
        ),
        "wetter_risiko": wetter_risiko,
        "packempfehlung": erstelle_packempfehlung(
            tagesuebersicht,
            anzahl_regentage,
            wetter_risiko,
        ),
        "tagesuebersicht": bereinige_tagesuebersicht_fuer_frontend(tagesuebersicht),
    }


def zeige_wetter_kachel(wetter_kachel):
    """Gibt die Wetter-Kachel lesbar auf der Konsole aus."""
    print(wetter_kachel["titel"])
    print("=" * len(wetter_kachel["titel"]))
    print(f"Datenbasis: {wetter_kachel['datenbasis']}")
    print(f"Temperaturspanne: {wetter_kachel['temperaturspanne']['text']}")
    print(f"Regentage: {wetter_kachel['anzahl_regentage']}")
    print(f"Wetterrisiko: {wetter_kachel['wetter_risiko']}")
    print(f"Gesamtbewertung: {wetter_kachel['gesamtbewertung']}")
    print(f"Packempfehlung: {wetter_kachel['packempfehlung']}")
    print()
    print("Tagesuebersicht:")

    for wettertag in wetter_kachel["tagesuebersicht"]:
        print(
            f"- Tag {wettertag['tag']} in {wettertag['ort']} ({wettertag['datum']}): "
            f"{wettertag['temperatur_min']} bis {wettertag['temperatur_max']} °C, "
            f"{wettertag['niederschlag_mm']} mm, "
            f"{wettertag['wetterbeschreibung']} [{wettertag['datenbasis']}]"
        )

        if wettertag["datenbasis"] == "unavailable":
            print("  Hinweis: Fuer diesen Tag konnten keine Wetterdaten geladen werden.")


def frage_text_ab(frage, standardwert=None):
    """Liest Text von der Konsole und nutzt bei leerer Eingabe einen Standardwert."""
    if standardwert is None:
        antwort = input(f"{frage}: ").strip()
    else:
        antwort = input(f"{frage} [{standardwert}]: ").strip()

    if antwort:
        return antwort
    return standardwert


def frage_ganzzahl_ab(frage, standardwert=None):
    """Liest eine ganze Zahl von der Konsole."""
    while True:
        antwort = frage_text_ab(frage, standardwert)
        try:
            return int(antwort)
        except (TypeError, ValueError):
            print("Bitte gib eine ganze Zahl ein.")


def erstelle_beispiel_reise_etappen():
    """Erstellt eine Beispielroute mit Zielorten innerhalb Deutschlands."""
    return [
        {
            "tag": 1,
            "datum": "2026-06-10",
            "startort": "Muenchen",
            "zielort": "Nuernberg",
            "ziel_lat": 49.4521,
            "ziel_lon": 11.0767,
        },
        {
            "tag": 2,
            "datum": "2026-06-11",
            "startort": "Nuernberg",
            "zielort": "Dresden",
            "ziel_lat": 51.0504,
            "ziel_lon": 13.7373,
        },
    ]


def frage_reise_startdatum_ab():
    """Erfragt einen natuerlichen Reisezeitraum und gibt das Startdatum zurueck."""
    print("Wann soll die Reise starten?")
    print("1 = ab morgen")
    print("2 = in einer Woche")
    print("3 = in einem Monat")
    print("4 = in einem bestimmten Monat")
    print("5 = eigenes Startdatum eingeben")

    auswahl = frage_text_ab("Auswahl", "1").lower()
    heute = date.today()

    if auswahl == "1" or auswahl == "ab morgen":
        return heute + timedelta(days=1)
    if auswahl == "2" or "woche" in auswahl:
        return heute + timedelta(days=7)
    if auswahl == "3" or "monat" in auswahl and "bestimmt" not in auswahl:
        return addiere_einen_monat(heute)
    if auswahl == "4":
        return frage_monat_ab(heute)
    if auswahl == "5":
        return parse_datum(frage_text_ab("Startdatum im Format YYYY-MM-DD"))

    if auswahl in MONATSNAMEN:
        return erster_tag_des_naechsten_monats(heute, MONATSNAMEN[auswahl])

    print("Auswahl nicht erkannt. Ich nutze morgen als Startdatum.")
    return heute + timedelta(days=1)


def addiere_einen_monat(heute):
    """Ermittelt ungefaehr denselben Tag im naechsten Monat."""
    ziel_monat = heute.month + 1
    ziel_jahr = heute.year

    if ziel_monat == 13:
        ziel_monat = 1
        ziel_jahr += 1

    letzter_tag = letzter_tag_des_monats(ziel_jahr, ziel_monat)
    return date(ziel_jahr, ziel_monat, min(heute.day, letzter_tag))


def frage_monat_ab(heute):
    """Fragt einen Monatsnamen ab und nimmt den ersten Tag des naechsten passenden Monats."""
    while True:
        monatsname = frage_text_ab("Monat, zum Beispiel Oktober", "Oktober").lower()
        if monatsname in MONATSNAMEN:
            return erster_tag_des_naechsten_monats(heute, MONATSNAMEN[monatsname])
        print("Bitte gib einen deutschen Monatsnamen ein, zum Beispiel Oktober.")


def erster_tag_des_naechsten_monats(heute, monat):
    """Nimmt den ersten Tag des naechsten passenden Monats."""
    jahr = heute.year
    if monat < heute.month:
        jahr += 1
    return date(jahr, monat, 1)


def letzter_tag_des_monats(jahr, monat):
    """Gibt den letzten Kalendertag eines Monats zurueck."""
    if monat == 12:
        erster_tag_folgemonat = date(jahr + 1, 1, 1)
    else:
        erster_tag_folgemonat = date(jahr, monat + 1, 1)
    return (erster_tag_folgemonat - timedelta(days=1)).day


def frage_deutsche_stadt_ab(frage, standardwert):
    """Fragt einen Stadtnamen ab und ermittelt die Koordinaten automatisch."""
    while True:
        stadtname = frage_text_ab(frage, standardwert)
        try:
            stadt = suche_deutsche_stadt(stadtname)
            zusatz = f", {stadt['bundesland']}" if stadt["bundesland"] else ""
            print(
                f"Gefunden: {stadt['name']}{zusatz} "
                f"({stadt['breitengrad']:.4f}, {stadt['laengengrad']:.4f})"
            )
            return stadt
        except (requests.RequestException, ValueError) as fehler:
            print(f"Stadt konnte nicht genutzt werden: {fehler}")
            print("Bitte gib eine deutsche Stadt ein, zum Beispiel Hamburg oder Leipzig.")


def frage_reise_etappen_ab():
    """Erfragt Reiseetappen fuer einen lokalen Konsolentest."""
    print("Eigene Reiseetappen eingeben")
    print("============================")
    print("Hinweis: Du gibst nur deutsche Staedte ein. Koordinaten werden automatisch gesucht.")
    print()

    startdatum = frage_reise_startdatum_ab()
    anzahl_etappen = frage_ganzzahl_ab("Wie viele Etappen moechtest du testen?", 2)
    vorheriger_ort = frage_deutsche_stadt_ab("Startstadt", "Muenchen")
    reise_etappen = []

    for nummer in range(1, anzahl_etappen + 1):
        print()
        print(f"Etappe {nummer}")
        print("-" * 8)

        zielort = frage_deutsche_stadt_ab(
            "Zielstadt",
            "Nuernberg" if nummer == 1 else "Dresden",
        )
        etappe = {
            "tag": nummer,
            "datum": (startdatum + timedelta(days=nummer - 1)).isoformat(),
            "startort": vorheriger_ort["name"],
            "zielort": zielort["name"],
            "ziel_lat": zielort["breitengrad"],
            "ziel_lon": zielort["laengengrad"],
        }
        reise_etappen.append(etappe)
        vorheriger_ort = zielort

    return reise_etappen


def waehle_reise_etappen_fuer_test():
    """Laesst den Nutzer zwischen Beispielroute und eigener Eingabe waehlen."""
    print("Wetter-Agent Test")
    print("=================")
    print("1 = Beispielroute in Deutschland verwenden")
    print("2 = Eigene Reisedaten eingeben")
    auswahl = frage_text_ab("Auswahl", "1")
    print()

    if auswahl == "2":
        return frage_reise_etappen_ab()

    return erstelle_beispiel_reise_etappen()


if __name__ == "__main__":
    try:
        test_reise_etappen = waehle_reise_etappen_fuer_test()
        wetter_kachel = erstelle_wetter_kachel(test_reise_etappen)
        print()
        zeige_wetter_kachel(wetter_kachel)
    except (requests.RequestException, ValueError) as fehler:
        print(f"Der Wetter-Agent konnte keine Kachel erstellen: {fehler}")
