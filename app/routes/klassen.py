from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.lernfeld_service import lernfelder_aus_vorlagen
from app.models import Bildungsgang, Klasse

bp = Blueprint("klassen", __name__, url_prefix="/klassen")


@bp.route("/")
def liste():
    klassen = Klasse.query.order_by(Klasse.bezeichnung).all()
    return render_template("klassen/liste.html", klassen=klassen)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    bildungsgaenge = (
        Bildungsgang.query.filter_by(aktiv=True).order_by(Bildungsgang.bezeichnung).all()
    )

    if request.method != "POST":
        return render_template(
            "klassen/neu.html", bildungsgaenge=bildungsgaenge, bezeichnung="", bildungsgang_id=None
        )

    bezeichnung = request.form.get("bezeichnung", "").strip()
    bildungsgang_id = request.form.get("bildungsgang_id", "").strip()
    vorlage_ids = {v for v in request.form.getlist("vorlage") if v.isdigit()}

    fehler = []
    if not bezeichnung:
        fehler.append("Bezeichnung darf nicht leer sein.")
    elif len(bezeichnung) > 50:
        fehler.append("Bezeichnung darf maximal 50 Zeichen lang sein.")
    elif Klasse.query.filter_by(bezeichnung=bezeichnung).first():
        fehler.append(f"Klasse '{bezeichnung}' existiert bereits.")

    bildungsgang = None
    if not bildungsgang_id.isdigit():
        fehler.append("Bitte einen Bildungsgang wählen.")
    else:
        bildungsgang = Bildungsgang.query.get(int(bildungsgang_id))
        if bildungsgang is None:
            fehler.append("Ungültiger Bildungsgang.")

    if fehler:
        for m in fehler:
            flash(m, "error")
        return render_template(
            "klassen/neu.html",
            bildungsgaenge=bildungsgaenge,
            bezeichnung=bezeichnung,
            bildungsgang_id=int(bildungsgang_id) if bildungsgang_id.isdigit() else None,
            gewaehlte_vorlagen=vorlage_ids,
        ), 400

    klasse = Klasse(bezeichnung=bezeichnung, bildungsgang_id=bildungsgang.id)
    db.session.add(klasse)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        flash(f"Klasse '{bezeichnung}' existiert bereits.", "error")
        return render_template(
            "klassen/neu.html", bildungsgaenge=bildungsgaenge, bezeichnung=bezeichnung,
            bildungsgang_id=bildungsgang.id,
        ), 400

    vorlagen = [
        v for v in bildungsgang.lernfeldvorlagen if str(v.id) in vorlage_ids
    ]
    anzahl = len(lernfelder_aus_vorlagen(klasse, vorlagen))
    db.session.commit()

    flash(
        f"Klasse '{bezeichnung}' angelegt" + (f" mit {anzahl} Lernfeld(ern)." if anzahl else "."),
        "success",
    )
    return redirect(url_for("klassen.liste"))
