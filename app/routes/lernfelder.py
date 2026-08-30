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
from app.noten_logik import gesamtnote, kategorie_durchschnitt, note_aus_eintrag, parse_note
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
        .filter(SchuelerKlasse.klasse_id == klasse.id, SchuelerKlasse.aktiv_filter())
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )


def _kategorie_des_lernfelds(lernfeld, kategorie_id):
    kat = db.session.get(Notenkategorie, kategorie_id)
    if kat is None or not any(g.kategorie_id == kat.id for g in lernfeld.gewichtungen):
        abort(404)
    return kat


def _bulk_kategorien(lernfeld):
    """Kategorien fuer die Erfassen-Buttons: mndl./sonstige zuerst, dann nach Gewicht."""
    return [
        g.kategorie
        for g in sorted(
            lernfeld.gewichtungen,
            key=lambda g: (g.kategorie.schluessel != _KOLLABIERTE_KATEGORIE, -g.gewicht),
        )
    ]


def _ist_punkte_kategorie(kategorie):
    """mndl./sonstige -> direkte Note, alles andere -> Punkte (Heuristik wie im Bulk-Dialog)."""
    return kategorie.schluessel != _KOLLABIERTE_KATEGORIE


def _zahl(wert):
    """Float -> Text fuers Eingabefeld (deutsche Kommaschreibweise, ohne ,0)."""
    return "" if wert is None else f"{wert:g}".replace(".", ",")


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
    return render_template(
        "lernfelder/uebersicht.html",
        klasse=klasse,
        lernfeld=lernfeld,
        spalten=spalten,
        zeilen=zeilen,
        schueler_liste=schueler_liste,
        bulk_kategorien=_bulk_kategorien(lernfeld),
        gewicht_info=[(g.kategorie.bezeichnung, round(g.gewicht * 100)) for g in kategorien_nach_gewicht],
        heute=date.today().isoformat(),
    )


@bp.route("/<int:lernfeld_id>/kategorie/<int:kategorie_id>")
def kategorie_uebersicht(klasse_id, lernfeld_id, kategorie_id):
    """Eine Ebene tiefer: alle Einzelnoten EINER Kategorie als bearbeitbare
    Matrix (SuS x Erfassung). Spalten = (Datum, Bezeichnung)."""
    klasse = Klasse.query.get_or_404(klasse_id)
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    kategorie = _kategorie_des_lernfelds(lernfeld, kategorie_id)
    schueler_liste = _aktive_schueler(klasse)
    ist_punkte = _ist_punkte_kategorie(kategorie)

    eintraege = Notenereintrag.query.filter_by(
        lernfeld_id=lernfeld.id, kategorie_id=kategorie.id
    ).all()

    schluessel_liste = sorted({(e.datum, (e.bezeichnung or "").strip()) for e in eintraege})
    spalten = []
    for i, (d, b) in enumerate(schluessel_liste):
        gruppe = [e for e in eintraege if e.datum == d and (e.bezeichnung or "").strip() == b]
        spalten.append({
            "idx": i, "datum": d, "bezeichnung": b,
            "max_punkte": next((e.max_punkte for e in gruppe if e.max_punkte), None),
        })

    eintrag_von = {}
    for e in eintraege:
        i = schluessel_liste.index((e.datum, (e.bezeichnung or "").strip()))
        eintrag_von[(e.schueler_id, i)] = e

    zeilen = []
    for s in schueler_liste:
        zellen, noten = [], []
        for sp in spalten:
            e = eintrag_von.get((s.id, sp["idx"]))
            note = note_aus_eintrag(e) if e is not None else None
            if note is not None:
                noten.append(note)
            if e is None:
                rohwert = ""
            elif ist_punkte:
                rohwert = _zahl(e.erreichte_punkte)
            else:
                rohwert = _zahl(e.manuelle_note if e.manuelle_note is not None else e.note_direkt)
            zellen.append({"eintrag": e, "note": note, "rohwert": rohwert, "idx": sp["idx"]})
        zeilen.append({
            "schueler": s, "zellen": zellen,
            "schnitt": round(sum(noten) / len(noten), 2) if noten else None,
        })

    return render_template(
        "lernfelder/kategorie_uebersicht.html",
        klasse=klasse, lernfeld=lernfeld, kategorie=kategorie, ist_punkte=ist_punkte,
        spalten=spalten, zeilen=zeilen, schueler_liste=schueler_liste,
        bulk_kategorien=[kategorie], heute=date.today().isoformat(),
    )


