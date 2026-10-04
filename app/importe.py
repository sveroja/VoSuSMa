"""
Einlesen der SuS-Liste aus dem Schulverwaltungs-Export (Untis "LessonStudentList",
TAB-getrennt). Reine Parse-Logik ohne DB-Zugriff - das Anlegen passiert im
Blueprint, damit dort die Dubletten-Prüfung gegen die Klasse laufen kann.
"""
import csv
import io
import re
from datetime import date, datetime

# Interner Feldname -> moegliche Spaltenueberschriften im Export
SPALTEN = {
    "nachname": ("langname", "nachname", "name"),
    "vorname": ("vorname",),
    "klasse": ("klasse",),
    "geschlecht": ("geschlecht",),
    "eintritt": ("eintrittsdatum", "eintritt"),
    "austritt": ("austrittsdatum", "austritt"),
    "email": ("e-mail adresse", "e-mail", "email", "e-mail-adresse"),
}

GESCHLECHT_MAP = {
    "m": "m", "männlich": "m", "maennlich": "m",
    "w": "w", "weiblich": "w", "f": "w",
    "d": "d", "divers": "d", "x": "d",
}


def _decode(rohdaten: bytes) -> str:
    for kodierung in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return rohdaten.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return rohdaten.decode("utf-8", errors="replace")


def _datum(text: str) -> date | None:
    text = (text or "").strip()
    if not text:
        return None
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text, muster).date()
        except ValueError:
            continue
    return None


def parse_sus_liste(rohdaten: bytes) -> tuple[list[dict], list[str]]:
    """Gibt (zeilen, warnungen) zurück. Jede Zeile ist ein dict mit
    nachname, vorname, geschlecht, email, von, bis, quelle_klasse, fehler(list)."""
    text = _decode(rohdaten).replace("\r\n", "\n").replace("\r", "\n")
    rohzeilen = [z for z in text.split("\n") if z.strip()]
    warnungen: list[str] = []

    if not rohzeilen:
        return [], ["Die Datei ist leer."]

    trenner = "\t" if "\t" in rohzeilen[0] else (";" if ";" in rohzeilen[0] else ",")
    kopf = [z.strip().lower().strip('"') for z in rohzeilen[0].split(trenner)]

    def spalte(feld: str) -> int | None:
        for name in SPALTEN[feld]:
            if name in kopf:
                return kopf.index(name)
        return None

    idx = {feld: spalte(feld) for feld in SPALTEN}
    if idx["nachname"] is None or idx["vorname"] is None:
        return [], [
            "Spalten 'Langname'/'Vorname' nicht gefunden – ist das der richtige Export?"
        ]

    def wert(felder: list[str], feld: str) -> str:
        i = idx[feld]
        if i is None or i >= len(felder):
            return ""
        return felder[i].strip().strip('"')

    zeilen: list[dict] = []
    for nr, roh in enumerate(rohzeilen[1:], start=2):
        felder = roh.split(trenner)
        nachname = wert(felder, "nachname")
        vorname = wert(felder, "vorname")
        if not nachname and not vorname:
            continue

        fehler: list[str] = []
        if not nachname or not vorname:
            fehler.append("Nach- oder Vorname fehlt")

        geschlecht_roh = wert(felder, "geschlecht").lower()
        geschlecht = GESCHLECHT_MAP.get(geschlecht_roh)
        if geschlecht_roh and geschlecht is None:
            warnungen.append(f"Zeile {nr}: Geschlecht '{geschlecht_roh}' ignoriert.")

        von = _datum(wert(felder, "eintritt"))
        bis = _datum(wert(felder, "austritt"))
        if wert(felder, "eintritt") and von is None:
            warnungen.append(f"Zeile {nr}: Eintrittsdatum unlesbar, wird auf heute gesetzt.")

        zeilen.append({
            "nachname": nachname,
            "vorname": vorname,
            "geschlecht": geschlecht,
            "email": wert(felder, "email") or None,
            "von": von,
            "bis": bis,
            "quelle_klasse": wert(felder, "klasse") or None,
            "fehler": fehler,
        })

    if not zeilen:
        warnungen.append("Keine Datenzeilen gefunden.")
    return zeilen, warnungen


# Spaltenueberschriften fuer den Betriebe-Import - eigenes schlankes Format
# (Spalten name/ansprechpartner/email/telefon) ODER der NOBO-Anmeldungen-Export,
# der Betrieb-Spalten je SuS-Zeile mitfuehrt.
BETRIEB_SPALTEN = {
    "name": ("name", "betrieb", "firma"),
    "ansprechpartner": ("ansprechpartner",),
    "email": ("email", "e-mail", "betrieb_email", "betrieb-email"),
    "telefon": ("telefon", "tel"),
}


