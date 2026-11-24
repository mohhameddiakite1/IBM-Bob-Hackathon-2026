"""Minimal Flask app factory for SOC Memory."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

_NOTICES_PATH = Path(__file__).parent / "data" / "notices.json"


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Load cases dynamically via matcher so additions.json is included
    from app.matcher import load_all_cases  # noqa: PLC0415
    app.config["CASES"] = load_all_cases()

    with open(_NOTICES_PATH, encoding="utf-8") as fh:
        app.config["NOTICES"] = json.load(fh)

    from app import routes  # noqa: PLC0415
    app.register_blueprint(routes.bp)

    return app
