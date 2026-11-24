"""Jira Simulator HTTP connector for SOC Memory.

Communicates with the Jira Simulator exclusively via its REST API.
The base URL is read from the JIRA_SIMULATOR_URL environment variable
(default: http://localhost:5001).

Swap point: replace this module's base_url or subclass for a real Jira instance.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from soc_memory.ioc_extractor import extract_iocs
from soc_memory.models import Incident


_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}


def _ticket_to_incident(data: dict[str, Any]) -> Incident:
    """Convert a Jira Simulator ticket dict to an Incident.

    The Jira Simulator stores IOCs as raw strings; we re-extract structured
    IOC objects via the ioc_extractor so the Incident is fully populated.
    Unknown severity/status values (e.g. 'info') fall back to safe defaults
    so a single bad ticket never silently drops the whole list.
    """
    raw_iocs: list[str] = data.get("iocs") or []
    combined_text = " ".join(raw_iocs)
    iocs = extract_iocs(combined_text) if raw_iocs else []

    severity = data.get("severity", "medium")
    if severity not in _VALID_SEVERITIES:
        severity = "medium"

    status = data.get("status", "open")
    if status not in _VALID_STATUSES:
        status = "open"

    return Incident(
        id=str(data.get("id", "")),
        title=data.get("title", ""),
        description=data.get("description", ""),
        severity=severity,
        status=status,
        iocs=iocs,
        tags=data.get("tags") or [],
        resolution_notes=data.get("resolution_notes", ""),
        created_at=data.get("created_at"),
        resolved_at=data.get("resolved_at"),
    )


class JiraSimulatorConnector:
    """HTTP client that calls the Jira Simulator REST API.

    Base URL is read from the JIRA_SIMULATOR_URL environment variable
    (default: http://localhost:5001).
    """

    def __init__(self) -> None:
        """Initialise the connector with the configured base URL."""
        self.base_url = os.getenv("JIRA_SIMULATOR_URL", "http://localhost:5001").rstrip("/")

    def ping(self) -> bool:
        """Return True if the Jira Simulator is reachable.

        Tries GET /api/health first; falls back to GET /api/tickets.
        Returns False on any network or HTTP error.
        """
        for path in ("/api/health", "/api/tickets"):
            try:
                resp = requests.get(f"{self.base_url}{path}", timeout=5)
                if resp.ok:
                    return True
            except requests.RequestException:
                pass
        return False

    def list_tickets(self) -> list[Incident]:
        """Fetch all tickets from the Jira Simulator as Incident objects.

        Returns an empty list on any network or deserialization error.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tickets", timeout=10)
            resp.raise_for_status()
            return [_ticket_to_incident(item) for item in resp.json()]
        except Exception:  # noqa: BLE001
            return []

    def get_ticket(self, ticket_id: str) -> Incident:
        """Fetch a single ticket by ID as an Incident object.

        Raises
        ------
        KeyError
            If the server returns a 404 (ticket not found).
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tickets/{ticket_id}", timeout=10)
            if resp.status_code == 404:
                raise KeyError(f"Ticket {ticket_id!r} not found")
            resp.raise_for_status()
            return _ticket_to_incident(resp.json())
        except KeyError:
            raise
        except requests.RequestException:
            raise KeyError(f"Ticket {ticket_id!r} not found")
