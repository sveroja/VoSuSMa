@echo off
setlocal EnableDelayedExpansion

rem pushd statt "cd /d": cmd.exe kann UNC-Pfade (\\server\freigabe\...) nicht
rem als aktuelles Verzeichnis setzen - pushd mappt dafuer automatisch einen
rem temporaeren Laufwerksbuchstaben.
pushd "%~dp0" || (
    echo Konnte nicht in das Skriptverzeichnis wechseln: %~dp0
    pause
    exit /b 1
)

rem Konfiguration (Umgebung, Backup-Ordner) laeuft ueber eine optionale Datei
rem .env in diesem Ordner - siehe README, Abschnitt "Konfiguration". Diese .bat
rem selbst muss dafuer nicht angefasst werden.

rem Wichtig: !errorlevel! (delayed expansion) statt %errorlevel% verwenden -
rem in verschachtelten if/else-Bloecken wird %errorlevel% beim Einlesen des
rem Blocks einmalig ersetzt, nicht zur Laufzeit jeder Zeile, und wuerde hier
rem immer den (veralteten) Wert des ersten "where"-Aufrufs liefern.
set "PY_LAUNCHER="

where py >nul 2>nul
if !errorlevel! == 0 set "PY_LAUNCHER=py -3"

if not defined PY_LAUNCHER (
    where python >nul 2>nul
    if !errorlevel! == 0 set "PY_LAUNCHER=python"
)

if not defined PY_LAUNCHER (
    echo Python 3 wurde nicht gefunden. Bitte installieren und sicherstellen,
    echo dass "python" oder der py-Launcher im PATH verfuegbar ist.
    popd
    pause
    exit /b 1
)

rem pip install nur beim allerersten Setup (wenn .venv fehlt) - nicht bei
rem jedem Doppelklick, damit der Start nicht von jeder Netzwerk-Laune
rem (Proxy, PyPI-Erreichbarkeit) abhaengt.
if not exist ".venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung ...
    %PY_LAUNCHER% -m venv .venv
    call ".venv\Scripts\activate.bat"
    echo Installiere Abhaengigkeiten ... Das kann beim ersten Mal 1-2 Minuten dauern,
    echo je nach Internetverbindung. Bitte warten, das Fenster haengt nicht.
    python -m pip install -q --disable-pip-version-check --timeout 20 -r requirements.txt
    if not !errorlevel! == 0 (
        echo Installation fehlgeschlagen - bitte Internetverbindung pruefen und erneut versuchen.
        popd
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

echo Starte Server ...
echo Falls sich hier laenger als ca. 30 Sekunden nichts tut: VoSuSMa liegt
echo vermutlich auf einem Netzlaufwerk (\\...), und Windows braucht nach einem
echo vorherigen unsauberen Beenden manchmal etwas, um die Dateisperren dafuer
echo freizugeben. Kurz warten reicht meist - im Zweifel Fenster schliessen und
echo nochmal per Doppelklick starten.
python start.py

popd
pause
