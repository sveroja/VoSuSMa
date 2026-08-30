from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.gewichtung import gewichte_aus_formular
from app.models import (
    Bildungsgang,
    Lernfeldvorlage,
    Notenkategorie,
    Notenschema,
    VorlageGewichtung,
)
from app.stammdaten import STANDARD_NOTENKATEGORIEN

bp = Blueprint("admin", __name__, url_prefix="/admin")

_DEFAULT_GEWICHT = {s: g for s, _b, g in STANDARD_NOTENKATEGORIEN}


def _nummer_pruefen(rohwert, fehler):
    if not rohwert:
        return None
    if rohwert.isdigit() and int(rohwert) > 0:
        return int(rohwert)
    fehler.append("Lernfeld-Nummer muss eine positive ganze Zahl sein (oder leer bleiben).")
    return None


# --------------------------------------------------------------------------- #
#  Bildungsgänge
# --------------------------------------------------------------------------- #
@bp.route("/")
def index():
    bildungsgaenge = Bildungsgang.query.order_by(Bildungsgang.bezeichnung).all()
    return render_template("admin/index.html", bildungsgaenge=bildungsgaenge)


@bp.route("/notenschema")
def notenschema():
    schema = Notenschema.query.filter_by(aktiv=True).first()
    stufen = sorted(schema.stufen, key=lambda s: -s.von_prozent) if schema else []
    return render_template("admin/notenschema.html", schema=schema, stufen=stufen)


@bp.route("/bildungsgaenge/neu", methods=["GET", "POST"])
def bildungsgang_neu():
    if request.method != "POST":
        return render_template("admin/bildungsgang_form.html", form={}, titel="Bildungsgang anlegen")

    bezeichnung = request.form.get("bezeichnung", "").strip()
    fehler = []
    if not bezeichnung:
        fehler.append("Bezeichnung darf nicht leer sein.")
    elif len(bezeichnung) > 120:
        fehler.append("Bezeichnung darf maximal 120 Zeichen lang sein.")
    elif Bildungsgang.query.filter_by(bezeichnung=bezeichnung).first():
        fehler.append(f"Bildungsgang '{bezeichnung}' existiert bereits.")

    if fehler:
        for m in fehler:
            flash(m, "error")
        return render_template(
            "admin/bildungsgang_form.html",
            form={"bezeichnung": bezeichnung},
            titel="Bildungsgang anlegen",
        ), 400

    bg = Bildungsgang(bezeichnung=bezeichnung)
    db.session.add(bg)
    db.session.commit()
    flash(f"Bildungsgang '{bezeichnung}' wurde angelegt.", "success")
    return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg.id))


@bp.route("/bildungsgaenge/<int:bildungsgang_id>", methods=["GET"])
def bildungsgang_detail(bildungsgang_id):
    bg = Bildungsgang.query.get_or_404(bildungsgang_id)
    return render_template("admin/bildungsgang_detail.html", bg=bg)


@bp.route("/bildungsgaenge/<int:bildungsgang_id>/bearbeiten", methods=["GET", "POST"])
def bildungsgang_bearbeiten(bildungsgang_id):
    bg = Bildungsgang.query.get_or_404(bildungsgang_id)
    if request.method != "POST":
        return render_template(
            "admin/bildungsgang_form.html",
            form={"bezeichnung": bg.bezeichnung, "aktiv": bg.aktiv},
            titel="Bildungsgang bearbeiten",
        )

    bezeichnung = request.form.get("bezeichnung", "").strip()
    fehler = []
    if not bezeichnung:
        fehler.append("Bezeichnung darf nicht leer sein.")
    else:
        andere = Bildungsgang.query.filter_by(bezeichnung=bezeichnung).first()
        if andere and andere.id != bg.id:
            fehler.append(f"Bildungsgang '{bezeichnung}' existiert bereits.")

    if fehler:
        for m in fehler:
            flash(m, "error")
        return render_template(
            "admin/bildungsgang_form.html",
            form={"bezeichnung": bezeichnung, "aktiv": bg.aktiv},
            titel="Bildungsgang bearbeiten",
        ), 400

    bg.bezeichnung = bezeichnung
    bg.aktiv = request.form.get("aktiv") == "on"
    db.session.commit()
    flash("Bildungsgang gespeichert.", "success")
    return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg.id))


@bp.route("/bildungsgaenge/<int:bildungsgang_id>/loeschen", methods=["POST"])
def bildungsgang_loeschen(bildungsgang_id):
    bg = Bildungsgang.query.get_or_404(bildungsgang_id)
    if bg.klassen:
        flash(
            f"'{bg.bezeichnung}' kann nicht gelöscht werden – {len(bg.klassen)} Klasse(n) "
            "nutzen ihn noch.",
            "error",
        )
        return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg.id))
    db.session.delete(bg)
    db.session.commit()
    flash(f"Bildungsgang '{bg.bezeichnung}' wurde gelöscht.", "success")
    return redirect(url_for("admin.index"))


