#!/bin/bash
cd "$(dirname "$0")"

# pip install nur beim allerersten Setup (wenn .venv fehlt) - nicht bei jedem
# Doppelklick, damit der Start nicht von jeder Netzwerk-Laune (Proxy,
# PyPI-Erreichbarkeit) abhaengt.
if [ ! -f ".venv/bin/python" ]; then
    echo "Erstelle virtuelle Umgebung ..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installiere Abhaengigkeiten ... Das kann beim ersten Mal 1-2 Minuten dauern."
    if ! python -m pip install -q --disable-pip-version-check --timeout 20 -r requirements.txt; then
        echo "Installation fehlgeschlagen - bitte Internetverbindung pruefen und erneut versuchen."
        read -n 1 -s -r -p "Taste druecken zum Beenden..."
        exit 1
    fi
else
    source .venv/bin/activate
fi

echo "Starte Server ..."
echo "Falls sich hier laenger als ca. 30 Sekunden nichts tut: VoSuSMa liegt"
echo "moeglicherweise auf einem Netzlaufwerk, das nach einem vorherigen"
echo "unsauberen Beenden kurz braucht, um Dateisperren freizugeben. Kurz"
echo "warten reicht meist - im Zweifel Terminal schliessen und neu starten."
python start.py
