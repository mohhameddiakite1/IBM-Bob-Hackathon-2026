"""Flask app factory for the Jira Simulator (port 5001)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

# ---------------------------------------------------------------------------
# Database path — stored next to this package so it stays self-contained
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
DB_PATH = _HERE / "jira_simulator.db"

db = SQLAlchemy()


def create_app() -> Flask:
    """Create and configure the Jira Simulator Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("JIRA_SECRET_KEY", "jira-simulator-dev-secret")

    db.init_app(app)

    # Register blueprints
    from jira_simulator.routes_ui import ui_bp
    from jira_simulator.routes_api import api_bp

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Jinja2 helper: parse a JSON string inside a template
    app.jinja_env.filters["from_json"] = json.loads

    with app.app_context():
        db.create_all()
        _seed_if_empty()

    return app


def _seed_if_empty() -> None:
    """Insert sample tickets on first run if the database is empty."""
    from jira_simulator.models import Ticket
    import json
    from datetime import datetime, timezone

    if db.session.query(Ticket).count() > 0:
        return

    sample_tickets = [
        {
            "title": "Phishing email targeting finance department",
            "description": (
                "Multiple employees in finance received a spear-phishing email "
                "impersonating the CFO. The email contained a malicious link pointing to "
                "hxxp://login.corp-portal.example/auth?token=abc123. Three users clicked "
                "the link before the campaign was detected."
            ),
            "severity": "high",
            "status": "open",
            "iocs": json.dumps(["login.corp-portal.example", "192.0.2.45"]),
            "tags": json.dumps(["phishing", "finance", "credential-theft"]),
            "resolution_notes": "",
        },
        {
            "title": "Ransomware detected on workstation WIN-07",
            "description": (
                "EDR alert triggered on WIN-07 for file encryption activity. "
                "Process tree shows explorer.exe spawning cmd.exe then powershell.exe. "
                "C2 callback observed to 198.51.100.23:443. Files encrypted with .locked extension."
            ),
            "severity": "critical",
            "status": "open",
            "iocs": json.dumps(["198.51.100.23", "a3f1c2d4e5b6a7f8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"]),
            "tags": json.dumps(["ransomware", "encryption", "c2"]),
            "resolution_notes": "",
        },
        {
            "title": "Suspicious outbound traffic to unknown IP",
            "description": (
                "Firewall logs show repeated outbound connections from server SRV-DB-02 "
                "to 192.0.2.188 on port 4444. Connections occur every 60 seconds, suggesting "
                "automated beaconing. No business justification found for this traffic."
            ),
            "severity": "medium",
            "status": "open",
            "iocs": json.dumps(["192.0.2.188"]),
            "tags": json.dumps(["c2-beaconing", "network", "server"]),
            "resolution_notes": "",
        },
        {
            "title": "Large data transfer to external cloud storage",
            "description": (
                "DLP alert triggered for user jdoe uploading 4.2 GB to a personal "
                "Dropbox account. Data includes HR records and salary spreadsheets. "
                "Transfer originated from 10.0.1.55 to storage.example-cloud.example."
            ),
            "severity": "high",
            "status": "open",
            "iocs": json.dumps(["storage.example-cloud.example", "10.0.1.55"]),
            "tags": json.dumps(["data-exfiltration", "dlp", "insider"]),
            "resolution_notes": "",
        },
        {
            "title": "Lateral movement detected via pass-the-hash",
            "description": (
                "Security monitoring detected NTLM authentication attempts from "
                "WIN-10 to multiple domain controllers using a harvested hash. "
                "Mimikatz artifact found in C:\\Users\\Public\\debug.exe. "
                "Hash: b1946ac92492d2347c6235b4d2611184."
            ),
            "severity": "critical",
            "status": "open",
            "iocs": json.dumps(["b1946ac92492d2347c6235b4d2611184", "192.0.2.10"]),
            "tags": json.dumps(["lateral-movement", "pass-the-hash", "credential"]),
            "resolution_notes": "",
        },
    ]

    for item in sample_tickets:
        ticket = Ticket(
            title=item["title"],
            description=item["description"],
            severity=item["severity"],
            status=item["status"],
            iocs=item["iocs"],
            tags=item["tags"],
            resolution_notes=item["resolution_notes"],
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(ticket)

    db.session.commit()
