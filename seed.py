"""
Befuellt die Dev-Datenbank mit Fake-Daten (Faker, Locale de_DE), strukturell
identisch zum echten Schema. Bricht sicherheitshalber ab, wenn APP_ENV nicht
"dev" ist, damit hier niemals versehentlich in prod.sqlite3 geschrieben wird.

Aufruf:
    python seed.py
"""
import random
import sys
from datetime import date, timedelta

from app.config import aktuelles_env

if aktuelles_env() != "dev":
    sys.exit(
        "Abgebrochen: seed.py laeuft nur in der dev-Umgebung "
        f"(aktuell: {aktuelles_env()!r}). Fake-Daten kommen nie in prod.sqlite3. "
        "Dieses Skript gehoert in den Entwicklungs-Ordner."
    )

from faker import Faker

from app import create_app
from app.extensions import db
from app.lernfeld_service import lernfelder_aus_vorlagen
from app.models import (
    Betrieb,
    Bildungsgang,
    Gruppe,
    Klasse,
    Lernfeld,
    Lernfeldvorlage,
    Notenereintrag,
    Notenkategorie,
    NotenkategorieGewichtung,
    Schueler,
    SchuelerKlasse,
    VorlageGewichtung,
    Zeugnisnote,
    schueler_gruppen,
)
from app.stammdaten import STANDARD_NOTENKATEGORIEN

fake = Faker("de_DE")

# Bildungsgang-Schluessel -> (Bezeichnung, [(nummer|None, name), ...])
BILDUNGSGAENGE = {
    "eh": ("Kaufmann/-frau im Einzelhandel", [
        (1, "Das Einzelhandelsunternehmen repräsentieren"),
        (2, "Verkaufsgespräche kundenorientiert führen"),
        (3, "Kunden im Servicebereich Kasse betreuen"),
        (4, "Waren präsentieren"),
        (None, "Deutsch / Kommunikation"),
        (None, "Wirtschafts- und Sozialkunde"),
    ]),
    "log": ("Fachkraft für Lagerlogistik", [
        (1, "Güter annehmen und kontrollieren"),
        (2, "Güter lagern"),
        (3, "Güter bearbeiten"),
        (None, "Deutsch / Kommunikation"),
    ]),
}

# (Klassenbezeichnung, Bildungsgang-Schluessel)
KLASSEN_DATEN = [("EH24a", "eh"), ("EH24b", "eh"), ("LOG23a", "log")]

KATEGORIEN = list(STANDARD_NOTENKATEGORIEN)

# Wird in seed() je Lernfeld befuellt: {lernfeld_id: {"muendlich": [(datum,bez)],
# "klassenarbeit": [...], "abgabe": [...]}}
_TERMINE_JE_LERNFELD = {}


def _termine_fuer_lernfeld():
    start = date.today() - timedelta(days=170)

    def d(offset):
        return start + timedelta(days=offset)

    kw = start.isocalendar()[1]
    muendlich = [
        (d(off), f"Mitarbeit KW{(kw + i * 4) % 52 or 52}")
        for i, off in enumerate(sorted(random.sample(range(0, 165), random.randint(3, 5))))
    ]
    klassenarbeit = [
        (d(off), f"Klassenarbeit {i + 1}")
        for i, off in enumerate(sorted(random.sample(range(30, 165), random.randint(1, 2))))
    ]
    abgabe = [(d(random.randint(20, 150)), "Hausaufgabe")] if random.random() < 0.7 else []
    return {"muendlich": muendlich, "klassenarbeit": klassenarbeit, "abgabe": abgabe}


def _get_or_create_kategorien():
    kategorien = {}
    for schluessel, bezeichnung, _gewicht in KATEGORIEN:
        kategorie = Notenkategorie.query.filter_by(schluessel=schluessel).first()
        if kategorie is None:
            kategorie = Notenkategorie(schluessel=schluessel, bezeichnung=bezeichnung)
            db.session.add(kategorie)
        kategorien[schluessel] = kategorie
    db.session.flush()
    return kategorien


