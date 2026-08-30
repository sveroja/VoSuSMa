"""
Berechnungslogik fuer Noten - aus den Excel-Formeln abgeleitet.

Wichtige Regel aus der Klaerung: Prozent wird NUR innerhalb einer Kategorie
verwendet (Punkte -> Prozent -> Note). Kategorieuebergreifend (fuer die
Gesamtnote) wird ausschliesslich mit der Note (Dezimal) gerechnet, nie mit
Prozenten gemischt.
"""
from app.models import Notenschema

NOTE_MIN = 1.0
NOTE_MAX = 6.0


def parse_note(rohwert: str) -> float:
    """Notentext ("2", "2,3", " 3.0 ") -> float. Wirft ValueError bei Unsinn
    oder ausserhalb 1,0-6,0. Gemeinsam genutzt von Einzel- und Bulk-Eingabe."""
    wert = float(rohwert.strip().replace(",", "."))
    if not (NOTE_MIN <= wert <= NOTE_MAX):
        raise ValueError(
            f"Note muss zwischen {NOTE_MIN:.1f} und {NOTE_MAX:.1f} liegen.".replace(".", ",")
        )
    return wert


def note_aus_prozent(prozent: float, schema: Notenschema | None = None) -> float | None:
    """VLOOKUP-Ersatz: Prozent -> Note ueber das aktive Notenschema."""
    if schema is None:
        schema = Notenschema.query.filter_by(aktiv=True).first()
    if schema is None:
        raise ValueError("Kein aktives Notenschema konfiguriert.")

    prozent_gerundet = round(prozent)
    for stufe in schema.stufen:
        if stufe.von_prozent <= prozent_gerundet <= stufe.bis_prozent:
            return stufe.note
    return None


def note_aus_eintrag(eintrag) -> float | None:
    """Ein einzelner Noteneintrag -> Note. manuelle_note sticht alles."""
    if eintrag.manuelle_note is not None:
        return eintrag.manuelle_note
    if eintrag.note_direkt is not None:
        return eintrag.note_direkt
    if eintrag.erreichte_punkte is not None and eintrag.max_punkte:
        prozent = eintrag.erreichte_punkte / eintrag.max_punkte * 100
        return note_aus_prozent(prozent)
    return None


def kategorie_durchschnitt(noteneintraege: list) -> float | None:
    """Durchschnitt aller Noten einer Kategorie (z.B. alle muendlichen Einzeltermine)."""
    noten = [n for n in (note_aus_eintrag(e) for e in noteneintraege) if n is not None]
    if not noten:
        return None
    return sum(noten) / len(noten)


def gesamtnote(lernfeld, noteneintraege_je_kategorie: dict) -> float | None:
    """
    lernfeld: Lernfeld-Objekt (fuer die Gewichtungen)
    noteneintraege_je_kategorie: {kategorie_id: [Notenereintrag, ...]}
    """
    gewichtungen = {g.kategorie_id: g.gewicht for g in lernfeld.gewichtungen}
    summe_gewicht = 0.0
    summe_gewichtet = 0.0

    for kategorie_id, eintraege in noteneintraege_je_kategorie.items():
        gewicht = gewichtungen.get(kategorie_id, 0.0)
        if gewicht <= 0:
            continue
        durchschnitt = kategorie_durchschnitt(eintraege)
        if durchschnitt is None:
            continue
        summe_gewichtet += durchschnitt * gewicht
        summe_gewicht += gewicht

    if summe_gewicht == 0:
        return None
    # Normalisieren, falls Gewichte nicht exakt 1.0 ergeben (z.B. fehlende Kategorie)
    return round(summe_gewichtet / summe_gewicht, 1)
