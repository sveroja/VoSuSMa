"""
Lernfelder einer Klasse aus dem Bildungsgang-Katalog erzeugen. Bewusst eine
Kopie (nicht Referenz): eine Klasse darf danach abweichen, und Katalog-Aenderungen
wirken nicht rueckwirkend auf bestehende Klassen/Noten.
"""
from app.models import Lernfeld, NotenkategorieGewichtung


def lernfelder_aus_vorlagen(klasse, vorlagen) -> list[Lernfeld]:
    """Legt je Vorlage ein Lernfeld in der Klasse an und kopiert die Gewichtungen.
    Ohne commit - der Aufrufer committet. Vorhandene gleichnamige Lernfelder werden
    uebersprungen. Gibt die neu angelegten Lernfelder zurueck."""
    vorhanden = {lf.name for lf in klasse.lernfelder}
    neu = []
    for vorlage in vorlagen:
        if vorlage.name in vorhanden:
            continue
        lernfeld = Lernfeld(nummer=vorlage.nummer, name=vorlage.name)
        for g in vorlage.gewichtungen:
            lernfeld.gewichtungen.append(
                NotenkategorieGewichtung(kategorie_id=g.kategorie_id, gewicht=g.gewicht)
            )
        klasse.lernfelder.append(lernfeld)
        neu.append(lernfeld)
    return neu
