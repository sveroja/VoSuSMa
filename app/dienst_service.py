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


def gruppen_fair_moeglich(klasse) -> bool:
    """True, wenn sich die gruppenuebergreifende Paarung ueberhaupt anbietet -
    mindestens 2 Gruppen der Klasse haben je mindestens eine/n aktive/n SuS."""
    aktive_ids = {s.id for s in aktive_schueler(klasse)}
    gruppen_mit_mitgliedern = sum(
        1 for g in klasse.gruppen if any(m.id in aktive_ids for m in g.mitglieder)
    )
    return gruppen_mit_mitgliedern >= 2


def gruppen_label_je_schueler(klasse) -> dict[int, str]:
    """schueler_id -> ", "-getrennte Namen aller Gruppen der Klasse, denen die
    Person angehoert - fuer die Anzeige in Auswahllisten (z.B. den
    Klassendienst-Dropdowns), damit die Gruppenzugehoerigkeit dort auf einen
    Blick sichtbar ist. SuS ohne Gruppe fehlen im dict."""
    namen_je_schueler: dict[int, list[str]] = {}
    for gruppe in klasse.gruppen:
        for mitglied in gruppe.mitglieder:
            namen_je_schueler.setdefault(mitglied.id, []).append(gruppe.name)
    return {sid: ", ".join(namen) for sid, namen in namen_je_schueler.items()}


def _gruppe_je_schueler(klasse) -> dict[int, int]:
    """schueler_id -> gruppe_id, je erste zugeordnete Gruppe der Klasse. SuS ohne
    Gruppe fehlen im dict (gelten beim Paaren als eigene, gemeinsame "Gruppe")."""
    zuordnung: dict[int, int] = {}
    for gruppe in klasse.gruppen:
        for mitglied in gruppe.mitglieder:
            zuordnung.setdefault(mitglied.id, gruppe.id)
    return zuordnung


def rota_generieren(klasse, von: date, bis: date, gruppen_fair: bool = False) -> int:
    """Legt fuer Schultage in [von, bis] ohne bestehenden Eintrag neue
    Klassendienst-Zeilen an (Session-add, kein Commit - macht der Aufrufer).
    Je Tag werden die zwei bislang am seltensten eingeteilten SuS gepaart
    (greedy, Zaehler wird waehrend der Generierung fortgeschrieben - bleibt so
    auch ueber lange Zeitraeume fair). Mit gruppen_fair=True kommt SuS 2 gezielt
    aus einer anderen Gruppe als SuS 1 (z.B. Kohorte A + Kohorte B je Dienst),
    SuS ohne Gruppenzuordnung zaehlen dafuer als eigene gemeinsame Gruppe.
    Gibt die Anzahl neu angelegter Tage zurueck."""
    schueler = aktive_schueler(klasse)
    if not schueler:
        return 0

    zaehler = dict(_dienst_zaehler(klasse))
    gruppe_von = _gruppe_je_schueler(klasse) if gruppen_fair else {}
    vorhandene_daten = {d.datum for d in klasse.dienste}

    def sortiert():
        return sorted(
            schueler, key=lambda s: (zaehler.get(s.id, 0), s.nachname.lower(), s.vorname.lower())
        )

    angelegt = 0
    tag = von
    while tag <= bis:
        if tag not in vorhandene_daten and kalender.ist_schultag(klasse, tag):
            kandidaten = sortiert()
            s1 = kandidaten[0]
            s2 = None
            if len(kandidaten) > 1:
                if gruppen_fair:
                    andere_gruppe = [
                        s for s in kandidaten[1:]
                        if gruppe_von.get(s.id) != gruppe_von.get(s1.id)
                    ]
                    s2 = andere_gruppe[0] if andere_gruppe else kandidaten[1]
                else:
                    s2 = kandidaten[1]
            db.session.add(Klassendienst(
                klasse_id=klasse.id, datum=tag, schueler1_id=s1.id,
                schueler2_id=s2.id if s2 else None,
            ))
            zaehler[s1.id] = zaehler.get(s1.id, 0) + 1
            if s2:
                zaehler[s2.id] = zaehler.get(s2.id, 0) + 1
            angelegt += 1
        tag += timedelta(days=1)
    return angelegt
