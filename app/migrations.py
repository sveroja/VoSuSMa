"""
Schlanke Schema-Migrationen ohne Alembic.

Ablauf beim Start (in create_app, VOR db.create_all): schema_aktualisieren(app)
- frische DB (keine Tabellen)  -> user_version direkt auf Head stempeln
- bestehende DB, Version < Head -> erst Sicherheitskopie, dann die offenen
  Migrationen der Reihe nach, jede in eigener Transaktion; schlaegt eine fehl,
  wird zurueckgerollt und der Start abgebrochen (Snapshot bleibt).
- danach legt db.create_all() zusaetzlich alle komplett neuen Tabellen an, fuer
  die es also gar keine Migration braucht.

Neue Migration: Funktion schreiben, ans Ende von MIGRATIONS anhaengen. Nie
umsortieren oder entfernen - der Listenindex IST die Version. Jede Migration
bekommt eine SQLAlchemy-Connection und nutzt conn.exec_driver_sql("...").
Modernes SQLite (>= 3.35) kann ADD/DROP/RENAME COLUMN; groessere Umbauten
(Constraints, PK) brauchen den Tabellen-Neuaufbau (create/copy/drop/rename).
"""
import shutil
from datetime import datetime
from pathlib import Path

from app.extensions import db


# ---------------------------------------------------------------------------
#  Migrationen (chronologisch)
# ---------------------------------------------------------------------------
# Beispiel:
# def _m_0001_schueler_telefon(conn):
#     conn.exec_driver_sql("ALTER TABLE schueler ADD COLUMN telefon VARCHAR(50)")

def _m_0001_schueler_betrieb_id(conn):
    # Neue Tabelle "betriebe" legt db.create_all() an - hier nur die FK-Spalte an
    # der bestehenden schueler-Tabelle. SQLite erzwingt FKs ohnehin nicht.
    conn.exec_driver_sql("ALTER TABLE schueler ADD COLUMN betrieb_id INTEGER")


MIGRATIONS = [
    _m_0001_schueler_betrieb_id,
]


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------
def _anzahl_tabellen(conn) -> int:
    return conn.exec_driver_sql(
        "SELECT count(*) FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).scalar()


def _user_version(conn) -> int:
    return conn.exec_driver_sql("PRAGMA user_version").scalar()


def schema_aktualisieren(app):
    """Vor db.create_all() im App-Context aufrufen."""
    ziel = len(MIGRATIONS)

    with db.engine.connect() as conn:
        frisch = _anzahl_tabellen(conn) == 0
        aktuell = _user_version(conn)
        if frisch:
            conn.exec_driver_sql(f"PRAGMA user_version = {ziel}")
            conn.commit()
            return
        if aktuell > ziel:
            raise RuntimeError(
                f"DB-Schemaversion {aktuell} ist neuer als der Code ({ziel}). "
                "Vermutlich ein aelterer Stand ausgecheckt - bitte 'git pull'."
            )
        if aktuell == ziel:
            return

    app.logger.warning("Schema-Migration: Version %d -> %d", aktuell, ziel)
    _sicherung_vor_migration(app)

    for i in range(aktuell, ziel):
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                MIGRATIONS[i](conn)
                conn.exec_driver_sql(f"PRAGMA user_version = {i + 1}")
                trans.commit()
            except Exception:
                trans.rollback()
                app.logger.error(
                    "Migration %d fehlgeschlagen - Start abgebrochen. "
                    "Die Datenbank ist unveraendert, eine Sicherung liegt vor.",
                    i + 1,
                )
                raise
        app.logger.info("Migration %d/%d ok", i + 1, ziel)


def _sicherung_vor_migration(app):
    """Immer eine Kopie ziehen, bevor an der DB geschraubt wird. Bevorzugt in
    den Backup-Ordner (VACUUM INTO), sonst direkt neben die DB-Datei."""
    cfg = app.config
    if cfg.get("BACKUP_DIR"):
        from app.backup import snapshot_erstellen

        try:
            ziel = snapshot_erstellen(cfg)
            app.logger.info("Sicherung vor Migration: %s", ziel)
            return
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Backup vor der Migration schlug fehl, breche ab: {exc}") from exc

    quelle = Path(cfg["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "", 1))
    if quelle.exists():
        ziel = quelle.with_name(
            f"{quelle.stem}-vor-migration-{datetime.now():%Y%m%d-%H%M%S}{quelle.suffix}"
        )
        shutil.copy2(quelle, ziel)
        app.logger.info("Sicherung vor Migration: %s", ziel)
