"""
Gemeinsame Kalenderlogik fuer Ferienkalender, Blockplanung und den
Klassendienst-Generator. Schuljahr = 1.8. bis 31.7. (deutsche Konvention),
abgebildet als Startjahr (2026 = Schuljahr 2026/2027).
"""
from datetime import date, timedelta

from app.models import Blockwoche, Ferienzeitraum


def schuljahr_von(d: date) -> int:
    return d.year if d.month >= 8 else d.year - 1


def iso_woche(d: date) -> tuple[int, int]:
    """(iso_jahr, kw) - iso_jahr kann vom Kalenderjahr abweichen (Jahreswechsel-KW)."""
    iso_jahr, kw, _ = d.isocalendar()
    return iso_jahr, kw


def wochen_des_schuljahrs(schuljahr: int) -> list[tuple[int, int, date]]:
    """Alle (iso_jahr, kw, montag) ISO-Wochen von KW mit dem 1.8. bis KW mit dem 31.7."""
    start = date(schuljahr, 8, 1)
    ende = date(schuljahr + 1, 7, 31)
    montag = start - timedelta(days=start.weekday())
    wochen = []
    d = montag
    while d <= ende:
        iso_jahr, kw = iso_woche(d)
        wochen.append((iso_jahr, kw, d))
        d += timedelta(days=7)
    return wochen


def ferien_liste() -> list[Ferienzeitraum]:
    return Ferienzeitraum.query.order_by(Ferienzeitraum.von).all()


def ferientag(d: date, ferien: list[Ferienzeitraum] | None = None) -> Ferienzeitraum | None:
    ferien = ferien_liste() if ferien is None else ferien
    for f in ferien:
        if f.von <= d <= f.bis:
            return f
    return None


def blockwochen_der_klasse(klasse, schuljahr: int) -> set[tuple[int, int]]:
    return {
        (bw.iso_jahr, bw.kw) for bw in klasse.blockwochen if bw.schuljahr == schuljahr
    }


def wochen_mit_ferien_label(schuljahr: int) -> list[dict]:
    """Wochen des Schuljahrs, je Woche mit Ferien-Bezeichnung (oder None), wenn
    Montag ODER Freitag dieser Woche in einen Ferienzeitraum faellt - fuer die
    Kopfbaender der Blockplanung."""
    ferien = ferien_liste()
    ausgabe = []
    for iso_jahr, kw, montag in wochen_des_schuljahrs(schuljahr):
        freitag = montag + timedelta(days=4)
        f = ferientag(montag, ferien) or ferientag(freitag, ferien)
        ausgabe.append({
            "iso_jahr": iso_jahr, "kw": kw, "montag": montag,
            "ferien_label": f.bezeichnung if f else None,
        })
    return ausgabe


def ferien_baender(wochen: list[dict]) -> list[dict]:
    """Fasst aufeinanderfolgende Wochen mit gleicher ferien_label zu einem
    Kopfband (colspan) zusammen - fuer die Blockplanungs-Tabelle. Baender in
    Wochen-Reihenfolge, Summe der colspan == len(wochen)."""
    baender: list[dict] = []
    for w in wochen:
        label = w["ferien_label"]
        if label is not None and baender and baender[-1]["label"] == label:
            baender[-1]["colspan"] += 1
        else:
            baender.append({"label": label, "colspan": 1})
    return baender


def ist_schultag(klasse, d: date, ferien: list[Ferienzeitraum] | None = None) -> bool:
    """Wochenende/Ferien -> nein. Block-Klasse (hat Blockwochen fuer dieses
    Schuljahr) -> nur in als anwesend markierten KW. Sonst (Normalfall,
    keine Blockplanung gepflegt) -> jeder Werktag ausserhalb der Ferien."""
    if d.weekday() >= 5:
        return False
    if ferientag(d, ferien) is not None:
        return False
    schuljahr = schuljahr_von(d)
    block = blockwochen_der_klasse(klasse, schuljahr)
    if not block:
        return True
    return iso_woche(d) in block
