from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import (
    Klasse,
    Lernfeld,
    Notenereintrag,
    Notenkategorie,
    NotenkategorieGewichtung,
    Schueler,
    SchuelerKlasse,
)
from app.gewichtung import gewichte_aus_formular
from app.noten_logik import gesamtnote, kategorie_durchschnitt, parse_note
from app.stammdaten import STANDARD_NOTENKATEGORIEN

bp = Blueprint("lernfelder", __name__, url_prefix="/klassen/<int:klasse_id>/lernfelder")

_DEFAULT_GEWICHT_JE_SCHLUESSEL = {
    schluessel: gewicht for schluessel, _bezeichnung, gewicht in STANDARD_NOTENKATEGORIEN
}

# Kategorie, die in der Klassenuebersicht als ein Durchschnitts-Wert steht statt
# in Einzelspalten je Arbeit ausgeklappt zu werden (wie mndl. im Excel-"Gesamt").
_KOLLABIERTE_KATEGORIE = "muendlich_sonstige"
# Ab so vielen verschiedenen Bezeichnungen wird auch eine sonst ausklappbare
# Kategorie zusammengefasst, damit die Matrix nicht ausufert.
_MAX_ARBEITEN_SPALTEN = 8


def _lernfeld_der_klasse(klasse_id, lernfeld_id):
    lernfeld = Lernfeld.query.get_or_404(lernfeld_id)
    if lernfeld.klasse_id != klasse_id:
        abort(404)
    return lernfeld


