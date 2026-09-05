from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.dienst_service import aktive_schueler, dienst_uebersicht, hinweistext, rota_generieren
from app.extensions import db
from app.models import Klasse, Klassendienst

bp = Blueprint("dienste", __name__, url_prefix="/klassen/<int:klasse_id>/dienste")

_LEERE_NEUE_ZEILEN = 6


@bp.route("/")
def liste(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    return render_template(
        "dienste/liste.html",
        klasse=klasse,
        eintraege=klasse.dienste,
        schueler=aktive_schueler(klasse),
        uebersicht=dienst_uebersicht(klasse),
        hinweis=hinweistext(klasse),
        heute=date.today().isoformat(),
        leere_zeilen=range(_LEERE_NEUE_ZEILEN),
    )


@bp.route("/generieren", methods=["POST"])
def generieren(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    try:
        von = date.fromisoformat(request.form.get("von", "").strip())
        bis = date.fromisoformat(request.form.get("bis", "").strip())
    except ValueError:
        flash("Bitte ein gültiges Von-/Bis-Datum angeben.", "error")
        return redirect(url_for("dienste.liste", klasse_id=klasse.id))

    if bis < von:
        flash("'Bis' darf nicht vor 'Von' liegen.", "error")
        return redirect(url_for("dienste.liste", klasse_id=klasse.id))
    if (bis - von) > timedelta(days=366):
        flash("Zeitraum darf höchstens ein Jahr umfassen.", "error")
        return redirect(url_for("dienste.liste", klasse_id=klasse.id))

    angelegt = rota_generieren(klasse, von, bis)
    if angelegt:
        db.session.commit()
        flash(f"{angelegt} neue Diensttage eingeplant.", "success")
    else:
        flash("Keine neuen Diensttage – entweder schon belegt oder keine Schultage im Zeitraum.", "error")
    return redirect(url_for("dienste.liste", klasse_id=klasse.id))


def _schueler_id_oder_none(roh):
    roh = (roh or "").strip()
    return int(roh) if roh.isdigit() else None


@bp.route("/speichern", methods=["POST"])
def speichern(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    erlaubte_ids = {s.id for s in aktive_schueler(klasse)}

    geaendert = geloescht = angelegt = 0

    for eintrag in list(klasse.dienste):
        if request.form.get(f"del_{eintrag.id}") == "on":
            db.session.delete(eintrag)
            geloescht += 1
            continue
        s1 = _schueler_id_oder_none(request.form.get(f"s1_{eintrag.id}"))
        s2 = _schueler_id_oder_none(request.form.get(f"s2_{eintrag.id}"))
        s1 = s1 if s1 in erlaubte_ids else None
        s2 = s2 if s2 in erlaubte_ids else None
        if s1 != eintrag.schueler1_id or s2 != eintrag.schueler2_id:
            eintrag.schueler1_id, eintrag.schueler2_id = s1, s2
            geaendert += 1

    vorhandene_daten = {d.datum for d in klasse.dienste}
    for i in range(_LEERE_NEUE_ZEILEN):
        roh_datum = request.form.get(f"neu_datum_{i}", "").strip()
        if not roh_datum:
            continue
        try:
            datum = date.fromisoformat(roh_datum)
        except ValueError:
            flash(f"Datum '{roh_datum}' ist ungültig – Zeile übersprungen.", "error")
            continue
        if datum in vorhandene_daten:
            flash(f"Für {datum.strftime('%d.%m.%Y')} gibt es schon einen Eintrag – Zeile übersprungen.", "error")
            continue
        s1 = _schueler_id_oder_none(request.form.get(f"neu_s1_{i}"))
        s2 = _schueler_id_oder_none(request.form.get(f"neu_s2_{i}"))
        db.session.add(Klassendienst(
            klasse_id=klasse.id, datum=datum,
            schueler1_id=s1 if s1 in erlaubte_ids else None,
            schueler2_id=s2 if s2 in erlaubte_ids else None,
        ))
        vorhandene_daten.add(datum)
        angelegt += 1

    if geaendert or geloescht or angelegt:
        db.session.commit()
        flash(f"Gespeichert – {geaendert} geändert, {angelegt} neu, {geloescht} gelöscht.", "success")
    else:
        flash("Keine Änderungen.", "success")
    return redirect(url_for("dienste.liste", klasse_id=klasse.id))


@bp.route("/hinweis", methods=["POST"])
def hinweis_speichern(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    text = request.form.get("hinweis", "").strip()
    klasse.dienst_hinweis = text or None
    db.session.commit()
    flash("Hinweistext gespeichert.", "success")
    return redirect(url_for("dienste.liste", klasse_id=klasse.id))


@bp.route("/drucken")
def drucken(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    return render_template(
        "dienste/drucken.html", klasse=klasse, eintraege=klasse.dienste, hinweis=hinweistext(klasse),
    )
