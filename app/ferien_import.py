"""
Liest eine lokal hochgeladene .ics-Datei (Ferienkalender, z.B. einmal jaehrlich
von der offiziellen Landes-Seite heruntergeladen) rein lokal ein - bewusst KEIN
Netzwerkaufruf/Abo (siehe CLAUDE.md). Nur eine handgeschriebene Mini-Parser
fuer VEVENT/SUMMARY/DTSTART/DTEND, keine neue Abhaengigkeit.
"""
from datetime import date, datetime, timedelta


def _entfalten(text: str) -> list[str]:
    """RFC5545-Zeilenfaltung rueckgaengig machen: eine Zeile, die mit Leerzeichen
    oder Tab beginnt, gehoert zur vorherigen Zeile."""
    rohzeilen = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    zeilen: list[str] = []
    for z in rohzeilen:
        if z.startswith((" ", "\t")) and zeilen:
            zeilen[-1] += z[1:]
        else:
            zeilen.append(z)
    return zeilen


def _datum(wert: str) -> date | None:
    wert = wert.strip()
    kern = wert.split("T", 1)[0]  # DATE-TIME -> nur den Datumsteil
    try:
        return datetime.strptime(kern, "%Y%m%d").date()
    except ValueError:
        return None


def parse_ics_ferien(rohdaten: bytes) -> tuple[list[dict], list[str]]:
    """Gibt (zeilen, warnungen) zurueck. Jede Zeile: bezeichnung, von, bis
    (beide inklusive - ICS-DTEND bei ganztaegigen Terminen ist exklusiv und
    wird hier um einen Tag zurueckgerechnet)."""
    try:
        text = rohdaten.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = rohdaten.decode("latin-1")

    zeilen = _entfalten(text)
    termine: list[dict] = []
    warnungen: list[str] = []

    aktuell: dict | None = None
    for zeile in zeilen:
        if zeile.strip() == "BEGIN:VEVENT":
            aktuell = {}
            continue
        if zeile.strip() == "END:VEVENT":
            if aktuell is not None:
                bez = aktuell.get("SUMMARY", "").strip() or "Ferientag"
                von = aktuell.get("DTSTART")
                bis = aktuell.get("DTEND")
                if von is None:
                    warnungen.append(f"Termin '{bez}' ohne lesbares Startdatum ignoriert.")
                else:
                    if bis is None:
                        bis = von
                    elif bis > von:
                        bis = bis - timedelta(days=1)  # DTEND exklusiv bei Ganztages-Terminen
                    termine.append({"bezeichnung": bez, "von": von, "bis": bis})
            aktuell = None
            continue
        if aktuell is None or ":" not in zeile:
            continue

        schluessel, _, wert = zeile.partition(":")
        name = schluessel.split(";", 1)[0].strip().upper()
        if name == "SUMMARY":
            aktuell["SUMMARY"] = wert
        elif name == "DTSTART":
            aktuell["DTSTART"] = _datum(wert)
        elif name == "DTEND":
            aktuell["DTEND"] = _datum(wert)

    if not termine:
        warnungen.append("Keine Termine (VEVENT) in der Datei gefunden.")
    return termine, warnungen
