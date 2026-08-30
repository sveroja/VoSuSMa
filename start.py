"""
VoSuSMa - gemeinsamer Einstiegspunkt fuer die Doppelklick-Skripte
(start_windows.bat, start_mac.command, start_linux.sh): startet den lokalen
Flask-Server und oeffnet danach automatisch den Browser.

Welche Datenbank (dev/prod) benutzt wird, steuert APP_ENV (Umgebungsvariable oder
.env im Projektordner, siehe app/config.py); Default ist "dev".
"""
import threading
import webbrowser

# Sofort eine Meldung ausgeben, bevor der (potenziell langsame) Import von
# app/__init__.py laeuft - sonst wirkt das Fenster eingefroren.
print("Initialisiere VoSuSMa ...", flush=True)

from app import create_app  # noqa: E402

HOST = "127.0.0.1"
PORT = 5000


def _oeffne_browser():
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    app = create_app()
    print(
        f"VoSuSMa laeuft (Umgebung: {app.config['ENV_NAME']}) auf http://{HOST}:{PORT}/",
        flush=True,
    )
    threading.Timer(1.0, _oeffne_browser).start()
    # use_reloader=False: der Reloader wuerde den Prozess doppelt starten und
    # damit auch den Browser doppelt oeffnen.
    app.run(host=HOST, port=PORT, debug=app.config["DEBUG"], use_reloader=False)
