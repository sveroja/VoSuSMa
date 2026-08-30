"""
Platzhalter fuer die spaetere WebDAV-Synchronisierung zu einer eigenen
Nextcloud-Instanz. Noch NICHT implementiert - dient nur als vorgemerkter
Anknuepfungspunkt, damit die spaetere Umsetzung nicht komplett bei null
anfaengt.

Geplanter Ablauf (siehe Absprache):
1. Konsistenter Snapshot der DB per `VACUUM INTO` erzeugen (niemals waehrend
   einer offenen Transaktion), z.B. nach instance/sync/prod-<timestamp>.sqlite3.
2. Einfachen Lock-Mechanismus pruefen/setzen (z.B. Lock-Datei auf dem
   WebDAV-Share mit Geraete-ID + Zeitstempel), um gleichzeitiges Offline-
   Arbeiten auf zwei Geraeten zu verhindern.
3. Snapshot per WebDAV zur Nextcloud-Instanz hochladen.
4. Lock wieder freigeben.

TODO: WebDAV-Client (z.B. `webdavclient3`) und Zugangsdaten-Handling
(Umgebungsvariablen, nicht im Repo) ergaenzen, sobald dieser Teil umgesetzt
wird.
"""


def erstelle_snapshot(*args, **kwargs):
    raise NotImplementedError("Sync ist noch nicht implementiert (siehe Modul-Docstring).")


def push_snapshot(*args, **kwargs):
    raise NotImplementedError("Sync ist noch nicht implementiert (siehe Modul-Docstring).")
