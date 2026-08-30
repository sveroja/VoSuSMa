"""
Gemeinsame Logik fuer das Einlesen und Pruefen der Notenkategorie-Gewichtungen
aus einem Formular - genutzt beim Lernfeld-Anlegen (pro Klasse) und beim Pflegen
der Lernfeldvorlagen im Admin-Bereich.

Feldnamen im Formular: gewicht_<kategorie_id> in Prozent (0-100).
"""


def gewichte_aus_formular(form, kategorien) -> tuple[dict[int, float], list[str]]:
    """Gibt ({kategorie_id: prozent}, fehler) zurueck. Prueft jeden Wert auf
    0-100 und die Summe auf 100 (+-0,5)."""
    gewichte: dict[int, float] = {}
    fehler: list[str] = []

    for kategorie in kategorien:
        roh = form.get(f"gewicht_{kategorie.id}", "0").strip().replace(",", ".")
        try:
            wert = float(roh) if roh else 0.0
        except ValueError:
            wert = None
        if wert is None or wert < 0 or wert > 100:
            fehler.append(f"Gewicht für '{kategorie.bezeichnung}' muss zwischen 0 und 100 liegen.")
            wert = 0.0
        gewichte[kategorie.id] = wert

    summe = sum(gewichte.values())
    if not fehler and abs(summe - 100) > 0.5:
        fehler.append(f"Die Gewichtungen müssen zusammen 100 % ergeben (aktuell {summe:g} %).")

    return gewichte, fehler
