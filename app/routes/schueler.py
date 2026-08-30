from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.importe import parse_sus_liste
from app.models import Klasse, Notenereintrag, Schueler, SchuelerKlasse
from app.noten_logik import gesamtnote, kategorie_durchschnitt, note_aus_eintrag

bp = Blueprint("schueler", __name__, url_prefix="/schueler")

GESCHLECHT_WAHL = [("", "–"), ("w", "weiblich"), ("m", "männlich"), ("d", "divers")]


def _aktuelle_klasse(schueler):
    for zuordnung in schueler.klassen_zuordnungen:
        if zuordnung.ist_aktiv:
            return zuordnung.klasse
    return None


def _schon_in_klasse(nachname, vorname, klasse_id):
    """Gibt es (irgendeine, auch beendete) Zuordnung mit gleichem Namen in dieser
    Klasse? Dubletten-Schutz beim Import - bewusst auch beendete Zuordnungen, damit
    ein erneuter Import niemand doppelt anlegt."""
    return (
        Schueler.query.join(SchuelerKlasse)
        .filter(
            SchuelerKlasse.klasse_id == klasse_id,
            db.func.lower(Schueler.nachname) == nachname.lower(),
            db.func.lower(Schueler.vorname) == vorname.lower(),
        )
        .first()
        is not None
    )


@bp.route("/")
def liste():
    klasse_id = request.args.get("klasse_id", type=int)

    query = Schueler.query.join(SchuelerKlasse).filter(SchuelerKlasse.aktiv_filter())
    if klasse_id:
        query = query.filter(SchuelerKlasse.klasse_id == klasse_id)
    schueler_liste = query.order_by(Schueler.nachname, Schueler.vorname).all()

    klassen = Klasse.query.filter_by(aktiv=True).order_by(Klasse.bezeichnung).all()

    return render_template(
        "schueler/liste.html",
        schueler_liste=[(s, _aktuelle_klasse(s)) for s in schueler_liste],
        klassen=klassen,
        gewaehlte_klasse_id=klasse_id,
    )


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    klassen = Klasse.query.filter_by(aktiv=True).order_by(Klasse.bezeichnung).all()

    if request.method != "POST":
        return render_template(
            "schueler/neu.html", klassen=klassen, form={}, geschlecht_wahl=GESCHLECHT_WAHL
        )

    form = {
        "vorname": request.form.get("vorname", "").strip(),
        "nachname": request.form.get("nachname", "").strip(),
        "geburtsdatum": request.form.get("geburtsdatum", "").strip(),
        "geschlecht": request.form.get("geschlecht", "").strip(),
        "email": request.form.get("email", "").strip(),
        "betriebs_email": request.form.get("betriebs_email", "").strip(),
        "klasse_id": request.form.get("klasse_id", "").strip(),
    }

    fehler = []
    if not form["vorname"]:
        fehler.append("Vorname darf nicht leer sein.")
    elif len(form["vorname"]) > 80:
        fehler.append("Vorname darf maximal 80 Zeichen lang sein.")

    if not form["nachname"]:
        fehler.append("Nachname darf nicht leer sein.")
    elif len(form["nachname"]) > 80:
        fehler.append("Nachname darf maximal 80 Zeichen lang sein.")

    if form["geschlecht"] and form["geschlecht"] not in ("w", "m", "d"):
        fehler.append("Ungültige Geschlechtsangabe.")

    klasse = None
    if not form["klasse_id"].isdigit():
        fehler.append("Bitte eine Klasse auswählen.")
    else:
        klasse = Klasse.query.get(int(form["klasse_id"]))
        if klasse is None:
            fehler.append("Ungültige Klasse ausgewählt.")

    geburtsdatum = None
    if form["geburtsdatum"]:
        try:
            geburtsdatum = date.fromisoformat(form["geburtsdatum"])
        except ValueError:
            fehler.append("Geburtsdatum ist ungültig.")

    if fehler:
        for meldung in fehler:
            flash(meldung, "error")
        return render_template(
            "schueler/neu.html", klassen=klassen, form=form, geschlecht_wahl=GESCHLECHT_WAHL
        ), 400

    schueler = Schueler(
        vorname=form["vorname"],
        nachname=form["nachname"],
        geburtsdatum=geburtsdatum,
        geschlecht=form["geschlecht"] or None,
        email=form["email"] or None,
        betriebs_email=form["betriebs_email"] or None,
    )
    db.session.add(schueler)
    db.session.flush()
    db.session.add(
        SchuelerKlasse(schueler_id=schueler.id, klasse_id=klasse.id, von=date.today(), bis=None)
    )
    db.session.commit()

    flash(f"'{schueler.vorname} {schueler.nachname}' wurde angelegt.", "success")
    return redirect(url_for("schueler.liste", klasse_id=klasse.id))


