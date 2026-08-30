# VoSuSMa (Vocational SuS Management) - Hinweise für Claude Code

## Datenschutz - höchste Priorität, gilt für JEDE Session

Dieses Projekt verwaltet echte Schülerdaten (SuS) in `instance/prod.sqlite3`.
Diese Datei enthält personenbezogene Daten im Sinne der DSGVO.

**Verbindliche Regeln:**

- `instance/prod.sqlite3` NIEMALS lesen, öffnen, per SQL/Skript abfragen oder
  in irgendeiner Form ausgeben - auch nicht auszugsweise zur Fehlersuche,
  auch nicht "nur zum Zählen von Zeilen".
- Entwicklung, Debugging und Tests laufen ausschliesslich gegen
  `instance/dev.sqlite3` (Faker-generierte Fake-Daten, siehe `seed.py`).
  `APP_ENV` steht dafür immer auf `dev`, nie explizit auf `prod` setzen,
  ausser der Nutzer verlangt es ausdrücklich für einen einzelnen Schritt.
- Wird ein Prod-Bug gemeldet: das Problem anhand von `seed.py` nachstellen
  (bei Bedarf `seed.py` um einen vergleichbaren Fall ergänzen), statt echte
  Daten anzufassen.
- `instance/` bleibt in `.gitignore`. Niemals versuchen, Dateien daraus zu
  committen, zu pushen, in einen PR/Issue-Text zu kopieren oder anderweitig
  aus dem lokalen Dateisystem herauszureichen (z.B. an ein externes Tool).
- Keine echten Namen, Noten oder sonstigen Schülerdaten in Commit-Messages,
  Code-Kommentaren, Fehlermeldungen oder Beispielen verwenden - auch nicht
  als "nur ein Beispiel".
- Die App selbst macht bewusst keine externen Netzwerkaufrufe (kein
  Tracking/Analytics, keine Cloud-Anbindung ausser dem später geplanten,
  selbst gehosteten WebDAV/Nextcloud-Sync). Das soll so bleiben - keine neue
  Abhängigkeit einführen, die Daten an Dritte sendet.

## Stack

Python + Flask + SQLite, kein Docker, kein LibreOffice Base. Details siehe
README.md.
