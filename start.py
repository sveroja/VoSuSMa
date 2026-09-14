"""
VoSuSMa - gemeinsamer Einstiegspunkt fuer die Doppelklick-Skripte
(start_windows.bat, start_mac.command, start_linux.sh): startet den lokalen
Flask-Server und oeffnet danach automatisch den Browser.

Laeuft unter Windows ueber pythonw.exe OHNE sichtbares Konsolenfenster (siehe
start_windows.bat) - kein Strg+C moeglich, daher gibt es die In-App-Aktion
"VoSuSMa beenden" (POST /beenden, siehe routes/main.py). Alle Meldungen gehen
nach instance/start.log statt auf die Konsole; ein fataler Startfehler zeigt
zusaetzlich eine MessageBoxW, sonst merkt der Nutzer ohne Konsole nichts davon.

Welche Datenbank (dev/prod) benutzt wird, steuert APP_ENV (Umgebungsvariable oder
.env im Projektordner, siehe app/config.py); Default ist "dev".
"""
import os
import sys

# pythonw.exe hat keine Konsole - sys.stdout/-stderr sind dann None. Ohne diesen
# Guard stuerzen interne print()/Log-Aufrufe (auch aus Flask/Werkzeug, z.B. der
# Request-Logger) sofort mit AttributeError ab, weil sie ".write(...)" auf None
# aufrufen.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import logging  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402
import webbrowser  # noqa: E402
from pathlib import Path  # noqa: E402

HOST = "127.0.0.1"
PORT = 5000

_INSTANCE_DIR = Path(__file__).resolve().parent / "instance"
_INSTANCE_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=_INSTANCE_DIR / "start.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("start")


def _fehler_meldung(text: str):
    """Fataler Fehler ohne Konsole - MessageBoxW, sonst merkt der Nutzer ohne
    Konsole gar nichts vom gescheiterten Start."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "VoSuSMa - Fehler beim Start", 0x10)


def _laeuft_schon() -> bool:
    """Schutz gegen Doppel-Doppelklick: laeuft auf HOST:PORT schon eine
    Instanz, wird nur der Browser geoeffnet statt ein zweiter Server zu starten
    (der ohnehin am belegten Port scheitern wuerde)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((HOST, PORT)) == 0


def _oeffne_browser():
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    if _laeuft_schon():
        log.info("Port %d ist schon belegt - oeffne nur den Browser.", PORT)
        _oeffne_browser()
        sys.exit(0)

    try:
        log.info("Initialisiere VoSuSMa ...")
        from app import create_app

        app = create_app()
        log.info(
            "VoSuSMa laeuft (Umgebung: %s) auf http://%s:%d/",
            app.config["ENV_NAME"], HOST, PORT,
        )
        threading.Timer(1.0, _oeffne_browser).start()
        # use_reloader=False: der Reloader wuerde den Prozess doppelt starten und
        # damit auch den Browser doppelt oeffnen.
        app.run(host=HOST, port=PORT, debug=app.config["DEBUG"], use_reloader=False)
    except Exception:
        log.exception("Fataler Fehler beim Start")
        _fehler_meldung(
            "VoSuSMa konnte nicht gestartet werden.\n\nDetails in instance/start.log."
        )
        sys.exit(1)
