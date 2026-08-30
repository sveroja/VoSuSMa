from flask import Blueprint, render_template

from app.models import Klasse, Schueler

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    anzahl_klassen = Klasse.query.filter_by(aktiv=True).count()
    anzahl_schueler = Schueler.query.count()
    return render_template(
        "main/index.html",
        anzahl_klassen=anzahl_klassen,
        anzahl_schueler=anzahl_schueler,
    )
