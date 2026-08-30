from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Lernfeld, Notenereintrag, Notenkategorie, Schueler
from app.noten_logik import parse_note

bp = Blueprint("noten", __name__, url_prefix="/noten")


@bp.route("/schueler/<int:schueler_id>/lernfeld/<int:lernfeld_id>/neu", methods=["GET", "POST"])
def neu(schueler_id, lernfeld_id):
    schueler = Schueler.query.get_or_404(schueler_id)
    lernfeld = Lernfeld.query.get_or_404(lernfeld_id)
    kategorien = [gewichtung.kategorie for gewichtung in lernfeld.gewichtungen]

    if request.method != "POST":
        return render_template(
            "noten/neu.html",
            schueler=schueler,
            lernfeld=lernfeld,
            kategorien=kategorien,
            form={"datum": date.today().isoformat(), "eingabeart": "direkt"},
        )

    form = {
        "kategorie_id": request.form.get("kategorie_id", "").strip(),
        "datum": request.form.get("datum", "").strip(),
        "bezeichnung": request.form.get("bezeichnung", "").strip(),
        "eingabeart": request.form.get("eingabeart", "direkt"),
        "note_direkt": request.form.get("note_direkt", "").strip().replace(",", "."),
        "erreichte_punkte": request.form.get("erreichte_punkte", "").strip().replace(",", "."),
        "max_punkte": request.form.get("max_punkte", "").strip().replace(",", "."),
    }

    fehler = []

    kategorie = None
    if form["kategorie_id"].isdigit():
        kategorie = Notenkategorie.query.get(int(form["kategorie_id"]))
    if kategorie is None:
        fehler.append("Bitte eine Kategorie auswählen.")

    try:
        datum = date.fromisoformat(form["datum"]) if form["datum"] else date.today()
    except ValueError:
        fehler.append("Datum ist ungültig.")
        datum = date.today()

    note_direkt = None
    erreichte_punkte = None
    max_punkte = None

    if form["eingabeart"] == "direkt":
        try:
            note_direkt = parse_note(form["note_direkt"])
        except ValueError as exc:
            fehler.append(str(exc) if "zwischen" in str(exc) else "Bitte eine gültige Note eingeben.")
    else:
        try:
            erreichte_punkte = float(form["erreichte_punkte"])
            max_punkte = float(form["max_punkte"])
            if max_punkte <= 0:
                fehler.append("Maximale Punktzahl muss größer als 0 sein.")
            elif erreichte_punkte < 0:
                fehler.append("Erreichte Punkte dürfen nicht negativ sein.")
        except ValueError:
            fehler.append("Bitte gültige Punktzahlen eingeben.")

    if fehler:
        for meldung in fehler:
            flash(meldung, "error")
        return render_template(
            "noten/neu.html", schueler=schueler, lernfeld=lernfeld, kategorien=kategorien, form=form
        ), 400

    eintrag = Notenereintrag(
        schueler_id=schueler.id,
        lernfeld_id=lernfeld.id,
        kategorie_id=kategorie.id,
        datum=datum,
        bezeichnung=form["bezeichnung"] or None,
        note_direkt=note_direkt,
        erreichte_punkte=erreichte_punkte,
        max_punkte=max_punkte,
    )
    db.session.add(eintrag)
    db.session.commit()

    flash("Noteneintrag wurde gespeichert.", "success")
    return redirect(url_for("schueler.detail", schueler_id=schueler.id))


@bp.route("/<int:noteneintrag_id>/loeschen", methods=["POST"])
def loeschen(noteneintrag_id):
    eintrag = Notenereintrag.query.get_or_404(noteneintrag_id)
    schueler_id = eintrag.schueler_id
    db.session.delete(eintrag)
    db.session.commit()
    flash("Noteneintrag wurde gelöscht.", "success")
    return redirect(url_for("schueler.detail", schueler_id=schueler_id))
