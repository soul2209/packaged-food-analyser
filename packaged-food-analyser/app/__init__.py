from pathlib import Path

from flask import Flask

from . import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "analyser.sqlite"),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )
    if config:
        app.config.update(config)

    if not Path(app.config["DATABASE"]).exists():
        db.init_db(app.config["DATABASE"])
    else:
        from .reference_extra import ensure_reference
        conn = db.connect(app.config["DATABASE"])
        try:
            ensure_reference(conn)
        finally:
            conn.close()

    app.teardown_appcontext(db.close_db)

    from .routes import bp, pages
    app.register_blueprint(bp)
    app.register_blueprint(pages)
    return app
