"""
Grunddaten, die unabhaengig von dev/prod und unabhaengig von Fake-Daten in
jeder Umgebung existieren muessen (im Gegensatz zu seed.py, das nur
Beispieldaten fuer dev erzeugt). Wird sowohl beim App-Start (siehe
app/__init__.py) als auch von seed.py verwendet, damit beide dieselben
Notenkategorien anlegen.
"""

STANDARD_NOTENKATEGORIEN = [
    ("muendlich_sonstige", "Mündlich / Sonstige", 0.4),
    ("klassenarbeit", "Klassenarbeit", 0.6),
    ("abgabe", "Abgabe", 0.0),
]
