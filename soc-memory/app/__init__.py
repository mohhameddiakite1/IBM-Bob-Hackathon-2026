"""Minimal Flask app factory for SOC Memory."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    cases_path = Path(__file__).parent / "data" / "cases.json"
    with open(cases_path, encoding="utf-8") as fh:
        app.config["CASES"] = json.load(fh)

    from app import routes  # noqa: PLC0415
    app.register_blueprint(routes.bp)

    return app