def _raeume_fake_daten_auf():
    """Vorherige Seed-Laeufe entfernen, damit das Skript wiederholt laufen kann."""
    Zeugnisnote.query.delete()
    Notenereintrag.query.delete()
    NotenkategorieGewichtung.query.delete()
    Lernfeld.query.delete()
    # schueler_gruppen ist eine reine Zuordnungstabelle (kein Modell) - bulk
    # delete() auf Gruppe raeumt sie nicht mit auf, darum hier explizit zuerst.
    db.session.execute(schueler_gruppen.delete())
    Gruppe.query.delete()
    SchuelerKlasse.query.delete()
    Schueler.query.delete()
    Betrieb.query.delete()
    Klasse.query.delete()
    VorlageGewichtung.query.delete()
    Lernfeldvorlage.query.delete()
    Bildungsgang.query.delete()
    db.session.commit()


def _katalog_anlegen(kategorien):
    bildungsgaenge = {}
    for schluessel, (bezeichnung, vorlagen) in BILDUNGSGAENGE.items():
        bg = Bildungsgang(bezeichnung=bezeichnung)
        db.session.add(bg)
        db.session.flush()
        for nummer, name in vorlagen:
            vorlage = Lernfeldvorlage(bildungsgang_id=bg.id, nummer=nummer, name=name)
            db.session.add(vorlage)
            db.session.flush()
            for kat_schluessel, _bez, gewicht in KATEGORIEN:
                db.session.add(VorlageGewichtung(
                    vorlage_id=vorlage.id,
                    kategorie_id=kategorien[kat_schluessel].id,
                    gewicht=gewicht,
                ))
        bildungsgaenge[schluessel] = bg
    db.session.flush()
    return bildungsgaenge


def _noten_fuer(schueler, lernfeld, kategorien):
    termine = _TERMINE_JE_LERNFELD[lernfeld.id]
    # muendlich: pro Termin (gemeinsames Datum/Bezeichnung wie beim Bulk) fast
    # jede/r eine Note - so sieht die Kategorie-Detailansicht realistisch aus.
    for datum, bez in termine["muendlich"]:
        wuerfel = random.random()
        if wuerfel < 0.08:  # nicht anwesend
            db.session.add(Notenereintrag(
                schueler_id=schueler.id, lernfeld_id=lernfeld.id,
                kategorie_id=kategorien["muendlich_sonstige"].id,
                datum=datum, bezeichnung=bez, abwesend=True,
                kommentar=random.choice([None, "krank", "entschuldigt", "Attest"]),
            ))
        elif wuerfel < 0.95:
            db.session.add(Notenereintrag(
                schueler_id=schueler.id, lernfeld_id=lernfeld.id,
                kategorie_id=kategorien["muendlich_sonstige"].id,
                datum=datum, bezeichnung=bez,
                note_direkt=round(random.uniform(1.0, 4.5), 1),
                kommentar=random.choice([None, None, None, "gute Mitarbeit", "wenig Beteiligung"]),
            ))
    for datum, bez in termine["klassenarbeit"]:
        db.session.add(Notenereintrag(
            schueler_id=schueler.id, lernfeld_id=lernfeld.id,
            kategorie_id=kategorien["klassenarbeit"].id,
            datum=datum, bezeichnung=bez,
            erreichte_punkte=round(random.uniform(0.2, 1.0) * 40, 1), max_punkte=40,
        ))
    for datum, bez in termine["abgabe"]:
        if random.random() < 0.7:
            db.session.add(Notenereintrag(
                schueler_id=schueler.id, lernfeld_id=lernfeld.id,
                kategorie_id=kategorien["abgabe"].id,
                datum=datum, bezeichnung=bez,
                erreichte_punkte=round(random.uniform(0.3, 1.0) * 20, 1), max_punkte=20,
            ))


