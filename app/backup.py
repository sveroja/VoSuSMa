"""
Einfache DB-Sicherung: konsistente Snapshots der SQLite-Datei per VACUUM INTO
in einen konfigurierbaren Ordner (idealerweise ein von OneDrive/Nextcloud
mitgesyncter Ordner). Kein Netzwerkzugriff, keine zusaetzliche Abhaengigkeit.

Wiederherstellen ist bewusst manuell: App stoppen, gewuenschten Snapshot aus dem
Backup-Ordner nach instance/<env>.sqlite3 kopieren, App starten.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def _db_pfad(config) -> Path:
    uri = config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        raise RuntimeError("Backup unterstützt nur SQLite-Datenbanken.")
    return Path(uri.replace("sqlite:///", "", 1))


def backup_dir(config) -> Path | None:
    wert = config.get("BACKUP_DIR")
    return Path(wert) if wert else None


def _praefix(config) -> str:
    return f"vosusma-{config.get('ENV_NAME', 'db')}-"


def snapshots(config) -> list[dict]:
    """Vorhandene Snapshots der aktuellen Umgebung, neuester zuerst."""
    ordner = backup_dir(config)
    if not ordner or not ordner.is_dir():
        return []
    dateien = sorted(
        ordner.glob(f"{_praefix(config)}*.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "name": p.name,
            "pfad": p,
            "groesse_kb": round(p.stat().st_size / 1024),
            "zeit": datetime.fromtimestamp(p.stat().st_mtime),
        }
        for p in dateien
    ]


def snapshot_erstellen(config) -> Path:
    """Konsistente Kopie der DB per VACUUM INTO. Gibt den Zielpfad zurück."""
    ordner = backup_dir(config)
    if not ordner:
        raise RuntimeError("Kein Backup-Ordner konfiguriert (VOSUSMA_BACKUP_DIR).")
    quelle = _db_pfad(config)
    if not quelle.exists():
        raise RuntimeError(f"Datenbank nicht gefunden: {quelle}")

    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{_praefix(config)}{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    if ziel.exists():
        raise RuntimeError("Es wurde gerade eben schon gesichert – bitte kurz warten.")

    con = sqlite3.connect(str(quelle))
    con.isolation_level = None  # VACUUM darf nicht in einer Transaktion laufen
    try:
        con.execute(f"VACUUM INTO '{str(ziel).replace(chr(39), chr(39) * 2)}'")
    finally:
        con.close()

    _alte_loeschen(config)
    return ziel


def _alte_loeschen(config) -> None:
    behalten = config.get("BACKUP_BEHALTEN", 30)
    for eintrag in snapshots(config)[behalten:]:
        try:
            eintrag["pfad"].unlink()
        except OSError:
            pass


def auto_backup_wenn_faellig(app) -> None:
    """Beim App-Start aufrufen: sichert, wenn kein oder nur ein zu alter Snapshot da ist.
    Fehler werden geschluckt (Backup darf den Start nie blockieren)."""
    config = app.config
    if not backup_dir(config):
        return
    try:
        vorhandene = snapshots(config)
        grenze = timedelta(hours=config.get("BACKUP_AUTO_STUNDEN", 20))
        if vorhandene and datetime.now() - vorhandene[0]["zeit"] < grenze:
            return
        ziel = snapshot_erstellen(config)
        app.logger.info("Auto-Backup erstellt: %s", ziel)
    except Exception as exc:  # noqa: BLE001 - Start nicht wegen Backup abbrechen
        app.logger.warning("Auto-Backup übersprungen: %s", exc)
