from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from app.backup import backup_dir, snapshot_erstellen, snapshots

bp = Blueprint("backup", __name__, url_prefix="/backup")


@bp.route("/")
def status():
    ordner = backup_dir(current_app.config)
    return render_template(
        "backup/status.html",
        backup_ordner=str(ordner) if ordner else None,
        snapshots=snapshots(current_app.config),
        db_name=current_app.config.get("ENV_NAME", "db"),
    )


@bp.route("/jetzt", methods=["POST"])
def jetzt():
    try:
        ziel = snapshot_erstellen(current_app.config)
        flash(f"Backup erstellt: {ziel.name}", "success")
    except Exception as exc:  # noqa: BLE001 - Meldung an die Nutzerin, kein Crash
        flash(f"Backup fehlgeschlagen: {exc}", "error")
    return redirect(url_for("backup.status"))
