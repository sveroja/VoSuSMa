# VoSuSMa

**Vo**cational **SuS** **Ma**nagement — Klassen-, SuS-, Lernfeld- und
Notenverwaltung für die berufliche Bildung, als Ersatz für eine gewachsene
Excel-Sammlung.

Einzelplatz-Tool für eine Lehrkraft: lokale Flask-App mit SQLite, kein Docker,
keine Cloud, keine externen Netzwerkaufrufe — startet per Doppelklick als
lokaler Webserver im Browser. „SuS" = Schülerinnen und Schüler.

## Start

- **Windows:** `start_windows.bat` doppelklicken
- **macOS:** `start_mac.command` doppelklicken
- **Linux:** `start_linux.sh` doppelklicken (bzw. ausführbar machen)

Jedes Skript legt bei Bedarf eine virtuelle Umgebung (`.venv`) an, installiert
`requirements.txt` und startet `start.py` (Flask-Dev-Server, öffnet automatisch
`http://127.0.0.1:5000/`). Manuell mit aktivierter venv: `python start.py`.

Unter Windows läuft der Server danach ohne sichtbares Konsolenfenster/
Taskleisten-Eintrag (`pythonw.exe`); Meldungen stehen in `instance/start.log`.
Beenden über den Link **„VoSuSMa beenden"** auf der Startseite (kein Strg+C
ohne Konsole möglich). Für eine Desktop-Verknüpfung, die auch das kurze
Setup-Fenster beim allerersten Start unterdrückt: `start_windows.vbs`
verknüpfen statt `start_windows.bat`.

## Erste Schritte

1. **Admin → Bildungsgang anlegen** und dort den **Lernfeld-Katalog** pflegen
   (Nr., Name, Gewichtung mündlich/schriftlich/Abgabe, muss 100 % ergeben).
2. Optional **Admin → Betriebe** anlegen (für die SuS-Zuordnung).
3. **Klasse anlegen**: Bildungsgang wählen und die unterrichteten Lernfelder
   ankreuzen – sie werden als Kopie übernommen (spätere Katalog-Änderungen
   wirken nicht rückwirkend).
4. **SuS** je Klasse per CSV-Import (Untis „LessonStudentList") oder einzeln.
5. **Noten** je Lernfeld über die Klassen-Notenübersicht (Bulk-Dialog oder
   CSV-Import: Note oder Punkte für die ganze Klasse; Moodle-Testexport mit
   „Bewertung/100“ direkt lesbar, fehlende/„-“ werden rot zum Nachschreiben).
6. **Zeugnisnote** in der letzten Spalte der Notenübersicht direkt eintragen
   (neben „Gesamt berechnet“, wird nie automatisch übernommen).

## Konfiguration

Über Umgebungsvariablen oder eine optionale Datei **`.env`** im Projektordner
(`KEY=VALUE` je Zeile, `#` = Kommentar). Echte Umgebungsvariablen haben Vorrang.
Die `.env` ist gitignored und liegt **pro Ordner**. Ohne `.env` läuft alles mit
den Defaults (dev, kein Backup).

| Variable | Zweck |
| --- | --- |
| `APP_ENV` | `dev` (Default) → `instance/dev.sqlite3`; `prod` → `instance/prod.sqlite3` |
| `VOSUSMA_BACKUP_DIR` | Zielordner für DB-Snapshots; leer = Backup aus |
| `VOSUSMA_BACKUP_BEHALTEN` | Anzahl aufbewahrter Snapshots (Default 30) |
| `SECRET_KEY` | optional; sonst einmalig erzeugt in `instance/secret_key` |

## Zwei Ordner (Entwicklung → Produktiv)

Entwicklungs- und Produktiv-Ordner sind zwei getrennte Klone desselben Repos
(Remote: `https://github.com/sveroja/VoSuSMa.git`), die sich per `git pull`
aktualisieren. `instance/` (die Daten), `.venv/` und `.env` sind gitignored und
bleiben je Ordner unabhängig. Im Prod-Ordner liegt eine `.env` mit `APP_ENV=prod`
und dem Backup-Pfad; dort wird **nur** `git pull` gemacht (nie `commit`/`push`,
nie `seed.py`). Entwickelt wird ausschließlich im Dev-Ordner.

## Fake-Daten für die Entwicklung

```
python seed.py
```

Erzeugt Bildungsgänge, Betriebe, Klassen, SuS, Lernfelder und Beispiel-Noten mit
Faker (`de_DE`) in `instance/dev.sqlite3`. Bricht ab, wenn `APP_ENV` nicht `dev`
ist.

## Backup

Konsistenter Snapshot (`VACUUM INTO`) in `VOSUSMA_BACKUP_DIR` – am besten ein
Ordner, den OneDrive/Nextcloud mitsynct. Beim Start automatisch, wenn der letzte
Snapshot älter als ~20 h ist; zusätzlich „Jetzt sichern" unter **Backup**. Die
letzten `VOSUSMA_BACKUP_BEHALTEN` Snapshots bleiben liegen. Wiederherstellen:
App stoppen, Snapshot nach `instance/<env>.sqlite3` kopieren, App starten.

`app/sync.py` ist Platzhalter für eine spätere echte WebDAV-Sync (mit Lock).

## Schema-Migrationen

Ohne Alembic über `app/migrations.py`: geordnete Liste `MIGRATIONS`, Version in
SQLites `PRAGMA user_version`. Beim Start (vor `db.create_all()`) werden offene
Migrationen nach automatischer Sicherung der Reihe nach ausgeführt; eine neuere
DB als der Code bricht mit Hinweis auf `git pull` ab. Für die Nutzerin heißt das
nur: `git pull` + neu starten.

Neue Migration = Funktion ans Ende von `MIGRATIONS` hängen (nie umsortieren/
löschen – der Index ist die Version). Komplett neue Tabellen brauchen keine
Migration, die legt `db.create_all()` an.

## Datenschutz

`instance/` (inkl. `prod.sqlite3` mit echten Personendaten) ist per `.gitignore`
ausgeschlossen und darf nie ins Repo. Lokale Import-Dateien (Untis-Exporte) sind
ebenfalls ignoriert. Die App macht keine externen Netzwerkaufrufe. Details siehe
`CLAUDE.md`.

## Status

Läuft im Eigengebrauch, aber noch in aktiver Entwicklung – kein stabiles
Release. Nutzung auf eigenes Risiko.
