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


class Betrieb(db.Model):
    """Ausbildungsbetrieb. Optional an SuS haengbar (Schueler.betrieb_id).
    Zentral unter /admin/betriebe gepflegt."""
    __tablename__ = "betriebe"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    ansprechpartner = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(255), nullable=True)  # Ausbilder-/Betriebs-Kontakt
    telefon = db.Column(db.String(50), nullable=True)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)

    schueler = db.relationship("Schueler", back_populates="betrieb")

    @property
    def anzahl_schueler(self):
        return len(self.schueler)

    def __repr__(self):
        return f"<Betrieb {self.name}>"


class Klasse(db.Model):
    __tablename__ = "klassen"

    id = db.Column(db.Integer, primary_key=True)
    # Klassen laufen ueber mehrere Jahre - kein Schuljahr. Die Zeitachse steckt
    # in SchuelerKlasse.von/bis.
    bezeichnung = db.Column(db.String(50), nullable=False, unique=True)  # z.B. "BFS22a"
    bildungsgang_id = db.Column(db.Integer, db.ForeignKey("bildungsgaenge.id"), nullable=False)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)
    # Freitext fuer die Klassendienste-Druckseite (Aufgabenbeschreibung). Leer -> Standardtext.
    dienst_hinweis = db.Column(db.Text, nullable=True)

    bildungsgang = db.relationship("Bildungsgang", back_populates="klassen")
    schueler_zuordnungen = db.relationship(
        "SchuelerKlasse", back_populates="klasse", cascade="all, delete-orphan"
    )
    lernfelder = db.relationship("Lernfeld", back_populates="klasse", cascade="all, delete-orphan")
    dienste = db.relationship(
        "Klassendienst", back_populates="klasse", cascade="all, delete-orphan",
        order_by="Klassendienst.datum",
    )
    blockwochen = db.relationship(
        "Blockwoche", back_populates="klasse", cascade="all, delete-orphan"
    )
    gruppen = db.relationship(
        "Gruppe", back_populates="klasse", cascade="all, delete-orphan",
        order_by="Gruppe.name",
    )

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
    email = db.Column(db.String(255), nullable=True)  # private Mail der SuS
    # Arbeitsmail der SuS im Betrieb (persoenlich). Getrennt vom allgemeinen
    # Betriebs-Kontakt Betrieb.email.
    betriebs_email = db.Column(db.String(255), nullable=True)
    betrieb_id = db.Column(db.Integer, db.ForeignKey("betriebe.id"), nullable=True)

    betrieb = db.relationship("Betrieb", back_populates="schueler")
    klassen_zuordnungen = db.relationship(
        "SchuelerKlasse", back_populates="schueler", cascade="all, delete-orphan"
    )
    gruppen = db.relationship(
        "Gruppe", secondary="schueler_gruppen", back_populates="mitglieder"
    )

    @property
    def betrieb_mail_anzeige(self):
        """Fuer die SuS-Liste: Mail des zugeordneten Betriebs, sonst die
        persoenliche Arbeitsmail als Fallback."""
        if self.betrieb and self.betrieb.email:
            return self.betrieb.email
        return self.betriebs_email or None

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


# n:m zwischen Schueler und Gruppe - reine Zuordnungstabelle, kein eigenes Modell.
schueler_gruppen = db.Table(
    "schueler_gruppen",
    db.Column("schueler_id", db.Integer, db.ForeignKey("schueler.id"), primary_key=True),
    db.Column("gruppe_id", db.Integer, db.ForeignKey("gruppen.id"), primary_key=True),
)


