import os

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text

from config import config_by_name
from models import db
from routes.analyzer_routes import analyzer_bp
from routes.auth_routes import auth_bp
from routes.builder_routes import builder_bp
from routes.firebase_routes import firebase_bp
from services.firebase_config import get_firestore


def _cors_origins(value: str) -> list[str]:
    origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url.rstrip("/"))
    return origins


def _ensure_auth_columns() -> None:
    """Add auth columns for installations created before username support."""
    inspector = sqlalchemy_inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    additions = []
    if "password_hash" not in columns:
        additions.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
    if "username" not in columns:
        additions.append("ALTER TABLE users ADD COLUMN username VARCHAR(64)")
    if "email_verified" not in columns:
        additions.append("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    for statement in additions:
        db.session.execute(text(statement))
    if "password_hash" not in columns and "password" in columns:
        db.session.execute(
            text("UPDATE users SET password_hash = password WHERE password_hash IS NULL")
        )
    # Store a case-insensitive uniqueness guarantee for usernames in SQL.
    # The index is safe to re-run during every application start.
    db.session.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (LOWER(username))")
    )
    db.session.commit()


def create_app(config_name: str | None = None) -> Flask:
    environment = (config_name or os.getenv("APP_ENV", "development")).lower()
    config_class = config_by_name.get(environment, config_by_name["development"])

    if environment == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in production.")

    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config["DATA_BACKEND"] != "firebase":
        db.init_app(app)

    CORS(
        app,
        resources={r"/*": {"origins": _cors_origins(app.config["CORS_ORIGINS"])}},
        supports_credentials=True,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(analyzer_bp)
    app.register_blueprint(builder_bp)
    app.register_blueprint(firebase_bp)

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        if app.config["DATA_BACKEND"] == "firebase":
            next(get_firestore().collection("users").limit(1).stream(), None)
        else:
            db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Resource not found."}), 404

    @app.errorhandler(500)
    def internal_server_error(_error):
        if app.config["DATA_BACKEND"] != "firebase":
            db.session.rollback()
        return jsonify({"error": "Internal server error."}), 500

    if app.config["DATA_BACKEND"] != "firebase":
        with app.app_context():
            db.create_all()
            _ensure_auth_columns()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))