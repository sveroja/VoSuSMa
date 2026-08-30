"""
Einlesen der SuS-Liste aus dem Schulverwaltungs-Export (Untis "LessonStudentList",
TAB-getrennt). Reine Parse-Logik ohne DB-Zugriff - das Anlegen passiert im
Blueprint, damit dort die Dubletten-Prüfung gegen die Klasse laufen kann.
"""
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


# Spaltenueberschriften fuer den Klausur-/Notenimport einer Kategorie
KLAUSUR_SPALTEN = {
    "nachname": ("langname", "nachname", "name"),
    "vorname": ("vorname",),
    "wert": ("wert", "punkte", "note", "ergebnis", "erreicht", "erreichte punkte"),
}


def parse_klausur_liste(rohdaten: bytes) -> tuple[list[dict], list[str]]:
    """Liest eine CSV mit Nachname/Vorname + einem Wert je SuS (Punkte oder Note,
    je nach Ziel-Kategorie). Gibt (zeilen, warnungen) zurueck; jede Zeile:
    nachname, vorname, wert(str, roh), fehler(list). Der Wert wird hier NICHT
    interpretiert - das macht die Route je nach Modus (Punkte/Note)."""
    text = _decode(rohdaten).replace("\r\n", "\n").replace("\r", "\n")
    rohzeilen = [z for z in text.split("\n") if z.strip()]
    if not rohzeilen:
        return [], ["Die Datei ist leer."]

    trenner = "\t" if "\t" in rohzeilen[0] else (";" if ";" in rohzeilen[0] else ",")
    kopf = [z.strip().lower().strip('"') for z in rohzeilen[0].split(trenner)]

    def spalte(feld):
        for name in KLAUSUR_SPALTEN[feld]:
            if name in kopf:
                return kopf.index(name)
        return None

    idx = {feld: spalte(feld) for feld in KLAUSUR_SPALTEN}
    if idx["nachname"] is None or idx["vorname"] is None or idx["wert"] is None:
        return [], [
            "Spalten 'Nachname', 'Vorname' und 'Punkte' (bzw. 'Note'/'Wert') "
            "nicht gefunden – bitte eine Kopfzeile mit diesen Spalten verwenden."
        ]

    def wert(felder, feld):
        i = idx[feld]
        if i is None or i >= len(felder):
            return ""
        return felder[i].strip().strip('"')

    zeilen, warnungen = [], []
    for nr, roh in enumerate(rohzeilen[1:], start=2):
        felder = roh.split(trenner)
        nachname = wert(felder, "nachname")
        vorname = wert(felder, "vorname")
        rohwert = wert(felder, "wert")
        if not nachname and not vorname and not rohwert:
            continue

        fehler = []
        if not nachname or not vorname:
            fehler.append("Nach- oder Vorname fehlt")
        if not rohwert:
            fehler.append("kein Wert")

        zeilen.append({
            "nachname": nachname,
            "vorname": vorname,
            "wert": rohwert,
            "fehler": fehler,
        })

    if not zeilen:
        warnungen.append("Keine Datenzeilen gefunden.")
    return zeilen, warnungen
