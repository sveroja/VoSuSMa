from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.lernfeld_service import lernfelder_aus_vorlagen
from app.models import Bildungsgang, Klasse, Lernfeld, Notenereintrag

bp = Blueprint("klassen", __name__, url_prefix="/klassen")


@bp.route("/")
def liste():
    alle = Klasse.query.order_by(Klasse.bezeichnung).all()
    gewaehlte_id = request.args.get("klasse_id", type=int)
    # Archivierte nur auf Wunsch - oder wenn direkt eine archivierte angesteuert wird
    archiv = request.args.get("archiv") == "1" or any(
        k.id == gewaehlte_id and not k.aktiv for k in alle
    )
    klassen = alle if archiv else [k for k in alle if k.aktiv]
    anzahl_archiviert = sum(1 for k in alle if not k.aktiv)

    gewaehlte = None
    if gewaehlte_id:
        gewaehlte = next((k for k in klassen if k.id == gewaehlte_id), None)
    if gewaehlte is None and klassen:
        gewaehlte = klassen[0]

    lernfelder = []
    anzahl_noten = {}
    if gewaehlte is not None:
        lernfelder = sorted(gewaehlte.lernfelder, key=lambda lf: lf.sortkey)
        anzahl_noten = {
            lf.id: Notenereintrag.query.filter_by(lernfeld_id=lf.id).count() for lf in lernfelder
        }

    return render_template(
        "klassen/liste.html", klassen=klassen, gewaehlte=gewaehlte,
        lernfelder=lernfelder, anzahl_noten=anzahl_noten,
        archiv=archiv, anzahl_archiviert=anzahl_archiviert,
    )


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
    return redirect(url_for("klassen.liste", klasse_id=klasse.id))


@bp.route("/<int:klasse_id>/loeschen", methods=["GET", "POST"])
def loeschen(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    anzahl_noten = (
        Notenereintrag.query.join(Lernfeld)
        .filter(Lernfeld.klasse_id == klasse.id)
        .count()
    )

    if request.method != "POST":
        warnung = (
            f"Die Klasse {klasse.bezeichnung} wird mit {len(klasse.lernfelder)} "
            f"Lernfeld(ern), {anzahl_noten} Noteneinträgen und allen "
            f"SuS-Zuordnungen gelöscht. Die SuS selbst bleiben erhalten. "
            f"Das lässt sich nicht rückgängig machen."
        )
        return render_template(
            "klassen/loeschen.html", klasse=klasse, warnung=warnung,
        )

    if request.form.get("bestaetigung", "").strip() != klasse.bezeichnung:
        flash("Bestätigung stimmte nicht – nichts gelöscht.", "error")
        return redirect(url_for("admin.klassen_liste"))

    bezeichnung = klasse.bezeichnung
    db.session.delete(klasse)  # Lernfelder (+ Noten/Gewichtungen) und Zuordnungen per Cascade
    db.session.commit()
    flash(f"Klasse '{bezeichnung}' wurde gelöscht.", "success")
    return redirect(url_for("admin.klassen_liste"))
