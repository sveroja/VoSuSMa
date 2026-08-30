import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def _lade_env_datei():
    """Optionale .env im Projektordner einlesen (KEY=VALUE je Zeile, # = Kommentar).
    Kein python-dotenv noetig. Echte Umgebungsvariablen haben Vorrang. Die Datei
    liegt pro Ordner und ist nicht im Repo (.gitignore) - so bekommt der
    Prod-Ordner sein eigenes APP_ENV / VOSUSMA_BACKUP_DIR."""
    pfad = BASE_DIR / ".env"
    if not pfad.exists():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        schluessel, _, wert = zeile.partition("=")
        os.environ.setdefault(schluessel.strip(), wert.strip().strip('"').strip("'"))


_lade_env_datei()


def _secret_key() -> str:
    """SECRET_KEY ohne .env: erst Umgebungsvariable, sonst ein einmalig erzeugter
    Zufallswert in instance/secret_key (nicht im Repo, da instance/ gitignored)."""
    aus_env = os.environ.get("SECRET_KEY", "").strip()
    if aus_env:
        return aus_env
    pfad = INSTANCE_DIR / "secret_key"
    if pfad.exists():
        return pfad.read_text(encoding="ascii").strip()
    key = secrets.token_hex(32)
    pfad.write_text(key, encoding="ascii")
    return key


class BaseConfig:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Zielordner fuer DB-Snapshots (idealerweise ein Ordner, den OneDrive/Nextcloud
    # mitsynct). Leer -> Backup-Funktion zeigt nur einen Hinweis, sichert nicht.
    BACKUP_DIR = os.environ.get("VOSUSMA_BACKUP_DIR", "").strip() or None
    # So viele Snapshots je Umgebung aufheben, aeltere werden beim Sichern geloescht.
    BACKUP_BEHALTEN = int(os.environ.get("VOSUSMA_BACKUP_BEHALTEN", "30"))
    # Beim Start automatisch sichern, wenn der juengste Snapshot aelter ist als:
    BACKUP_AUTO_STUNDEN = 20


class DevConfig(BaseConfig):
    """Läuft gegen dev.sqlite3 - wird ausschliesslich mit Faker-Fake-Daten befüllt."""
    ENV_NAME = "dev"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_DIR / 'dev.sqlite3'}"
    DEBUG = True


class ProdConfig(BaseConfig):
    """Läuft gegen prod.sqlite3 - echte Schülerdaten, nur lokal, Sync via WebDAV (später)."""
    ENV_NAME = "prod"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_DIR / 'prod.sqlite3'}"
    DEBUG = False


def aktuelles_env() -> str:
    """dev oder prod - aus APP_ENV (Umgebungsvariable oder .env). Default: dev
    (safety first). Der normalisierte Wert wird nach os.environ zurueckgeschrieben,
    damit start.py und seed.py dasselbe sehen."""
    env = "prod" if os.environ.get("APP_ENV", "").strip().lower() == "prod" else "dev"
    os.environ["APP_ENV"] = env
    return env


def get_config():
    return ProdConfig if aktuelles_env() == "prod" else DevConfig
