from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import screensaver
from app.extensions import db
from app.models import DashboardLink, Klasse, Schueler

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    anzahl_klassen = Klasse.query.filter_by(aktiv=True).count()
    anzahl_schueler = Schueler.query.count()
    links = DashboardLink.query.order_by(DashboardLink.reihenfolge, DashboardLink.id).all()
    return render_template(
        "main/index.html",
        anzahl_klassen=anzahl_klassen,
        anzahl_schueler=anzahl_schueler,
        links=links,
        screensaver_verfuegbar=screensaver.unterstuetzt(),
        screensaver_aktiv=screensaver.ist_aktiv(),
    )


@bp.route("/dashboard-links/neu", methods=["POST"])
def dashboard_link_neu():
    titel = request.form.get("titel", "").strip()
    url = request.form.get("url", "").strip()
    icon = request.form.get("icon", "").strip()[:8] or None

    fehler = []
    if not titel or len(titel) > 80:
        fehler.append("Titel darf nicht leer und höchstens 80 Zeichen lang sein.")
    if not url or len(url) > 500:
        fehler.append("Link darf nicht leer und höchstens 500 Zeichen lang sein.")
    elif not (url.startswith("http://") or url.startswith("https://")):
        fehler.append("Link muss mit http:// oder https:// beginnen.")

    if fehler:
        for m in fehler:
            flash(m, "error")
        return redirect(url_for("main.index"))

    letzte = db.session.query(db.func.max(DashboardLink.reihenfolge)).scalar() or 0
    db.session.add(DashboardLink(titel=titel, url=url, icon=icon, reihenfolge=letzte + 1))
    db.session.commit()
    flash(f"Kachel '{titel}' wurde angelegt.", "success")
    return redirect(url_for("main.index"))


@bp.route("/dashboard-links/<int:link_id>/loeschen", methods=["POST"])
def dashboard_link_loeschen(link_id):
    link = DashboardLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    flash(f"Kachel '{link.titel}' wurde entfernt.", "success")
    return redirect(url_for("main.index"))


@bp.route("/bildschirmschoner", methods=["POST"])
def bildschirmschoner_umschalten():
    an = request.form.get("an") == "on"
    wirkt = screensaver.setzen(an)
    if not wirkt:
        flash("Bildschirmschoner-Schalter wird nur unter Windows unterstützt.", "error")
    return redirect(url_for("main.index"))