def parse_betriebe_liste(rohdaten: bytes) -> tuple[list[dict], list[str]]:
    """Liest eine Betriebe-CSV. Dedupliziert nach Name (case-insensitiv) - im
    NOBO-Export z.B. kommt derselbe Betrieb ueber mehrere SuS-Zeilen vor. Gibt
    (zeilen, warnungen) zurueck; jede Zeile: name, ansprechpartner, email,
    telefon, fehler(list)."""
    text = _decode(rohdaten).replace("\r\n", "\n").replace("\r", "\n")
    rohzeilen = [z for z in text.split("\n") if z.strip()]
    if not rohzeilen:
        return [], ["Die Datei ist leer."]

    trenner = ";" if ";" in rohzeilen[0] else ("\t" if "\t" in rohzeilen[0] else ",")
    kopf = [z.strip().lower().strip('"') for z in rohzeilen[0].split(trenner)]

    def spalte(feld):
        for name in BETRIEB_SPALTEN[feld]:
            if name in kopf:
                return kopf.index(name)
        return None

    idx = {feld: spalte(feld) for feld in BETRIEB_SPALTEN}
    if idx["name"] is None:
        return [], [
            "Spalte 'Name' (bzw. 'Betrieb') nicht gefunden – bitte eine Kopfzeile "
            "mit dieser Spalte verwenden."
        ]

    def wert(felder, feld):
        i = idx[feld]
        if i is None or i >= len(felder):
            return ""
        return felder[i].strip().strip('"')

    gesehen: dict[str, dict] = {}
    for roh in rohzeilen[1:]:
        felder = roh.split(trenner)
        name = wert(felder, "name")
        if not name or name.lower() in gesehen:
            continue
        gesehen[name.lower()] = {
            "name": name,
            "ansprechpartner": wert(felder, "ansprechpartner") or None,
            "email": wert(felder, "email") or None,
            "telefon": wert(felder, "telefon") or None,
            "fehler": [],
        }

    zeilen = list(gesehen.values())
    warnungen = [] if zeilen else ["Keine Datenzeilen gefunden."]
    return zeilen, warnungen


# Spaltenueberschriften fuer den NOBO-Anmeldungen-Export (Online-Anmeldetool der
# Schule) - eine Zeile je SuS inkl. des zugeordneten Ausbildungsbetriebs.
NOBO_SPALTEN = {
    "nachname": ("nachname",),
    "vorname": ("vorname",),
    "geburtsdatum": ("geburtsdatum",),
    "betrieb": ("betrieb",),
    "betrieb_email": ("betrieb_email",),
}


def parse_nobo_anmeldungen(rohdaten: bytes) -> tuple[list[dict], list[str]]:
    """Liest den NOBO-Anmeldungen-Export (Semikolon-getrennt). Andere Spalten
    des Exports (beruf, zug, strasse, plz, ort, status, ...) werden bewusst
    ignoriert - dafuer gibt es aktuell keine passenden Felder im Modell. Gibt
    (zeilen, warnungen) zurueck; jede Zeile: nachname, vorname, geburtsdatum,
    betrieb, betrieb_email, fehler(list)."""
    text = _decode(rohdaten).replace("\r\n", "\n").replace("\r", "\n")
    rohzeilen = [z for z in text.split("\n") if z.strip()]
    if not rohzeilen:
        return [], ["Die Datei ist leer."]

    trenner = ";" if ";" in rohzeilen[0] else ("\t" if "\t" in rohzeilen[0] else ",")
    kopf = [z.strip().lower().strip('"') for z in rohzeilen[0].split(trenner)]

    def spalte(feld):
        for name in NOBO_SPALTEN[feld]:
            if name in kopf:
                return kopf.index(name)
        return None

    idx = {feld: spalte(feld) for feld in NOBO_SPALTEN}
    if idx["nachname"] is None or idx["vorname"] is None:
        return [], [
            "Spalten 'nachname'/'vorname' nicht gefunden – ist das der richtige "
            "NOBO-Anmeldungen-Export?"
        ]

    def wert(felder, feld):
        i = idx[feld]
        if i is None or i >= len(felder):
            return ""
        return felder[i].strip().strip('"')

    zeilen: list[dict] = []
    warnungen: list[str] = []
    for nr, roh in enumerate(rohzeilen[1:], start=2):
        felder = roh.split(trenner)
        nachname = wert(felder, "nachname")
        vorname = wert(felder, "vorname")
        if not nachname and not vorname:
            continue

        fehler = []
        if not nachname or not vorname:
            fehler.append("Nach- oder Vorname fehlt")

        geburtsdatum_roh = wert(felder, "geburtsdatum")
        geburtsdatum = _datum(geburtsdatum_roh)
        if geburtsdatum_roh and geburtsdatum is None:
            warnungen.append(f"Zeile {nr}: Geburtsdatum unlesbar, wird leer gelassen.")

        zeilen.append({
            "nachname": nachname,
            "vorname": vorname,
            "geburtsdatum": geburtsdatum,
            "betrieb": wert(felder, "betrieb") or None,
            "betrieb_email": wert(felder, "betrieb_email") or None,
            "fehler": fehler,
        })

    if not zeilen:
        warnungen.append("Keine Datenzeilen gefunden.")
    return zeilen, warnungen


