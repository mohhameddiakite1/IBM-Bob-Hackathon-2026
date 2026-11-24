"""Unit tests for soc_memory.connector.JiraSimulatorConnector.

All HTTP calls are mocked — no running server is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from soc_memory.connector import JiraSimulatorConnector
from soc_memory.models import Incident

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

_TICKET_1 = {
    "id": "1",
    "title": "Phishing email targeting finance",
    "description": "Spear-phishing email with link to login.corp-portal.example",
    "severity": "high",
    "status": "open",
    "iocs": ["login.corp-portal.example", "192.0.2.45"],
    "tags": ["phishing", "finance"],
    "resolution_notes": "",
    "created_at": "2026-01-01T00:00:00+00:00",
    "resolved_at": None,
}

_TICKET_2 = {
    "id": "2",
    "title": "Ransomware on WIN-07",
    "description": "C2 callback to 198.51.100.23:443",
    "severity": "critical",
    "status": "open",
    "iocs": ["198.51.100.23"],
    "tags": ["ransomware", "c2"],
    "resolution_notes": "",
    "created_at": "2026-01-02T00:00:00+00:00",
    "resolved_at": None,
}


def _ok_response(json_data: object, status: int = 200) -> MagicMock:
    """Build a mock requests.Response with the given JSON payload."""
    mock = MagicMock()
    mock.ok = status < 400
    mock.status_code = status
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(response=mock)
    return mock


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


class TestPing:
    """Tests for JiraSimulatorConnector.ping()."""

    def test_ping_true_on_health_ok(self):
        """/api/health returns 200 → ping returns True."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response({"status": "ok"})) as mock_get:
            connector = JiraSimulatorConnector()
            result = connector.ping()

        assert result is True
        mock_get.assert_called_once()

    def test_ping_true_fallback_to_tickets(self):
        """/api/health fails, /api/tickets returns 200 → ping returns True."""
        health_err = MagicMock()
        health_err.ok = False
        health_err.status_code = 404

        tickets_ok = _ok_response([_TICKET_1])

        with patch("soc_memory.connector.requests.get", side_effect=[health_err, tickets_ok]):
            connector = JiraSimulatorConnector()
            result = connector.ping()

        assert result is True

    def test_ping_false_on_connection_error(self):
        """Network error on all paths → ping returns False."""
        with patch("soc_memory.connector.requests.get", side_effect=requests.ConnectionError("unreachable")):
            connector = JiraSimulatorConnector()
            result = connector.ping()

        assert result is False

    def test_ping_false_when_all_endpoints_fail(self):
        """Both /api/health and /api/tickets return non-ok → ping returns False."""
        bad = MagicMock()
        bad.ok = False
        bad.status_code = 503

        with patch("soc_memory.connector.requests.get", return_value=bad):
            connector = JiraSimulatorConnector()
            result = connector.ping()

        assert result is False


# ---------------------------------------------------------------------------
# list_tickets()
# ---------------------------------------------------------------------------


class TestListTickets:
    """Tests for JiraSimulatorConnector.list_tickets()."""

    def test_returns_incident_list(self):
        """Successful response → list of Incident objects with correct fields."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response([_TICKET_1, _TICKET_2])):
            connector = JiraSimulatorConnector()
            tickets = connector.list_tickets()

        assert len(tickets) == 2
        assert all(isinstance(t, Incident) for t in tickets)
        assert tickets[0].id == "1"
        assert tickets[0].title == "Phishing email targeting finance"
        assert tickets[0].severity == "high"
        assert tickets[1].id == "2"

    def test_iocs_are_structured(self):
        """Raw IOC strings from the API are converted to structured IOC objects."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response([_TICKET_1])):
            connector = JiraSimulatorConnector()
            tickets = connector.list_tickets()

        ioc_values = {ioc.value for ioc in tickets[0].iocs}
        assert "192.0.2.45" in ioc_values or "login.corp-portal.example" in ioc_values

    def test_returns_empty_list_on_network_error(self):
        """Network failure → empty list, no exception raised."""
        with patch("soc_memory.connector.requests.get", side_effect=requests.ConnectionError("down")):
            connector = JiraSimulatorConnector()
            tickets = connector.list_tickets()

        assert tickets == []

    def test_returns_empty_list_on_http_error(self):
        """HTTP 500 → empty list, no exception raised."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response({}, status=500)):
            connector = JiraSimulatorConnector()
            tickets = connector.list_tickets()

        assert tickets == []


# ---------------------------------------------------------------------------
# get_ticket()
# ---------------------------------------------------------------------------


class TestGetTicket:
    """Tests for JiraSimulatorConnector.get_ticket()."""

    def test_returns_incident_for_valid_id(self):
        """Known ticket ID → Incident with correct data."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response(_TICKET_2)):
            connector = JiraSimulatorConnector()
            incident = connector.get_ticket("2")

        assert isinstance(incident, Incident)
        assert incident.id == "2"
        assert incident.title == "Ransomware on WIN-07"
        assert incident.severity == "critical"

    def test_raises_key_error_on_404(self):
        """404 from the API → KeyError is raised."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response({"error": "not found"}, status=404)):
            connector = JiraSimulatorConnector()
            with pytest.raises(KeyError):
                connector.get_ticket("9999")

    def test_raises_key_error_on_network_error(self):
        """Network failure when fetching single ticket → KeyError is raised."""
        with patch("soc_memory.connector.requests.get", side_effect=requests.ConnectionError("down")):
            connector = JiraSimulatorConnector()
            with pytest.raises(KeyError):
                connector.get_ticket("1")

    def test_tags_preserved(self):
        """Tags list from the API is preserved on the returned Incident."""
        with patch("soc_memory.connector.requests.get", return_value=_ok_response(_TICKET_1)):
            connector = JiraSimulatorConnector()
            incident = connector.get_ticket("1")

        assert "phishing" in incident.tags
        assert "finance" in incident.tags
