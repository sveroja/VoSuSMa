"""
Befuellt die Dev-Datenbank mit Fake-Daten (Faker, Locale de_DE), strukturell
identisch zum echten Schema. Bricht sicherheitshalber ab, wenn APP_ENV nicht
"dev" ist, damit hier niemals versehentlich in prod.sqlite3 geschrieben wird.

Aufruf:
    python seed.py
"""
import random
import sys
from datetime import date

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
    Bildungsgang,
    Klasse,
    Lernfeld,
    Lernfeldvorlage,
    Notenereintrag,
    Notenkategorie,
    NotenkategorieGewichtung,
    Schueler,
    SchuelerKlasse,
    VorlageGewichtung,
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
    Notenereintrag.query.delete()
    NotenkategorieGewichtung.query.delete()
    Lernfeld.query.delete()
    SchuelerKlasse.query.delete()
    Schueler.query.delete()
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
    for _ in range(random.randint(2, 4)):
        db.session.add(Notenereintrag(
            schueler_id=schueler.id, lernfeld_id=lernfeld.id,
            kategorie_id=kategorien["muendlich_sonstige"].id,
            datum=fake.date_between(start_date="-6M", end_date="today"),
            bezeichnung="Mitarbeit",
            note_direkt=round(random.uniform(1.0, 4.5), 1),
        ))
    for i in range(random.randint(1, 2)):
        db.session.add(Notenereintrag(
            schueler_id=schueler.id, lernfeld_id=lernfeld.id,
            kategorie_id=kategorien["klassenarbeit"].id,
            datum=fake.date_between(start_date="-6M", end_date="today"),
            bezeichnung=f"Klassenarbeit {i + 1}",
            erreichte_punkte=round(random.uniform(0.2, 1.0) * 40, 1), max_punkte=40,
        ))
    if random.random() < 0.6:
        db.session.add(Notenereintrag(
            schueler_id=schueler.id, lernfeld_id=lernfeld.id,
            kategorie_id=kategorien["abgabe"].id,
            datum=fake.date_between(start_date="-6M", end_date="today"),
            bezeichnung="Hausaufgabe",
            erreichte_punkte=round(random.uniform(0.3, 1.0) * 20, 1), max_punkte=20,
        ))


def seed():
    _raeume_fake_daten_auf()
    kategorien = _get_or_create_kategorien()
    bildungsgaenge = _katalog_anlegen(kategorien)

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

        for _ in range(random.randint(15, 22)):
            geschlecht = random.choices(["w", "m", "d"], weights=[48, 48, 4])[0]
            vorname = fake.first_name_female() if geschlecht == "w" else (
                fake.first_name_male() if geschlecht == "m" else fake.first_name()
            )
            schueler = Schueler(
                nachname=fake.last_name(),
                vorname=vorname,
                geburtsdatum=fake.date_of_birth(minimum_age=16, maximum_age=25),
                einschulungsdatum=date(2025, 8, 1),
                geschlecht=geschlecht,
                email=fake.ascii_free_email(),
            )
            db.session.add(schueler)
            db.session.flush()
            db.session.add(SchuelerKlasse(
                schueler_id=schueler.id, klasse_id=klasse.id, von=date(2025, 8, 1), bis=None,
            ))
            for lernfeld in klasse.lernfelder:
                _noten_fuer(schueler, lernfeld, kategorien)

    db.session.commit()

    print(
        f"Fake-Daten erzeugt: {Bildungsgang.query.count()} Bildungsgänge, "
        f"{Lernfeldvorlage.query.count()} Lernfeldvorlagen, {Klasse.query.count()} Klassen, "
        f"{Schueler.query.count()} SuS, {Lernfeld.query.count()} Lernfelder, "
        f"{Notenereintrag.query.count()} Noteneinträge."
    )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
