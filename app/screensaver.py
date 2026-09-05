"""
Bildschirm wach halten (Bildschirmschoner/Sperre unterdruecken) waehrend die
App laeuft - fuer den Dashboard-Schalter. Nur Windows (ctypes-Aufruf gegen
kernel32); auf anderen Plattformen ist der Schalter ein No-op. Gilt nur
prozesslokal, kein persistenter Systemeingriff - nach Prozessende (App zu)
ist der normale Bildschirmschoner sofort wieder aktiv.
"""
import sys
import threading
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_wach = False
_lock = threading.Lock()
_thread: threading.Thread | None = None


def unterstuetzt() -> bool:
    return sys.platform == "win32"


def ist_aktiv() -> bool:
    return _wach


def _wach_halten_schleife():
    import ctypes

    while True:
        with _lock:
            if not _wach:
                return
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        time.sleep(30)


def setzen(an: bool) -> bool:
    """An/aus schalten. Gibt zurueck, ob der Schalter ueberhaupt wirkt
    (False auf nicht-Windows-Systemen)."""
    global _wach, _thread
    if not unterstuetzt():
        return False

    with _lock:
        _wach = an
    if an:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_wach_halten_schleife, daemon=True)
            _thread.start()
    else:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    return True
