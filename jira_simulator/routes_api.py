"""REST API routes for the Jira Simulator (/api/*)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from jira_simulator.app import db
from jira_simulator.models import Ticket

api_bp = Blueprint("api", __name__)


@api_bp.route("/tickets", methods=["GET"])
def list_tickets():
    """Return all tickets as a JSON array."""
    tickets = db.session.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tickets])


@api_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
def get_ticket(ticket_id: int):
    """Return a single ticket by ID, or 404 if not found."""
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return jsonify({"error": f"Ticket {ticket_id} not found"}), 404
    return jsonify(ticket.to_dict())


@api_bp.route("/tickets", methods=["POST"])
def create_ticket():
    """Create a new ticket from JSON body. Returns the created ticket."""
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "Field 'title' is required"}), 400
    if not data.get("description"):
        return jsonify({"error": "Field 'description' is required"}), 400

    ticket = Ticket(
        title=data["title"],
        description=data["description"],
        severity=data.get("severity", "medium"),
        status=data.get("status", "open"),
        iocs=json.dumps(data.get("iocs", [])),
        tags=json.dumps(data.get("tags", [])),
        resolution_notes=data.get("resolution_notes", ""),
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(ticket)
    db.session.commit()
    return jsonify(ticket.to_dict()), 201


@api_bp.route("/tickets/<int:ticket_id>", methods=["PATCH"])
def update_ticket(ticket_id: int):
    """Partially update a ticket (status, resolution_notes, resolved_at, severity)."""
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return jsonify({"error": f"Ticket {ticket_id} not found"}), 404

    data = request.get_json(silent=True) or {}
    if "status" in data:
        ticket.status = data["status"]
    if "resolution_notes" in data:
        ticket.resolution_notes = data["resolution_notes"]
    if "severity" in data:
        ticket.severity = data["severity"]
    if "iocs" in data:
        ticket.iocs = json.dumps(data["iocs"])
    if "tags" in data:
        ticket.tags = json.dumps(data["tags"])

    # Auto-set resolved_at when status moves to resolved/closed
    if data.get("status") in {"resolved", "closed"} and ticket.resolved_at is None:
        ticket.resolved_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify(ticket.to_dict())
