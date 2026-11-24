"""HTML CRUD routes for the Jira Simulator web UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template, request, url_for

from jira_simulator.app import db
from jira_simulator.models import Ticket

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/", methods=["GET"])
def ticket_list():
    """Render the ticket list page."""
    tickets = db.session.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return render_template("tickets.html", tickets=tickets)


@ui_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
def ticket_detail(ticket_id: int):
    """Render the ticket detail page."""
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return render_template("404.html"), 404
    iocs = json.loads(ticket.iocs) if ticket.iocs else []
    tags = json.loads(ticket.tags) if ticket.tags else []
    return render_template("ticket_detail.html", ticket=ticket, iocs=iocs, tags=tags)


@ui_bp.route("/tickets/create", methods=["GET", "POST"])
def ticket_create():
    """Render and handle the create-ticket form."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        severity = request.form.get("severity", "medium")
        iocs_raw = request.form.get("iocs", "").strip()
        tags_raw = request.form.get("tags", "").strip()

        if not title or not description:
            return render_template(
                "ticket_create.html",
                error="Title and description are required.",
                form=request.form,
            )

        iocs = [i.strip() for i in iocs_raw.split(",") if i.strip()]
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        ticket = Ticket(
            title=title,
            description=description,
            severity=severity,
            status="open",
            iocs=json.dumps(iocs),
            tags=json.dumps(tags),
            resolution_notes="",
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for("ui.ticket_detail", ticket_id=ticket.id))

    return render_template("ticket_create.html", error=None, form={})


@ui_bp.route("/tickets/<int:ticket_id>/resolve", methods=["POST"])
def ticket_resolve(ticket_id: int):
    """Mark a ticket as resolved with resolution notes."""
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None:
        return render_template("404.html"), 404

    ticket.status = "resolved"
    ticket.resolution_notes = request.form.get("resolution_notes", "").strip()
    ticket.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("ui.ticket_detail", ticket_id=ticket_id))
