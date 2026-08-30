"""
Datenmodell - abgeleitet aus der Analyse von importTool.ods.

Kernentscheidungen aus der Besprechung:
- Gesamtnote wird IMMER aus Noten (Dezimal 1,0-6,0) berechnet, nie aus Prozenten
  gemischt. Prozent ist nur ein Zwischenschritt INNERHALB einer Kategorie
  (Punkte -> Prozent -> Note), niemals kategorieuebergreifend.
- Nur EIN aktives Notenschema (die feine Dezimalskala). Mehrere Schemata sind
  im Modell trotzdem als Daten (nicht Code) abgebildet, falls sich das mal
  aendert - aber aktuell gibt es genau ein aktives.
- Gewichtung von Notenkategorien ist pro Lernfeld konfigurierbar (spiegelt die
  0.4/0.6-Formel aus "Gesamt" wider, Abgabe defaultet auf Gewicht 0 wie im
  Original-Sheet).
- "Lernfeld" ist die Berufsschul-Terminologie und ersetzt den frueheren Begriff
  "Fach". Allgemeinbildende Faecher (Deutsch, WiSo, ...) laufen im selben Modell,
  nur ohne Lernfeld-Nummer (nummer = NULL).
"""
from datetime import date

from app.extensions import db


class _LernfeldNamen:
    """Gemeinsame Anzeige-/Sortierlogik fuer Lernfeld und Lernfeldvorlage
    (beide haben nummer + name)."""

    @property
    def label(self):
        """Anzeigename: "LF 3 – Name" wenn nummeriert, sonst nur der Name."""
        if self.nummer is not None:
            return f"LF {self.nummer} – {self.name}"
        return self.name

    @property
    def sortkey(self):
        """Nummerierte zuerst nach Nummer, danach unnummerierte nach Name."""
        return (self.nummer is None, self.nummer or 0, self.name.lower())


class Bildungsgang(db.Model):
    """Berufsbezeichnung (z.B. "Kaufmann/-frau im Einzelhandel"). Traegt den
    zentral gepflegten Lernfeld-Katalog, aus dem Klassen ihre Lernfelder ziehen."""
    __tablename__ = "bildungsgaenge"

    id = db.Column(db.Integer, primary_key=True)
    bezeichnung = db.Column(db.String(120), nullable=False, unique=True)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)

    lernfeldvorlagen = db.relationship(
        "Lernfeldvorlage", back_populates="bildungsgang", cascade="all, delete-orphan"
    )
    klassen = db.relationship("Klasse", back_populates="bildungsgang")

    @property
    def vorlagen_sortiert(self):
        return sorted(self.lernfeldvorlagen, key=lambda v: v.sortkey)

    def __repr__(self):
        return f"<Bildungsgang {self.bezeichnung}>"


class Lernfeldvorlage(_LernfeldNamen, db.Model):
    """Katalog-Eintrag je Bildungsgang. Wird beim Klasse-Anlegen in ein
    konkretes Lernfeld kopiert (nicht referenziert) - so bleiben abgeschlossene
    Klassen stabil, wenn der Katalog spaeter geaendert wird."""
    __tablename__ = "lernfeldvorlagen"

    id = db.Column(db.Integer, primary_key=True)
    bildungsgang_id = db.Column(db.Integer, db.ForeignKey("bildungsgaenge.id"), nullable=False)
    nummer = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(100), nullable=False)

    bildungsgang = db.relationship("Bildungsgang", back_populates="lernfeldvorlagen")
    gewichtungen = db.relationship(
        "VorlageGewichtung", back_populates="vorlage", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("bildungsgang_id", "name", name="uq_vorlage_bildungsgang_name"),
    )

    def __repr__(self):
        return f"<Lernfeldvorlage {self.label}>"


class VorlageGewichtung(db.Model):
    """Standard-Gewichtung einer Notenkategorie fuer eine Lernfeldvorlage."""
    __tablename__ = "vorlage_gewichtungen"

    id = db.Column(db.Integer, primary_key=True)
    vorlage_id = db.Column(db.Integer, db.ForeignKey("lernfeldvorlagen.id"), nullable=False)
    kategorie_id = db.Column(db.Integer, db.ForeignKey("notenkategorien.id"), nullable=False)
    gewicht = db.Column(db.Float, nullable=False, default=0.0)  # 0.0 - 1.0

    __table_args__ = (
        db.UniqueConstraint("vorlage_id", "kategorie_id", name="uq_vorlage_kategorie"),
    )

    vorlage = db.relationship("Lernfeldvorlage", back_populates="gewichtungen")
    kategorie = db.relationship("Notenkategorie")