# Spaltenueberschriften fuer den Klausur-/Notenimport einer Kategorie
KLAUSUR_SPALTEN = {
    "nachname": ("langname", "nachname", "name"),
    "vorname": ("vorname",),
    "wert": ("wert", "punkte", "note", "ergebnis", "erreicht", "erreichte punkte"),
}

# Moodle-Testexport: Punktespalte heisst "Bewertung/100" bzw. "Bewertung/100,00"
# (engl. "Grade/100.00") - die Zahl hinter dem "/" ist die im Test eingestellte
# Maximalpunktzahl. Die Einzelfragen-Spalten ("F. 1 /10,00") passen bewusst nicht.
_MOODLE_BEWERTUNG = re.compile(r"^(?:bewertung|grade)\s*/\s*(\d+(?:[.,]\d+)?)$")

# Moodle haengt eine Schlusszeile mit dem Klassenschnitt an - keine SuS.
_MOODLE_SCHNITTZEILE = ("gesamtdurchschnitt", "overall average")

# Wert-Zellen, die "nicht mitgeschrieben" bedeuten (Moodle-Export mit allen SuS)
NICHT_MITGESCHRIEBEN = {"-", "–", ""}


def parse_klausur_liste(rohdaten: bytes) -> tuple[list[dict], list[str], float | None]:
    """Liest eine CSV mit Nachname/Vorname + einem Wert je SuS (Punkte oder Note,
    je nach Ziel-Kategorie). Gibt (zeilen, warnungen, max_punkte) zurueck;
    max_punkte stammt aus einem Moodle-Kopf "Bewertung/<max>", sonst None.
    Jede Zeile: nachname, vorname, wert(str, roh), nachschreiben(bool), fehler(list).
    Der Wert wird hier NICHT interpretiert - das macht die Route je nach Modus.
    Echtes CSV-Parsing (Anfuehrungszeichen!), weil Moodle komma-getrennt
    exportiert und Dezimalwerte als "87,50" in Anfuehrungszeichen schreibt."""
    text = _decode(rohdaten).replace("\r\n", "\n").replace("\r", "\n")
    rohzeilen = [z for z in text.split("\n") if z.strip()]
    if not rohzeilen:
        return [], ["Die Datei ist leer."], None

    erste = rohzeilen[0]
    trenner = "\t" if "\t" in erste else (";" if ";" in erste else ",")
    tabelle = list(csv.reader(io.StringIO("\n".join(rohzeilen)), delimiter=trenner))
    kopf = [z.strip().lower() for z in tabelle[0]]

    max_punkte = None
    idx = {}
    for feld, namen in KLAUSUR_SPALTEN.items():
        idx[feld] = next((kopf.index(n) for n in namen if n in kopf), None)
    if idx["wert"] is None:
        for i, name in enumerate(kopf):
            m = _MOODLE_BEWERTUNG.match(name)
            if m:
                idx["wert"] = i
                max_punkte = float(m.group(1).replace(",", "."))
                break

    if idx["nachname"] is None or idx["vorname"] is None or idx["wert"] is None:
        return [], [
            "Spalten 'Nachname', 'Vorname' und 'Punkte' (bzw. 'Note'/'Wert' oder "
            "Moodle 'Bewertung/100') nicht gefunden – bitte eine Kopfzeile mit "
            "diesen Spalten verwenden."
        ], None

    def wert(felder, feld):
        i = idx[feld]
        if i is None or i >= len(felder):
            return ""
        return felder[i].strip()

    zeilen, warnungen = [], []
    for felder in tabelle[1:]:
        nachname = wert(felder, "nachname")
        vorname = wert(felder, "vorname")
        rohwert = wert(felder, "wert")
        if not nachname and not vorname:
            continue
        if not vorname and nachname.lower().startswith(_MOODLE_SCHNITTZEILE):
            continue

        fehler = []
        if not nachname or not vorname:
            fehler.append("Nach- oder Vorname fehlt")

        zeilen.append({
            "nachname": nachname,
            "vorname": vorname,
            "wert": rohwert,
            "nachschreiben": rohwert in NICHT_MITGESCHRIEBEN,
            "fehler": fehler,
        })

    if not zeilen:
        warnungen.append("Keine Datenzeilen gefunden.")
    return zeilen, warnungen, max_punkte
