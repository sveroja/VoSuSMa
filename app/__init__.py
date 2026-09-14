from flask import Flask

from app.config import get_config
from app.extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)

    from app.routes.main import bp as main_bp
    from app.routes.klassen import bp as klassen_bp
    from app.routes.schueler import bp as schueler_bp
    from app.routes.lernfelder import bp as lernfelder_bp
    from app.routes.dienste import bp as dienste_bp
    from app.routes.gruppen import bp as gruppen_bp
    from app.routes.noten import bp as noten_bp
    from app.routes.backup import bp as backup_bp
    from app.routes.admin import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(klassen_bp)
    app.register_blueprint(schueler_bp)
    app.register_blueprint(lernfelder_bp)
    app.register_blueprint(dienste_bp)
    app.register_blueprint(gruppen_bp)
    app.register_blueprint(noten_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        from app.migrations import schema_aktualisieren

        schema_aktualisieren(app)   # offene Schema-Migrationen (mit Backup davor)
        db.create_all()             # zusaetzlich komplett neue Tabellen anlegen
        _seed_notenschema_falls_leer()
        _seed_notenkategorien_falls_leer()

    from app.backup import auto_backup_wenn_faellig
    auto_backup_wenn_faellig(app)

    return app


def _seed_notenschema_falls_leer():
    """Legt die feine Dezimal-Notenskala als aktives Schema an, falls noch keine existiert.
    Werte 1:1 aus NotenAusProzenteDez in importTool.ods uebernommen."""
    from app.models import Notenschema, NotenschemaStufe

    if Notenschema.query.first() is not None:
        return

    stufen_daten = [
        (100, 100, 1.0), (99, 99, 1.1), (98, 98, 1.1), (97, 97, 1.2), (96, 96, 1.2),
        (95, 95, 1.3), (94, 94, 1.3), (93, 93, 1.4), (92, 92, 1.4), (91, 91, 1.5),
        (90, 90, 1.6), (89, 89, 1.7), (88, 88, 1.8), (87, 87, 1.9), (85, 86, 2.0),
        (84, 84, 2.1), (83, 83, 2.2), (82, 82, 2.3), (81, 81, 2.4), (80, 80, 2.5),
        (79, 79, 2.5), (78, 78, 2.6), (77, 77, 2.7), (76, 76, 2.8), (75, 75, 2.8),
        (74, 74, 2.9), (72, 73, 3.0), (71, 71, 3.1), (70, 70, 3.2), (68, 69, 3.3),
        (67, 67, 3.4), (65, 66, 3.5), (63, 64, 3.6), (62, 62, 3.7), (60, 61, 3.8),
        (58, 59, 3.9), (56, 57, 4.0), (54, 55, 4.2), (52, 53, 4.3), (50, 51, 4.4),
        (48, 49, 4.5), (46, 47, 4.6), (44, 45, 4.7), (42, 43, 4.8), (40, 41, 4.9),
        (38, 39, 5.0), (36, 37, 5.1), (34, 35, 5.2), (32, 33, 5.3), (30, 31, 5.4),
        (25, 29, 5.5), (20, 24, 5.6), (15, 19, 5.7), (10, 14, 5.8), (5, 9, 5.9),
        (0, 4, 6.0),
    ]

    schema = Notenschema(name="Feine Dezimalskala (Standard)", aktiv=True)
    for von, bis, note in stufen_daten:
        schema.stufen.append(NotenschemaStufe(von_prozent=von, bis_prozent=bis, note=note))

    db.session.add(schema)
    db.session.commit()


def _seed_notenkategorien_falls_leer():
    """Legt die Standard-Notenkategorien an, falls noch keine existieren.
    Strukturdaten (kein Fake-Content) - muessen daher auch in prod ohne
    seed.py vorhanden sein, damit Lernfeld-Gewichtungen konfiguriert werden koennen."""
    from app.models import Notenkategorie
    from app.stammdaten import STANDARD_NOTENKATEGORIEN

    if Notenkategorie.query.first() is not None:
        return

    for schluessel, bezeichnung, _default_gewicht in STANDARD_NOTENKATEGORIEN:
        db.session.add(Notenkategorie(schluessel=schluessel, bezeichnung=bezeichnung))
    db.session.commit()
