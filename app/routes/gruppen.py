"""
CRUD fuer Gruppen (frei benennbare Untergruppen einer Klasse, z.B. Kohorte
A/B oder Projektteams) + Pflege der Mitgliedschaft. Die eigentliche Nutzung
(gruppenuebergreifende Klassendienst-Paarung) sitzt in dienst_service.py.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.dienst_service import aktive_schueler
from app.extensions import db
from app.models import Gruppe, Klasse

bp = Blueprint("gruppen", __name__, url_prefix="/klassen/<int:klasse_id>/gruppen")


@bp.route("/")
def liste(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    schueler = aktive_schueler(klasse)
    gruppen_je_schueler = {}
    for gruppe in klasse.gruppen:
        for mitglied in gruppe.mitglieder:
            gruppen_je_schueler.setdefault(mitglied.id, set()).add(gruppe.id)
    return render_template(
        "gruppen/liste.html",
        klasse=klasse,
        schueler=schueler,
        gruppen=klasse.gruppen,
        gruppen_je_schueler=gruppen_je_schueler,
    )


@bp.route("/neu", methods=["POST"])
def neu(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    name = request.form.get("name", "").strip()

    if not name:
        flash("Name darf nicht leer sein.", "error")
    elif len(name) > 80:
        flash("Name darf maximal 80 Zeichen lang sein.", "error")
    else:
        db.session.add(Gruppe(klasse_id=klasse.id, name=name))
        try:
            db.session.commit()
            flash(f"Gruppe '{name}' wurde angelegt.", "success")
        except IntegrityError:
            db.session.rollback()
            flash(f"Gruppe '{name}' gibt es in dieser Klasse schon.", "error")

    return redirect(url_for("gruppen.liste", klasse_id=klasse.id))


@bp.route("/<int:gruppe_id>/loeschen", methods=["POST"])
def loeschen(klasse_id, gruppe_id):
    gruppe = Gruppe.query.get_or_404(gruppe_id)
    if gruppe.klasse_id != klasse_id:
        abort(404)

    name = gruppe.name
    db.session.delete(gruppe)
    db.session.commit()
    flash(f"Gruppe '{name}' wurde gelöscht.", "success")
    return redirect(url_for("gruppen.liste", klasse_id=klasse_id))


@bp.route("/mitglieder", methods=["POST"])
def mitglieder_speichern(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    schueler = aktive_schueler(klasse)
    erlaubte_ids = {s.id for s in schueler}

    geaendert = 0
    for gruppe in klasse.gruppen:
        aktuell = {m.id for m in gruppe.mitglieder}
        gewuenscht = {
            int(roh) for roh in request.form.getlist(f"gruppe_{gruppe.id}")
            if roh.isdigit() and int(roh) in erlaubte_ids
        }
        if aktuell != gewuenscht:
            gruppe.mitglieder = [s for s in schueler if s.id in gewuenscht]
            geaendert += 1

    if geaendert:
        db.session.commit()
        flash("Gruppenzuordnung gespeichert.", "success")
    else:
        flash("Keine Änderungen.", "success")
    return redirect(url_for("gruppen.liste", klasse_id=klasse.id))
