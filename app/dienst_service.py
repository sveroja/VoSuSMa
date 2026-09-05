"""
Reihum-Rotation fuer Klassendienste (zu zweit, taeglich wechselnd). Reine
Planungslogik ohne Route-Kram - siehe routes/dienste.py.
"""
from datetime import date, timedelta

from app import kalender
from app.extensions import db
from app.models import Klassendienst, Schueler, SchuelerKlasse

STANDARD_HINWEIS_VORLAGE = """\
Reihum übernehmen die Schülerinnen und Schüler der Klasse {bezeichnung} einen \
täglich wechselnden Klassendienst (zu zweit). Die Aufgaben beziehen sich auf \
den jeweils benutzten Klassenraum bzw. das benutzte Labor:

- Reinigung der Tafel
- Lüftung des Raums
- Tisch- und Stuhlordnung nach Verlassen herstellen
- Auf herumliegenden Müll hinweisen
- ggf. Einstellung der Beleuchtung (Vorhänge, ...)"""


def hinweistext(klasse) -> str:
    return klasse.dienst_hinweis or STANDARD_HINWEIS_VORLAGE.format(bezeichnung=klasse.bezeichnung)


def aktive_schueler(klasse) -> list[Schueler]:
    return (
        Schueler.query.join(SchuelerKlasse)
        .filter(SchuelerKlasse.klasse_id == klasse.id, SchuelerKlasse.aktiv_filter())
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )


def _dienst_zaehler(klasse) -> dict[int, int]:
    zaehler: dict[int, int] = {}
    for d in klasse.dienste:
        if d.schueler1_id:
            zaehler[d.schueler1_id] = zaehler.get(d.schueler1_id, 0) + 1
        if d.schueler2_id:
            zaehler[d.schueler2_id] = zaehler.get(d.schueler2_id, 0) + 1
    return zaehler


def dienst_uebersicht(klasse) -> list[tuple[Schueler, int]]:
    """(SuS, Anzahl Diensttage) je aktiver SuS - fuer die Fairness-Uebersicht
    auf der Klassendienste-Seite. Alphabetisch, auch SuS mit 0 Diensten."""
    zaehler = _dienst_zaehler(klasse)
    return [(s, zaehler.get(s.id, 0)) for s in aktive_schueler(klasse)]


def rota_generieren(klasse, von: date, bis: date) -> int:
    """Legt fuer Schultage in [von, bis] ohne bestehenden Eintrag neue
    Klassendienst-Zeilen an (Session-add, kein Commit - macht der Aufrufer).
    Reihum je zwei SuS, beginnend bei den bisher am seltensten eingeteilten.
    Gibt die Anzahl neu angelegter Tage zurueck."""
    schueler = aktive_schueler(klasse)
    if not schueler:
        return 0

    zaehler = _dienst_zaehler(klasse)
    reihenfolge = sorted(
        schueler, key=lambda s: (zaehler.get(s.id, 0), s.nachname.lower(), s.vorname.lower())
    )
    vorhandene_daten = {d.datum for d in klasse.dienste}

    i = 0
    angelegt = 0
    tag = von
    while tag <= bis:
        if tag not in vorhandene_daten and kalender.ist_schultag(klasse, tag):
            s1 = reihenfolge[i % len(reihenfolge)]
            s2 = reihenfolge[(i + 1) % len(reihenfolge)] if len(reihenfolge) > 1 else None
            db.session.add(Klassendienst(
                klasse_id=klasse.id, datum=tag, schueler1_id=s1.id,
                schueler2_id=s2.id if s2 and s2.id != s1.id else None,
            ))
            i += 2
            angelegt += 1
        tag += timedelta(days=1)
    return angelegt