class Gruppe(db.Model):
    """Frei benennbare Untergruppe innerhalb einer Klasse (z.B. Kohorte A/B,
    Projektteam) - Grundlage fuer Differenzierung, u.a. die gruppenuebergreifende
    Klassendienst-Paarung (siehe dienst_service.rota_generieren)."""
    __tablename__ = "gruppen"

    id = db.Column(db.Integer, primary_key=True)
    klasse_id = db.Column(db.Integer, db.ForeignKey("klassen.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)

    klasse = db.relationship("Klasse", back_populates="gruppen")
    mitglieder = db.relationship(
        "Schueler", secondary=schueler_gruppen, back_populates="gruppen"
    )

    __table_args__ = (
        db.UniqueConstraint("klasse_id", "name", name="uq_gruppe_klasse_name"),
    )

    def __repr__(self):
        return f"<Gruppe {self.name}>"


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
    zeugnisnoten = db.relationship(
        "Zeugnisnote", back_populates="lernfeld", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Lernfeld {self.label}>"


class Zeugnisnote(db.Model):
    """Zeugnis-Dokumentation je SuS und Lernfeld: manuell festgelegte Noten
    fuer Halbjahr 1 und 2 (wie "Note manuell" im Excel-"Gesamt") plus
    Selbsteinschaetzung der SuS und freie Bemerkung. Steht bewusst NEBEN der
    berechneten Gesamtnote statt sie zu ersetzen - Zeugnisnoten sind eine
    paedagogische Entscheidung, die Berechnung bleibt als Orientierung sichtbar.
    Alle Felder optional; eine Zeile ohne jeden Inhalt wird geloescht."""
    __tablename__ = "zeugnisnoten"

    id = db.Column(db.Integer, primary_key=True)
    lernfeld_id = db.Column(db.Integer, db.ForeignKey("lernfelder.id"), nullable=False)
    schueler_id = db.Column(db.Integer, db.ForeignKey("schueler.id"), nullable=False)
    note_hj1 = db.Column(db.Float, nullable=True)
    selbsteinschaetzung = db.Column(db.String(100), nullable=True)
    bemerkung = db.Column(db.Text, nullable=True)
    note_hj2 = db.Column(db.Float, nullable=True)

    lernfeld = db.relationship("Lernfeld", back_populates="zeugnisnoten")
    schueler = db.relationship("Schueler")

    __table_args__ = (
        db.UniqueConstraint("lernfeld_id", "schueler_id", name="uq_zeugnisnote_lernfeld_schueler"),
    )


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
    # abwesend: SuS war bei dieser Erfassung nicht da ("na"). Dokumentiert, zaehlt
    # aber nicht in den Schnitt (note_aus_eintrag -> None).
    abwesend = db.Column(db.Boolean, nullable=False, default=False)
    kommentar = db.Column(db.String(255), nullable=True)

    schueler = db.relationship("Schueler")
    lernfeld = db.relationship("Lernfeld", back_populates="noteneintraege")
    kategorie = db.relationship("Notenkategorie")


class Ferienzeitraum(db.Model):
    """Manuell gepflegter Ferienkalender (Schulferien + bewegliche Ferientage).
    Bewusst ohne externen API-/ICS-Abgleich (siehe CLAUDE.md - keine externen
    Netzwerkaufrufe) - stattdessen Datei-Import (app/ferien_import.py), der eine
    einmal heruntergeladene .ics-Datei rein lokal einliest. Treibt sowohl die
    Blockplanung (Kopfbaender) als auch den Klassendienst-Generator (Tage
    ueberspringen)."""
    __tablename__ = "ferienzeitraeume"

    id = db.Column(db.Integer, primary_key=True)
    bezeichnung = db.Column(db.String(120), nullable=False)  # z.B. "Sommerferien", "Beweglicher Ferientag"
    von = db.Column(db.Date, nullable=False)
    bis = db.Column(db.Date, nullable=False)  # inklusive, von == bis fuer Einzeltage

    def __repr__(self):
        return f"<Ferienzeitraum {self.bezeichnung} {self.von}-{self.bis}>"


class Blockwoche(db.Model):
    """Blockplanung: markiert eine Kalenderwoche, in der eine Klasse in der
    Schule ist (duale Ausbildung im Blockunterricht - nicht jede Woche).
    Zeilen existieren nur fuer 'anwesend'-Wochen; eine Klasse ohne jede Zeile in
    einem Schuljahr gilt als durchgehend woechentlich anwesend (Normalfall)."""
    __tablename__ = "blockwochen"

    id = db.Column(db.Integer, primary_key=True)
    klasse_id = db.Column(db.Integer, db.ForeignKey("klassen.id"), nullable=False)
    schuljahr = db.Column(db.Integer, nullable=False)  # Startjahr, z.B. 2026 fuer 2026/2027
    kw = db.Column(db.Integer, nullable=False)  # ISO-Kalenderwoche 1-53
    iso_jahr = db.Column(db.Integer, nullable=False)  # ISO-Jahr der KW (Jahreswechsel bei KW1/52/53)

    klasse = db.relationship("Klasse", back_populates="blockwochen")

    __table_args__ = (
        db.UniqueConstraint("klasse_id", "iso_jahr", "kw", name="uq_blockwoche_klasse_kw"),
    )


class Klassendienst(db.Model):
    """Ein Tag Klassendienst (zu zweit) - Reihum-Rotation aus der Excel-Vorlage.
    schueler2 optional (Dienst auch mit nur einer Person moeglich)."""
    __tablename__ = "klassendienste"

    id = db.Column(db.Integer, primary_key=True)
    klasse_id = db.Column(db.Integer, db.ForeignKey("klassen.id"), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    schueler1_id = db.Column(db.Integer, db.ForeignKey("schueler.id"), nullable=True)
    schueler2_id = db.Column(db.Integer, db.ForeignKey("schueler.id"), nullable=True)

    klasse = db.relationship("Klasse", back_populates="dienste")
    schueler1 = db.relationship("Schueler", foreign_keys=[schueler1_id])
    schueler2 = db.relationship("Schueler", foreign_keys=[schueler2_id])

    __table_args__ = (
        db.UniqueConstraint("klasse_id", "datum", name="uq_klassendienst_klasse_datum"),
    )


class DashboardLink(db.Model):
    """Frei pflegbare Link-Kachel auf der Startseite (Schulalltag-Links wie
    WebUntis, Stundenplan, Intranet, ...)."""
    __tablename__ = "dashboard_links"

    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(8), nullable=True)  # optionales Emoji
    reihenfolge = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<DashboardLink {self.titel}>"