def _aktive_schueler(klasse):
    return (
        Schueler.query.join(SchuelerKlasse)
        .filter(SchuelerKlasse.klasse_id == klasse.id, SchuelerKlasse.bis.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )


@bp.route("/")
def liste(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    lernfelder = sorted(klasse.lernfelder, key=lambda lf: lf.sortkey)
    anzahl_noten = {
        lf.id: Notenereintrag.query.filter_by(lernfeld_id=lf.id).count() for lf in lernfelder
    }
    return render_template(
        "lernfelder/liste.html", klasse=klasse, lernfelder=lernfelder, anzahl_noten=anzahl_noten
    )


def _lernfeld_form_lesen(kategorien, klasse, aktuelles=None):
    """Liest nummer/name/Gewichtungen aus request.form und prueft sie.
    -> (nummer, name, gewichte_prozent, fehler)."""
    name = request.form.get("name", "").strip()
    nummer_roh = request.form.get("nummer", "").strip()
    fehler = []

    if not name:
        fehler.append("Name darf nicht leer sein.")
    elif len(name) > 100:
        fehler.append("Name darf maximal 100 Zeichen lang sein.")
    else:
        andere = Lernfeld.query.filter_by(klasse_id=klasse.id, name=name).first()
        if andere is not None and (aktuelles is None or andere.id != aktuelles.id):
            fehler.append(f"Lernfeld '{name}' existiert in dieser Klasse bereits.")

    nummer = None
    if nummer_roh:
        if nummer_roh.isdigit() and int(nummer_roh) > 0:
            nummer = int(nummer_roh)
        else:
            fehler.append("Lernfeld-Nummer muss eine positive ganze Zahl sein (oder leer bleiben).")

    gewichte_prozent, gewicht_fehler = gewichte_aus_formular(request.form, kategorien)
    fehler.extend(gewicht_fehler)
    return nummer, name, gewichte_prozent, fehler


@bp.route("/neu", methods=["GET", "POST"])
def neu(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    kategorien = Notenkategorie.query.all()

    if request.method != "POST":
        default_gewichte = {
            kategorie.id: round(_DEFAULT_GEWICHT_JE_SCHLUESSEL.get(kategorie.schluessel, 0.0) * 100)
            for kategorie in kategorien
        }
        return render_template(
            "lernfelder/form.html", klasse=klasse, kategorien=kategorien,
            form={"name": "", "nummer": ""}, gewichte=default_gewichte,
            titel="Lernfeld anlegen",
            hinweis="Zusätzliches Lernfeld nur für diese Klasse. Die reguläre "
                    "Ausstattung kommt beim Klasse-Anlegen aus dem Bildungsgang-Katalog.",
        )

    nummer, name, gewichte_prozent, fehler = _lernfeld_form_lesen(kategorien, klasse)
    if fehler:
        for meldung in fehler:
            flash(meldung, "error")
        return render_template(
            "lernfelder/form.html", klasse=klasse, kategorien=kategorien,
            form={"name": name, "nummer": request.form.get("nummer", "")},
            gewichte=gewichte_prozent, titel="Lernfeld anlegen", hinweis=None,
        ), 400

    lernfeld = Lernfeld(nummer=nummer, name=name, klasse_id=klasse.id)
    db.session.add(lernfeld)
    db.session.flush()
    for kategorie in kategorien:
        db.session.add(NotenkategorieGewichtung(
            lernfeld_id=lernfeld.id, kategorie_id=kategorie.id,
            gewicht=gewichte_prozent[kategorie.id] / 100,
        ))
    db.session.commit()

    flash(f"Lernfeld '{lernfeld.label}' wurde angelegt.", "success")
    return redirect(url_for("lernfelder.liste", klasse_id=klasse.id))


@bp.route("/<int:lernfeld_id>/bearbeiten", methods=["GET", "POST"])
def bearbeiten(klasse_id, lernfeld_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    kategorien = Notenkategorie.query.all()

    if request.method != "POST":
        vorhanden = {g.kategorie_id: round(g.gewicht * 100) for g in lernfeld.gewichtungen}
        return render_template(
            "lernfelder/form.html", klasse=klasse, kategorien=kategorien,
            form={"name": lernfeld.name, "nummer": lernfeld.nummer or ""},
            gewichte={k.id: vorhanden.get(k.id, 0) for k in kategorien},
            titel="Lernfeld bearbeiten",
            hinweis="Änderungen gelten nur für diese Klasse, nicht für den Katalog.",
        )

    nummer, name, gewichte_prozent, fehler = _lernfeld_form_lesen(kategorien, klasse, lernfeld)
    if fehler:
        for meldung in fehler:
            flash(meldung, "error")
        return render_template(
            "lernfelder/form.html", klasse=klasse, kategorien=kategorien,
            form={"name": name, "nummer": request.form.get("nummer", "")},
            gewichte=gewichte_prozent, titel="Lernfeld bearbeiten", hinweis=None,
        ), 400

    lernfeld.nummer = nummer
    lernfeld.name = name
    vorhandene = {g.kategorie_id: g for g in lernfeld.gewichtungen}
    for kategorie in kategorien:
        anteil = gewichte_prozent[kategorie.id] / 100
        if kategorie.id in vorhandene:
            vorhandene[kategorie.id].gewicht = anteil
        else:
            db.session.add(NotenkategorieGewichtung(
                lernfeld_id=lernfeld.id, kategorie_id=kategorie.id, gewicht=anteil,
            ))
    db.session.commit()

    flash(f"Lernfeld '{lernfeld.label}' wurde gespeichert.", "success")
    return redirect(url_for("lernfelder.liste", klasse_id=klasse.id))


@bp.route("/<int:lernfeld_id>/loeschen", methods=["POST"])
def loeschen(klasse_id, lernfeld_id):
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    label = lernfeld.label
    db.session.delete(lernfeld)  # Gewichtungen + Noteneinträge hängen per Cascade dran
    db.session.commit()
    flash(f"Lernfeld '{label}' wurde mit allen Noteneinträgen gelöscht.", "success")
    return redirect(url_for("lernfelder.liste", klasse_id=klasse_id))


@bp.route("/<int:lernfeld_id>/uebersicht")
def uebersicht(klasse_id, lernfeld_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    schueler_liste = _aktive_schueler(klasse)

    eintraege = Notenereintrag.query.filter_by(lernfeld_id=lernfeld.id).all()
    eintraege_je_schueler = {}
    for e in eintraege:
        eintraege_je_schueler.setdefault(e.schueler_id, []).append(e)

    # Reihenfolge wie im Excel-"Gesamt": schwerste Kategorie zuerst, Gewicht 0
    # (z.B. Abgabe) am Ende - informativ sichtbar, zählt aber nicht in die Gesamtnote.
    gewichtungen = sorted(
        lernfeld.gewichtungen,
        key=lambda g: (-g.gewicht, g.kategorie.bezeichnung),
    )

    # Spaltenmodell aufbauen
    spalten = []  # {key, titel, typ: 'arbeit'|'schnitt', kategorie_id, gewicht}
    for g in gewichtungen:
        kat = g.kategorie
        kat_eintraege = [e for e in eintraege if e.kategorie_id == kat.id]
        bezeichnungen = sorted({(e.bezeichnung or "").strip() for e in kat_eintraege})
        ausklappen = (
            kat.schluessel != _KOLLABIERTE_KATEGORIE
            and 0 < len(bezeichnungen) <= _MAX_ARBEITEN_SPALTEN
        )
        if ausklappen:
            for bez in bezeichnungen:
                spalten.append({
                    "key": f"{kat.id}:{bez}",
                    "titel": bez or "ohne Bez.",
                    "typ": "arbeit",
                    "kategorie_id": kat.id,
                    "bezeichnung": bez,
                    "gewicht": g.gewicht,
                })
            if len(bezeichnungen) > 1:  # Schnitt-Spalte nur sinnvoll bei mehreren Arbeiten
                spalten.append({
                    "key": f"{kat.id}:_schnitt",
                    "titel": f"{kat.bezeichnung} ⌀",
                    "typ": "schnitt",
                    "kategorie_id": kat.id,
                    "gewicht": g.gewicht,
                })
        else:
            spalten.append({
                "key": f"{kat.id}:_schnitt",
                "titel": kat.bezeichnung,
                "typ": "schnitt",
                "kategorie_id": kat.id,
                "gewicht": g.gewicht,
            })

    zeilen = []
    for schueler in schueler_liste:
        meine = eintraege_je_schueler.get(schueler.id, [])
        je_kategorie = {}
        for e in meine:
            je_kategorie.setdefault(e.kategorie_id, []).append(e)

        zellen = {}
        for sp in spalten:
            if sp["typ"] == "schnitt":
                wert = kategorie_durchschnitt(je_kategorie.get(sp["kategorie_id"], []))
            else:
                passende = [
                    e for e in je_kategorie.get(sp["kategorie_id"], [])
                    if (e.bezeichnung or "").strip() == sp["bezeichnung"]
                ]
                wert = kategorie_durchschnitt(passende)
            zellen[sp["key"]] = wert

        zeilen.append({
            "schueler": schueler,
            "zellen": zellen,
            "gesamt": gesamtnote(lernfeld, je_kategorie),
        })

    kategorien_nach_gewicht = sorted(lernfeld.gewichtungen, key=lambda g: -g.gewicht)
    # Erfassen-Buttons: mndl./sonstige zuerst (haeufigster Fall), dann nach Gewicht.
    bulk_kategorien = [
        g.kategorie
        for g in sorted(
            lernfeld.gewichtungen,
            key=lambda g: (g.kategorie.schluessel != _KOLLABIERTE_KATEGORIE, -g.gewicht),
        )
    ]
    return render_template(
        "lernfelder/uebersicht.html",
        klasse=klasse,
        lernfeld=lernfeld,
        spalten=spalten,
        zeilen=zeilen,
        schueler_liste=schueler_liste,
        bulk_kategorien=bulk_kategorien,
        gewicht_info=[(g.kategorie.bezeichnung, round(g.gewicht * 100)) for g in kategorien_nach_gewicht],
        heute=date.today().isoformat(),
    )


@bp.route("/<int:lernfeld_id>/noten-bulk", methods=["POST"])
def noten_bulk(klasse_id, lernfeld_id):
    """Schnelle Erfassung vieler Einzelnoten direkt aus der Klassenübersicht:
    ein Wert je SuS, gemeinsames Datum/Bezeichnung/Kategorie. Modus 'note' =
    direkte Note, Modus 'punkte' = erreichte Punkte auf gemeinsame Maximalpunkte."""
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    klasse = Klasse.query.get_or_404(klasse_id)
    zurueck = redirect(url_for("lernfelder.uebersicht", klasse_id=klasse_id, lernfeld_id=lernfeld_id))

    erlaubte_kategorie_ids = {g.kategorie_id for g in lernfeld.gewichtungen}
    kategorie = None
    if request.form.get("kategorie_id", "").isdigit():
        kid = int(request.form["kategorie_id"])
        if kid in erlaubte_kategorie_ids:
            kategorie = Notenkategorie.query.get(kid)
    if kategorie is None:
        flash("Bitte eine gültige Kategorie wählen.", "error")
        return zurueck

    modus = request.form.get("modus", "note")
    max_punkte = None
    if modus == "punkte":
        try:
            max_punkte = float(request.form.get("max_punkte", "").strip().replace(",", "."))
        except ValueError:
            max_punkte = 0
        if max_punkte <= 0:
            flash("Bitte eine gültige Maximalpunktzahl (> 0) angeben.", "error")
            return zurueck

    try:
        datum = date.fromisoformat(request.form.get("datum", "").strip())
    except ValueError:
        datum = date.today()
    bezeichnung = request.form.get("bezeichnung", "").strip() or None

    gespeichert = 0
    fehler = []
    for schueler in _aktive_schueler(klasse):
        rohwert = request.form.get(f"wert_{schueler.id}", "").strip().replace(",", ".")
        if not rohwert:
            continue
        eintrag = Notenereintrag(
            schueler_id=schueler.id,
            lernfeld_id=lernfeld.id,
            kategorie_id=kategorie.id,
            datum=datum,
            bezeichnung=bezeichnung,
        )
        if modus == "punkte":
            try:
                punkte = float(rohwert)
                if punkte < 0:
                    raise ValueError
            except ValueError:
                fehler.append(rohwert)
                continue
            eintrag.erreichte_punkte = punkte
            eintrag.max_punkte = max_punkte
        else:
            try:
                eintrag.note_direkt = parse_note(rohwert)
            except ValueError:
                fehler.append(rohwert)
                continue
        db.session.add(eintrag)
        gespeichert += 1

    if gespeichert:
        db.session.commit()
        flash(f"{gespeichert} Eintrag/Einträge gespeichert.", "success")
    if fehler:
        erwartet = "Punkte ≥ 0" if modus == "punkte" else "Note 1,0–6,0"
        flash(f"Nicht gespeichert (ungültig, {erwartet} erwartet): " + ", ".join(fehler), "error")
    if not gespeichert and not fehler:
        flash("Nichts eingetragen.", "error")

    return zurueck