# --------------------------------------------------------------------------- #
#  Lernfeldvorlagen
# --------------------------------------------------------------------------- #
def _vorlage_formular(bg, vorlage=None):
    kategorien = Notenkategorie.query.all()
    if vorlage is None:
        gewichte = {
            k.id: round(_DEFAULT_GEWICHT.get(k.schluessel, 0.0) * 100) for k in kategorien
        }
        form = {"nummer": "", "name": ""}
    else:
        vorhanden = {g.kategorie_id: round(g.gewicht * 100) for g in vorlage.gewichtungen}
        gewichte = {k.id: vorhanden.get(k.id, 0) for k in kategorien}
        form = {"nummer": vorlage.nummer or "", "name": vorlage.name}
    return kategorien, gewichte, form


@bp.route("/bildungsgaenge/<int:bildungsgang_id>/vorlagen/neu", methods=["GET", "POST"])
def vorlage_neu(bildungsgang_id):
    bg = Bildungsgang.query.get_or_404(bildungsgang_id)
    kategorien, gewichte, form = _vorlage_formular(bg)

    if request.method != "POST":
        return render_template(
            "admin/vorlage_form.html", bg=bg, kategorien=kategorien, gewichte=gewichte,
            form=form, titel="Lernfeldvorlage anlegen",
        )

    form = {"nummer": request.form.get("nummer", "").strip(), "name": request.form.get("name", "").strip()}
    fehler = []
    if not form["name"]:
        fehler.append("Name darf nicht leer sein.")
    elif len(form["name"]) > 100:
        fehler.append("Name darf maximal 100 Zeichen lang sein.")
    elif any(v.name == form["name"] for v in bg.lernfeldvorlagen):
        fehler.append(f"'{form['name']}' gibt es in diesem Bildungsgang schon.")

    nummer = _nummer_pruefen(form["nummer"], fehler)
    gewichte_prozent, gewicht_fehler = gewichte_aus_formular(request.form, kategorien)
    fehler.extend(gewicht_fehler)

    if fehler:
        for m in fehler:
            flash(m, "error")
        return render_template(
            "admin/vorlage_form.html", bg=bg, kategorien=kategorien, gewichte=gewichte_prozent,
            form=form, titel="Lernfeldvorlage anlegen",
        ), 400

    vorlage = Lernfeldvorlage(bildungsgang_id=bg.id, nummer=nummer, name=form["name"])
    db.session.add(vorlage)
    db.session.flush()
    for k in kategorien:
        db.session.add(VorlageGewichtung(
            vorlage_id=vorlage.id, kategorie_id=k.id, gewicht=gewichte_prozent[k.id] / 100,
        ))
    db.session.commit()
    flash(f"Lernfeldvorlage '{vorlage.label}' wurde angelegt.", "success")
    return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg.id))


@bp.route("/vorlagen/<int:vorlage_id>/bearbeiten", methods=["GET", "POST"])
def vorlage_bearbeiten(vorlage_id):
    vorlage = Lernfeldvorlage.query.get_or_404(vorlage_id)
    bg = vorlage.bildungsgang
    kategorien, gewichte, form = _vorlage_formular(bg, vorlage)

    if request.method != "POST":
        return render_template(
            "admin/vorlage_form.html", bg=bg, kategorien=kategorien, gewichte=gewichte,
            form=form, titel="Lernfeldvorlage bearbeiten",
        )

    form = {"nummer": request.form.get("nummer", "").strip(), "name": request.form.get("name", "").strip()}
    fehler = []
    if not form["name"]:
        fehler.append("Name darf nicht leer sein.")
    elif any(v.name == form["name"] and v.id != vorlage.id for v in bg.lernfeldvorlagen):
        fehler.append(f"'{form['name']}' gibt es in diesem Bildungsgang schon.")

    nummer = _nummer_pruefen(form["nummer"], fehler)
    gewichte_prozent, gewicht_fehler = gewichte_aus_formular(request.form, kategorien)
    fehler.extend(gewicht_fehler)

    if fehler:
        for m in fehler:
            flash(m, "error")
        return render_template(
            "admin/vorlage_form.html", bg=bg, kategorien=kategorien, gewichte=gewichte_prozent,
            form=form, titel="Lernfeldvorlage bearbeiten",
        ), 400

    vorlage.nummer = nummer
    vorlage.name = form["name"]
    vorhandene = {g.kategorie_id: g for g in vorlage.gewichtungen}
    for k in kategorien:
        anteil = gewichte_prozent[k.id] / 100
        if k.id in vorhandene:
            vorhandene[k.id].gewicht = anteil
        else:
            db.session.add(VorlageGewichtung(vorlage_id=vorlage.id, kategorie_id=k.id, gewicht=anteil))
    db.session.commit()
    flash("Lernfeldvorlage gespeichert.", "success")
    return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg.id))


@bp.route("/vorlagen/<int:vorlage_id>/loeschen", methods=["POST"])
def vorlage_loeschen(vorlage_id):
    vorlage = Lernfeldvorlage.query.get_or_404(vorlage_id)
    bg_id = vorlage.bildungsgang_id
    label = vorlage.label
    db.session.delete(vorlage)
    db.session.commit()
    flash(f"Vorlage '{label}' gelöscht. Bestehende Klassen bleiben unverändert.", "success")
    return redirect(url_for("admin.bildungsgang_detail", bildungsgang_id=bg_id))