@bp.route("/<int:schueler_id>")
def detail(schueler_id):
    schueler = Schueler.query.get_or_404(schueler_id)
    klasse = _aktuelle_klasse(schueler)

    lernfelder_uebersicht = []
    if klasse is not None:
        for lernfeld in sorted(klasse.lernfelder, key=lambda lf: lf.sortkey):
            eintraege = Notenereintrag.query.filter_by(
                schueler_id=schueler.id, lernfeld_id=lernfeld.id
            ).all()
            je_kategorie = {}
            for eintrag in eintraege:
                je_kategorie.setdefault(eintrag.kategorie_id, []).append(eintrag)

            kategorien_uebersicht = []
            for gewichtung in lernfeld.gewichtungen:
                eintraege_der_kategorie = je_kategorie.get(gewichtung.kategorie_id, [])
                kategorien_uebersicht.append(
                    {
                        "kategorie": gewichtung.kategorie,
                        "gewicht": gewichtung.gewicht,
                        "eintraege": [(e, note_aus_eintrag(e)) for e in eintraege_der_kategorie],
                        "durchschnitt": kategorie_durchschnitt(eintraege_der_kategorie),
                    }
                )

            lernfelder_uebersicht.append(
                {
                    "lernfeld": lernfeld,
                    "kategorien": kategorien_uebersicht,
                    "gesamtnote": gesamtnote(lernfeld, je_kategorie),
                }
            )

    return render_template(
        "schueler/detail.html",
        schueler=schueler,
        klasse=klasse,
        lernfelder_uebersicht=lernfelder_uebersicht,
    )


@bp.route("/import/<int:klasse_id>", methods=["GET", "POST"])
def importieren(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)

    if request.method != "POST":
        return render_template("schueler/import.html", klasse=klasse)

    datei = request.files.get("csv_datei")
    if not datei or not datei.filename:
        flash("Bitte eine Datei auswählen.", "error")
        return render_template("schueler/import.html", klasse=klasse), 400

    zeilen, warnungen = parse_sus_liste(datei.read())
    if not zeilen:
        for w in warnungen:
            flash(w, "error")
        return render_template("schueler/import.html", klasse=klasse), 400

    # Status je Zeile für die Vorschau
    for z in zeilen:
        if z["fehler"]:
            z["status"] = "fehler"
        elif _schon_in_klasse(z["nachname"], z["vorname"], klasse.id):
            z["status"] = "vorhanden"
        else:
            z["status"] = "neu"

    for w in warnungen:
        flash(w, "error")

    return render_template(
        "schueler/import_vorschau.html",
        klasse=klasse,
        zeilen=zeilen,
        csv_text=_wieder_text(zeilen),
        anzahl_neu=sum(1 for z in zeilen if z["status"] == "neu"),
    )


def _wieder_text(zeilen: list[dict]) -> str:
    """Serialisiert die geparsten Zeilen als TSV zurück - wird versteckt ins
    Bestätigungsformular gelegt, damit der Import zustandslos bleibt."""
    kopf = "nachname\tvorname\tgeschlecht\temail\tvon\tbis"
    aus = [kopf]
    for z in zeilen:
        aus.append(
            "\t".join([
                z["nachname"],
                z["vorname"],
                z["geschlecht"] or "",
                z["email"] or "",
                z["von"].isoformat() if z["von"] else "",
                z["bis"].isoformat() if z["bis"] else "",
            ])
        )
    return "\n".join(aus)


@bp.route("/import/<int:klasse_id>/anlegen", methods=["POST"])
def importieren_anlegen(klasse_id):
    klasse = Klasse.query.get_or_404(klasse_id)
    text = request.form.get("csv_text", "")

    angelegt = 0
    uebersprungen = 0
    for roh in text.split("\n")[1:]:  # erste Zeile ist der Kopf aus _wieder_text
        if not roh.strip():
            continue
        teile = (roh.split("\t") + [""] * 6)[:6]
        nachname, vorname, geschlecht, email, von_s, bis_s = (t.strip() for t in teile)
        if not nachname or not vorname:
            continue
        if _schon_in_klasse(nachname, vorname, klasse.id):
            uebersprungen += 1
            continue

        schueler = Schueler(
            nachname=nachname,
            vorname=vorname,
            geschlecht=geschlecht or None,
            email=email or None,
        )
        db.session.add(schueler)
        db.session.flush()
        db.session.add(
            SchuelerKlasse(
                schueler_id=schueler.id,
                klasse_id=klasse.id,
                von=date.fromisoformat(von_s) if von_s else date.today(),
                bis=date.fromisoformat(bis_s) if bis_s else None,
            )
        )
        angelegt += 1

    db.session.commit()
    flash(
        f"{angelegt} SuS importiert" + (f", {uebersprungen} übersprungen (schon in der Klasse)" if uebersprungen else "") + ".",
        "success",
    )
    return redirect(url_for("schueler.liste", klasse_id=klasse.id))
