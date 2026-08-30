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
`requirements.txt` und startet `start.py`, was den Flask-Dev-Server hochfährt
und automatisch `http://127.0.0.1:5000/` im Browser öffnet.

Manuell (z.B. für Entwicklung mit bereits aktivierter venv):

```
pip install -r requirements.txt
python start.py
```

## Erste Schritte

1. **Admin → Bildungsgang anlegen** (Berufsbezeichnung) und dort den
   **Lernfeld-Katalog** pflegen (Nr., Name, Gewichtung mündlich/schriftlich/Abgabe,
   muss 100 % ergeben).
2. **Klasse anlegen**: Bildungsgang wählen und die tatsächlich unterrichteten
   Lernfelder ankreuzen – sie werden als Kopie in die Klasse übernommen. Spätere
   Katalog-Änderungen wirken nicht rückwirkend.
3. **SuS** je Klasse per CSV-Import (Untis „LessonStudentList") oder einzeln.
4. **Noten** je Lernfeld über die Klassen-Notenübersicht (Bulk-Dialog: Note oder
   Punkte für die ganze Klasse).

## Dev/Prod-Trennung

Gesteuert über `APP_ENV`:

- `APP_ENV=dev` (Default) → `instance/dev.sqlite3`, ausschliesslich
  Faker-generierte Fake-Daten.
- `APP_ENV=prod` → `instance/prod.sqlite3`, echte Schülerdaten.

Das Git-Repo enthält **niemals** echte Schülerdaten — `instance/` ist in
`.gitignore` ausgeschlossen. Der Entwicklungs- und der Produktiv-Ordner sind
zwei getrennte Klone desselben Repos (siehe unten), die sich über `git pull`
aktualisieren; `instance/` und `.venv/` bleiben je Ordner unabhängig.

## Konfiguration

Konfiguration läuft über Umgebungsvariablen oder eine optionale Datei **`.env`**
im Projektordner (`KEY=VALUE` je Zeile, `#` = Kommentar). Die `.env` ist
gitignored und liegt **pro Ordner** — so hat der Prod-Ordner sein eigenes
`APP_ENV=prod` und seinen eigenen Backup-Pfad. Ohne `.env` läuft alles mit den
Defaults (dev, kein Backup).

| Variable | Zweck |
| --- | --- |
| `APP_ENV` | `dev` (Default) oder `prod` |
| `VOSUSMA_BACKUP_DIR` | Zielordner für DB-Snapshots; leer = Backup aus |
| `VOSUSMA_BACKUP_BEHALTEN` | Anzahl aufbewahrter Snapshots (Default 30) |
| `SECRET_KEY` | optional; sonst einmalig erzeugt in `instance/secret_key` |

Beispiel `.env` im **Prod-Ordner**:

```
APP_ENV=prod
VOSUSMA_BACKUP_DIR=C:\Users\DEINNAME\OneDrive\VoSuSMa-Backups
```

Im Dev-Ordner braucht es meist keine `.env`.

## Fake-Daten für die Entwicklung

```
python seed.py
```

Erzeugt Bildungsgänge, Klassen, SuS, Lernfelder und Beispiel-Noten mit Faker
(Locale `de_DE`) in `instance/dev.sqlite3`. Bricht ab, wenn `APP_ENV` nicht
`dev` ist — im Prod-Ordner läuft es also gar nicht erst.

## Zwei Ordner per Git (Dev → Prod)

Einmalig einrichten:

Remote: `https://github.com/sveroja/VoSuSMa.git`. Beide Ordner sind Klone davon.

```
# Prod-Ordner als Klon von GitHub anlegen (Pfad frei wählbar)
git clone https://github.com/sveroja/VoSuSMa.git C:\Notentool\Prod

# im Prod-Ordner die .env anlegen (einmalig, wird nicht versioniert)
cd C:\Notentool\Prod
echo APP_ENV=prod> .env
```

Danach starten beide Ordner per Doppelklick auf `start_windows.bat` ihre eigene
Datenbank (`instance/dev.sqlite3` bzw. `instance/prod.sqlite3`).

Änderungen übernehmen:

```
# im Dev-Ordner: entwickeln, testen, dann festschreiben und hochladen
git add -A
git commit -m "Was geändert wurde"
git push

# im Prod-Ordner: neuen Stand holen (App vorher schliessen)
cd C:\Notentool\Prod
git pull
```

`git pull` fasst nur versionierte Dateien an. `instance/` (deine echten Daten),
`.venv/` und `.env` sind gitignored und bleiben beim Pull unangetastet. Nach
einem Pull mit geänderten Abhängigkeiten `start_windows.bat` einmal neu starten
(installiert `requirements.txt` allerdings nur, wenn `.venv` fehlt — bei neuen
Paketen `.venv` im Prod-Ordner löschen und neu starten).

**Wichtig:** Im Prod-Ordner nie `git commit`/`git push` und nie `seed.py` —
dort wird nur `git pull` gemacht. Entwickelt wird ausschliesslich im Dev-Ordner.

## Backup

VoSuSMa sichert die Datenbank als konsistenten Snapshot (`VACUUM INTO`) in
einen frei wählbaren Ordner – am besten einen, den OneDrive/Nextcloud mitsynct.

- Ordner setzen über `VOSUSMA_BACKUP_DIR` (z.B. in den Start-Skripten).
- Beim Start wird automatisch gesichert, wenn der letzte Snapshot älter als
  ~20 h ist; zusätzlich gibt es unter **Backup** einen „Jetzt sichern"-Knopf.
- Die letzten `VOSUSMA_BACKUP_BEHALTEN` Snapshots (Default 30) bleiben liegen.
- Wiederherstellen: App stoppen, Snapshot nach `instance/<env>.sqlite3` kopieren,
  App starten.

`app/sync.py` bleibt Platzhalter für eine spätere echte WebDAV-Zwei-Wege-Sync
zu einer eigenen Nextcloud-Instanz (mit Lock gegen paralleles Offline-Arbeiten).

## Schema-Migrationen

Läuft ohne Alembic über `app/migrations.py`: eine geordnete Liste `MIGRATIONS`,
die Version steckt in SQLites `PRAGMA user_version`. Beim Start (vor
`db.create_all()`):

- **frische DB** → wird direkt auf die aktuelle Version gestempelt
- **bestehende DB mit älterer Version** → erst automatische Sicherung, dann die
  offenen Migrationen der Reihe nach (jede in eigener Transaktion). Schlägt eine
  fehl, bricht der Start ab; die DB bleibt auf der letzten erfolgreichen Stufe,
  die Sicherung liegt im Backup-Ordner bzw. neben der DB.
- **DB neuer als der Code** → Abbruch mit Hinweis auf `git pull`

Für die Nutzerin heißt das weiterhin nur: `git pull` + neu starten.

Eine neue Migration schreiben = Funktion ans Ende von `MIGRATIONS` hängen
(nie umsortieren/löschen – der Index ist die Version):

```python
# neue Spalte: eine Zeile
MIGRATIONS.append(lambda c: c.exec_driver_sql(
    "ALTER TABLE schueler ADD COLUMN telefon VARCHAR(50)"))
```

Komplett neue Tabellen brauchen keine Migration – die legt `db.create_all()` an.
Größere Umbauten (Constraints, Primärschlüssel) als eigene Funktion mit
Tabellen-Neuaufbau (create/copy/drop/rename).

## Datenschutz

`instance/` (inkl. `prod.sqlite3` mit echten Personendaten) ist per `.gitignore`
ausgeschlossen und darf nie ins Repo. Lokale Import-Dateien (z.B. Untis-Exporte
`LessonStudentList*.csv`) sind ebenfalls ignoriert. Die App macht keine externen
Netzwerkaufrufe. Details siehe `CLAUDE.md`.

## Status

Läuft im Eigengebrauch, aber noch in aktiver Entwicklung – kein stabiles Release,
keine Migrationslogik (Schemaänderungen = DB neu aufsetzen). Nutzung auf eigenes
Risiko.
