"""SOC Memory Flask routes — analyst UI and API endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from soc_memory.connector import JiraSimulatorConnector
from soc_memory.ioc_extractor import extract_iocs
from soc_memory.models import Incident

routes_bp = Blueprint("soc_memory", __name__)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@routes_bp.route("/health", methods=["GET"])
def health():
    """Return health check: index size and Jira Simulator reachability."""
    index = current_app.config.get("INDEX")
    index_size: int = 0
    if index is not None and index._incidents is not None:
        index_size = len(index._incidents)

    jira_reachable: bool = False
    try:
        jira_reachable = JiraSimulatorConnector().ping()
    except Exception:  # noqa: BLE001
        pass

    return jsonify({
        "status": "ok",
        "index_size": index_size,
        "jira_reachable": jira_reachable,
    })


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@routes_bp.route("/", methods=["GET"])
def index():
    """Analyst home: search form + live Jira ticket list."""
    jira_tickets: list[Incident] = []
    jira_error: str | None = None
    try:
        jira_tickets = JiraSimulatorConnector().list_tickets()
    except Exception as exc:  # noqa: BLE001
        jira_error = str(exc)

    return render_template("index.html", jira_tickets=jira_tickets, jira_error=jira_error)


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

@routes_bp.route("/analyze", methods=["POST"])
def analyze():
    """Accept free-text or a Jira ticket ID, run similarity search + synthesis."""
    index = current_app.config["INDEX"]
    summarizer = current_app.config["SUMMARIZER"]

    # ── Resolve the query incident ────────────────────────────────────────────
    ticket_id: str = (request.form.get("ticket_id") or "").strip()
    text: str = (request.form.get("text") or "").strip()

    query_incident: Incident | None = None
    fetch_error: str | None = None

    if ticket_id:
        try:
            query_incident = JiraSimulatorConnector().get_ticket(ticket_id)
        except KeyError as exc:
            fetch_error = str(exc)
        except Exception as exc:  # noqa: BLE001
            fetch_error = f"Could not fetch ticket {ticket_id!r}: {exc}"
    elif text:
        iocs = extract_iocs(text)
        query_incident = Incident(
            id=str(uuid.uuid4()),
            title="Ad-hoc query",
            description=text,
            iocs=iocs,
        )
    else:
        fetch_error = "Provide either free text or a Jira ticket ID."

    if fetch_error or query_incident is None:
        jira_tickets: list[Incident] = []
        try:
            jira_tickets = JiraSimulatorConnector().list_tickets()
        except Exception:  # noqa: BLE001
            pass
        return render_template(
            "index.html",
            jira_tickets=jira_tickets,
            jira_error=None,
            analyze_error=fetch_error or "No query incident resolved.",
        )

    # ── Similarity search + synthesis ─────────────────────────────────────────
    try:
        matches = index.search(query_incident, top_k=10)
        result = summarizer.synthesize(query_incident, matches)
    except Exception as exc:  # noqa: BLE001
        return render_template(
            "index.html",
            jira_tickets=[],
            jira_error=None,
            analyze_error=f"Analysis error: {exc}",
        )

    return render_template(
        "results.html",
        query=query_incident,
        result=result,
        matches=matches,
    )


# ---------------------------------------------------------------------------
# GET /incidents/<incident_id>
# ---------------------------------------------------------------------------

@routes_bp.route("/incidents/<incident_id>", methods=["GET"])
def incident_detail(incident_id: str):
    """Show full detail for a historical seed incident."""
    index = current_app.config["INDEX"]
    incident: Incident | None = None
    if index._incidents:
        for inc in index._incidents:
            if inc.id == incident_id:
                incident = inc
                break

    if incident is None:
        return render_template("404.html", incident_id=incident_id), 404

    return render_template("incident_detail.html", incident=incident)
