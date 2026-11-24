"""SQLAlchemy Ticket model for the Jira Simulator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from jira_simulator.app import db


class Ticket(db.Model):
    """Represents a security incident ticket in the Jira Simulator."""

    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    severity = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)
    iocs = db.Column(db.Text, nullable=False, default="[]")       # JSON list of IOC strings
    tags = db.Column(db.Text, nullable=False, default="[]")       # JSON list of tag strings
    resolution_notes = db.Column(db.Text, nullable=False, default="")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this ticket to a JSON-compatible dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "iocs": json.loads(self.iocs) if self.iocs else [],
            "tags": json.loads(self.tags) if self.tags else [],
            "resolution_notes": self.resolution_notes,
        }