@bp.route("/<int:lernfeld_id>/kategorie/<int:kategorie_id>/speichern", methods=["POST"])
def kategorie_speichern(klasse_id, lernfeld_id, kategorie_id):
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    kategorie = _kategorie_des_lernfelds(lernfeld, kategorie_id)
    ist_punkte = _ist_punkte_kategorie(kategorie)
    zurueck = redirect(url_for(
        "lernfelder.kategorie_uebersicht",
        klasse_id=klasse_id, lernfeld_id=lernfeld_id, kategorie_id=kategorie_id,
    ))

    # Spalten-Metadaten (Datum/Bezeichnung/Max je Spaltenindex) aus hidden fields
    spalten = {}
    for key, val in request.form.items():
        if not key.startswith("sp_datum_"):
            continue
        i = key[len("sp_datum_"):]
        try:
            d = date.fromisoformat(val.strip())
        except ValueError:
            continue
        mp_roh = request.form.get(f"sp_max_{i}", "").strip().replace(",", ".")
        spalten[i] = (
            d,
            request.form.get(f"sp_bez_{i}", "").strip() or None,
            float(mp_roh) if mp_roh else None,
        )

    def _wert(roh):
        roh = roh.strip().replace(",", ".")
        if ist_punkte:
            v = float(roh)
            if v < 0:
                raise ValueError
            return v
        return parse_note(roh)

    geaendert = geloescht = angelegt = 0
    fehler = []

    for key in list(request.form):
        if key.startswith("e_") and key[2:].isdigit():
            e = db.session.get(Notenereintrag, int(key[2:]))
            if e is None or e.lernfeld_id != lernfeld.id or e.kategorie_id != kategorie.id:
                continue
            roh = request.form[key].strip()
            if not roh:
                db.session.delete(e)
                geloescht += 1
                continue
            try:
                v = _wert(roh)
            except ValueError:
                fehler.append(roh)
                continue
            if ist_punkte:
                if e.erreichte_punkte != v:
                    e.erreichte_punkte = v
                    geaendert += 1
            elif e.manuelle_note is not None:
                if e.manuelle_note != v:
                    e.manuelle_note = v
                    geaendert += 1
            elif e.note_direkt != v:
                e.note_direkt = v
                geaendert += 1

        elif key.startswith("n_") and request.form[key].strip():
            teile = key.split("_", 2)
            if len(teile) != 3 or teile[1] not in spalten or not teile[2].isdigit():
                continue
            d, bez, mp = spalten[teile[1]]
            try:
                v = _wert(request.form[key])
            except ValueError:
                fehler.append(request.form[key].strip())
                continue
            neu = Notenereintrag(
                schueler_id=int(teile[2]), lernfeld_id=lernfeld.id,
                kategorie_id=kategorie.id, datum=d, bezeichnung=bez,
            )
            if ist_punkte:
                neu.erreichte_punkte = v
                neu.max_punkte = mp
            else:
                neu.note_direkt = v
            db.session.add(neu)
            angelegt += 1

    if geaendert or geloescht or angelegt:
        db.session.commit()
        flash(
            f"Gespeichert – {geaendert} geändert, {angelegt} neu, {geloescht} gelöscht.",
            "success",
        )
    if fehler:
        erwartet = "Punkte ≥ 0" if ist_punkte else "Note 1,0–6,0"
        flash(f"Übersprungen (ungültig, {erwartet}): " + ", ".join(fehler), "error")
    if not (geaendert or geloescht or angelegt or fehler):
        flash("Keine Änderungen.", "success")
    return zurueck


@bp.route("/<int:lernfeld_id>/noten-bulk", methods=["POST"])
def noten_bulk(klasse_id, lernfeld_id):
    """Schnelle Erfassung vieler Einzelnoten direkt aus der Klassenübersicht:
    ein Wert je SuS, gemeinsames Datum/Bezeichnung/Kategorie. Modus 'note' =
    direkte Note, Modus 'punkte' = erreichte Punkte auf gemeinsame Maximalpunkte."""
    lernfeld = _lernfeld_der_klasse(klasse_id, lernfeld_id)
    klasse = Klasse.query.get_or_404(klasse_id)

    weiter = request.form.get("weiter", "")
    ziel = weiter if weiter.startswith(f"/klassen/{klasse_id}/lernfelder/{lernfeld_id}/") else \
        url_for("lernfelder.uebersicht", klasse_id=klasse_id, lernfeld_id=lernfeld_id)
    zurueck = redirect(ziel)

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