class Klasse(db.Model):
    __tablename__ = "klassen"

    id = db.Column(db.Integer, primary_key=True)
    # Klassen laufen ueber mehrere Jahre - kein Schuljahr. Die Zeitachse steckt
    # in SchuelerKlasse.von/bis.
    bezeichnung = db.Column(db.String(50), nullable=False, unique=True)  # z.B. "BFS22a"
    bildungsgang_id = db.Column(db.Integer, db.ForeignKey("bildungsgaenge.id"), nullable=False)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)

    bildungsgang = db.relationship("Bildungsgang", back_populates="klassen")
    schueler_zuordnungen = db.relationship(
        "SchuelerKlasse", back_populates="klasse", cascade="all, delete-orphan"
    )
    lernfelder = db.relationship("Lernfeld", back_populates="klasse", cascade="all, delete-orphan")

    @property
    def anzahl_schueler(self):
        return sum(1 for z in self.schueler_zuordnungen if z.ist_aktiv)

    def __repr__(self):
        return f"<Klasse {self.bezeichnung}>"


class Schueler(db.Model):
    __tablename__ = "schueler"

    id = db.Column(db.Integer, primary_key=True)
    nachname = db.Column(db.String(80), nullable=False)
    vorname = db.Column(db.String(80), nullable=False)
    geburtsdatum = db.Column(db.Date, nullable=True)
    einschulungsdatum = db.Column(db.Date, nullable=True)
    geschlecht = db.Column(db.String(1), nullable=True)  # 'm' | 'w' | 'd', optional
    email = db.Column(db.String(255), nullable=True)
    # dienstliche/betriebliche Mail-Adresse - fuer eine spaetere Funktion
    betriebs_email = db.Column(db.String(255), nullable=True)

    klassen_zuordnungen = db.relationship(
        "SchuelerKlasse", back_populates="schueler", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Schueler {self.nachname}, {self.vorname}>"


class SchuelerKlasse(db.Model):
    """n:m mit Zeitraum - deckt Klassenwechsel/Wiederholung ab."""
    __tablename__ = "schueler_klassen"

    id = db.Column(db.Integer, primary_key=True)
    schueler_id = db.Column(db.Integer, db.ForeignKey("schueler.id"), nullable=False)
    klasse_id = db.Column(db.Integer, db.ForeignKey("klassen.id"), nullable=False)
    von = db.Column(db.Date, nullable=False, default=date.today)
    # bis: NULL oder ein Datum in der Zukunft (z.B. Vertragsende aus dem
    # Untis-Import) -> Zuordnung ist aktiv. Nur ein Datum in der Vergangenheit
    # heisst "nicht mehr in der Klasse".
    bis = db.Column(db.Date, nullable=True)

    schueler = db.relationship("Schueler", back_populates="klassen_zuordnungen")
    klasse = db.relationship("Klasse", back_populates="schueler_zuordnungen")

    @property
    def ist_aktiv(self):
        return self.bis is None or self.bis >= date.today()

    @classmethod
    def aktiv_filter(cls, stichtag=None):
        """SQL-Filter fuer aktive Zuordnungen (bis offen oder in der Zukunft)."""
        stichtag = stichtag or date.today()
        return db.or_(cls.bis.is_(None), cls.bis >= stichtag)


class Lernfeld(_LernfeldNamen, db.Model):
    """Konkretes Lernfeld einer Klasse - beim Klasse-Anlegen aus einer
    Lernfeldvorlage kopiert. Allgemeinbildende Faecher: nummer = NULL."""
    __tablename__ = "lernfelder"

    id = db.Column(db.Integer, primary_key=True)
    nummer = db.Column(db.Integer, nullable=True)  # LF-Nummer aus dem Rahmenlehrplan; NULL bei allg. Faechern
    name = db.Column(db.String(100), nullable=False)
    klasse_id = db.Column(db.Integer, db.ForeignKey("klassen.id"), nullable=False)

    klasse = db.relationship("Klasse", back_populates="lernfelder")
    gewichtungen = db.relationship(
        "NotenkategorieGewichtung", back_populates="lernfeld", cascade="all, delete-orphan"
    )
    # delete-orphan: ein geloeschtes Lernfeld nimmt seine Noteneintraege mit
    noteneintraege = db.relationship(
        "Notenereintrag", back_populates="lernfeld", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Lernfeld {self.label}>"


class Notenkategorie(db.Model):
    """Feste Kategorien wie in der Excel-Mappe: mündlich/sonstige, Klassenarbeit, Abgabe."""
    __tablename__ = "notenkategorien"

    id = db.Column(db.Integer, primary_key=True)
    schluessel = db.Column(db.String(50), unique=True, nullable=False)  # z.B. "muendlich_sonstige"
    bezeichnung = db.Column(db.String(100), nullable=False)


class NotenkategorieGewichtung(db.Model):
    """Bildet z.B. mündlich*0.4 + schriftlich*0.6 aus dem Gesamt-Sheet ab, pro Lernfeld editierbar."""
    __tablename__ = "notenkategorie_gewichtungen"

    id = db.Column(db.Integer, primary_key=True)
    lernfeld_id = db.Column(db.Integer, db.ForeignKey("lernfelder.id"), nullable=False)
    kategorie_id = db.Column(db.Integer, db.ForeignKey("notenkategorien.id"), nullable=False)
    gewicht = db.Column(db.Float, nullable=False, default=0.0)  # 0.0 - 1.0

    __table_args__ = (
        db.UniqueConstraint("lernfeld_id", "kategorie_id", name="uq_lernfeld_kategorie"),
    )

    lernfeld = db.relationship("Lernfeld", back_populates="gewichtungen")
    kategorie = db.relationship("Notenkategorie")


class Notenschema(db.Model):
    """Prozent -> Note Umrechnungstabelle. Aktuell genau ein aktives Schema (feine Dezimalskala)."""
    __tablename__ = "notenschemata"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)

    stufen = db.relationship(
        "NotenschemaStufe", back_populates="schema",
        order_by="NotenschemaStufe.von_prozent", cascade="all, delete-orphan"
    )


class NotenschemaStufe(db.Model):
    __tablename__ = "notenschema_stufen"

    id = db.Column(db.Integer, primary_key=True)
    schema_id = db.Column(db.Integer, db.ForeignKey("notenschemata.id"), nullable=False)
    von_prozent = db.Column(db.Integer, nullable=False)
    bis_prozent = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Float, nullable=False)

    schema = db.relationship("Notenschema", back_populates="stufen")