def _betriebe_anlegen(anzahl=12):
    betriebe = []
    for _ in range(anzahl):
        name = fake.unique.company()
        betrieb = Betrieb(
            name=name,
            ansprechpartner=fake.name(),
            email=f"ausbildung@{fake.domain_name()}",
            telefon=fake.phone_number(),
        )
        db.session.add(betrieb)
        betriebe.append(betrieb)
    db.session.flush()
    return betriebe


def seed():
    _raeume_fake_daten_auf()
    fake.unique.clear()
    kategorien = _get_or_create_kategorien()
    bildungsgaenge = _katalog_anlegen(kategorien)
    betriebe = _betriebe_anlegen()

    for bezeichnung, bg_schluessel in KLASSEN_DATEN:
        bg = bildungsgaenge[bg_schluessel]
        klasse = Klasse(bezeichnung=bezeichnung, bildungsgang_id=bg.id)
        db.session.add(klasse)
        db.session.flush()

        # Wie im echten Betrieb: die Lehrkraft unterrichtet nicht immer alle
        # Lernfelder - hier zufaellig 0-1 weglassen.
        vorlagen = list(bg.lernfeldvorlagen)
        random.shuffle(vorlagen)
        vorlagen = vorlagen[: len(vorlagen) - random.randint(0, 1)]
        lernfelder_aus_vorlagen(klasse, vorlagen)
        db.session.flush()

        for lernfeld in klasse.lernfelder:
            _TERMINE_JE_LERNFELD[lernfeld.id] = _termine_fuer_lernfeld()

        # Kohorte A/B als Beispiel fuer Gruppen (Differenzierung, z.B.
        # gruppenuebergreifende Klassendienst-Paarung).
        gruppe_a = Gruppe(klasse_id=klasse.id, name="Kohorte A")
        gruppe_b = Gruppe(klasse_id=klasse.id, name="Kohorte B")
        db.session.add_all([gruppe_a, gruppe_b])
        db.session.flush()

        for i in range(random.randint(15, 22)):
            geschlecht = random.choices(["w", "m", "d"], weights=[48, 48, 4])[0]
            vorname = fake.first_name_female() if geschlecht == "w" else (
                fake.first_name_male() if geschlecht == "m" else fake.first_name()
            )
            betrieb = random.choice(betriebe) if random.random() < 0.75 else None
            schueler = Schueler(
                nachname=fake.last_name(),
                vorname=vorname,
                geburtsdatum=fake.date_of_birth(minimum_age=16, maximum_age=25),
                einschulungsdatum=date(2025, 8, 1),
                geschlecht=geschlecht,
                email=fake.ascii_free_email(),
                betrieb=betrieb,
                betriebs_email=(
                    f"{vorname.lower()}.{fake.last_name().lower()}@{fake.domain_name()}"
                    if betrieb and random.random() < 0.5 else None
                ),
            )
            db.session.add(schueler)
            db.session.flush()
            db.session.add(SchuelerKlasse(
                schueler_id=schueler.id, klasse_id=klasse.id, von=date(2025, 8, 1), bis=None,
            ))
            (gruppe_a if i % 2 == 0 else gruppe_b).mitglieder.append(schueler)
            for lernfeld in klasse.lernfelder:
                _noten_fuer(schueler, lernfeld, kategorien)

    db.session.commit()

    print(
        f"Fake-Daten erzeugt: {Bildungsgang.query.count()} Bildungsgänge, "
        f"{Betrieb.query.count()} Betriebe, "
        f"{Lernfeldvorlage.query.count()} Lernfeldvorlagen, {Klasse.query.count()} Klassen, "
        f"{Schueler.query.count()} SuS, {Lernfeld.query.count()} Lernfelder, "
        f"{Notenereintrag.query.count()} Noteneinträge."
    )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