class Notenereintrag(db.Model):
    """
    Einzelne Note. Deckt beide Muster aus der Excel-Mappe ab:
    - muendlich/sonstige: note_direkt gesetzt (freie Dezimalnote je Termin)
    - Klassenarbeit/Abgabe: erreichte_punkte + max_punkte gesetzt,
      Note wird zur Anzeigezeit ueber das aktive Notenschema berechnet
      (nicht redundant gespeichert, sonst Inkonsistenz bei Schema-Aenderung)
    manuelle_note sticht immer, egal was sonst gesetzt ist (wie "Note manuell" in der Mappe).
    """
    __tablename__ = "noteneintraege"

    id = db.Column(db.Integer, primary_key=True)
    schueler_id = db.Column(db.Integer, db.ForeignKey("schueler.id"), nullable=False)
    lernfeld_id = db.Column(db.Integer, db.ForeignKey("lernfelder.id"), nullable=False)
    kategorie_id = db.Column(db.Integer, db.ForeignKey("notenkategorien.id"), nullable=False)
    datum = db.Column(db.Date, nullable=False, default=date.today)
    bezeichnung = db.Column(db.String(150), nullable=True)  # z.B. "KA1", "Hausaufgabe 15.10."

    erreichte_punkte = db.Column(db.Float, nullable=True)
    max_punkte = db.Column(db.Float, nullable=True)
    note_direkt = db.Column(db.Float, nullable=True)
    manuelle_note = db.Column(db.Float, nullable=True)

    schueler = db.relationship("Schueler")
    lernfeld = db.relationship("Lernfeld", back_populates="noteneintraege")
    kategorie = db.relationship("Notenkategorie")
