"""Flask test-client tests for soc_memory routes.

Covers:
  GET  /health
  GET  /
  POST /analyze  (free-text path)
  POST /analyze  (ticket_id path — connector raises KeyError)
  POST /analyze  (empty form — error path)
  GET  /incidents/<id>  (found)
  GET  /incidents/<id>  (not found → 404)

The embedding model and JiraSimulatorConnector are mocked so these tests
run offline and without the Jira Simulator server.  The index is built
against a minimal in-memory IndexManager so seed.py does NOT need to have
been run first (but if index/ exists it is ignored in favour of the stub).
"""

from __future__ import annotations

import json
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from soc_memory.index_manager import IndexManager
from soc_memory.models import IOC, IOCType, Incident, Severity, Status
from soc_memory.synthesizer import DeterministicSummarizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident(inc_id: str = "INC-TEST-001", title: str = "Test incident") -> Incident:
    """Return a minimal Incident for use as test data."""
    return Incident(
        id=inc_id,
        title=title,
        description="Phishing email from evil.example.com targeting finance.",
        severity=Severity.high,
        status=Status.open,
        iocs=[IOC(type=IOCType.domain, value="evil.example.com")],
        tags=["phishing", "email"],
        resolution_notes="Blocked sender domain and reset user credentials.",
    )


def _stub_index() -> IndexManager:
    """Return an IndexManager with 3 pre-seeded incidents (no model calls)."""
    inc1 = _make_incident("INC-001", "Phishing email campaign")
    inc2 = _make_incident("INC-002", "Credential harvesting via fake portal")
    inc3 = _make_incident("INC-003", "Ransomware delivery via phishing link")

    mgr = IndexManager()
    rng = np.random.default_rng(42)
    matrix = rng.standard_normal((3, 384)).astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    mgr._matrix = (matrix / norms).astype(np.float32)
    mgr._incidents = [inc1, inc2, inc3]
    return mgr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    """Create a Flask app with a stubbed index injected after app creation.

    Strategy: patch the index load path inside create_app() so it loads our
    stub rather than touching disk or the embedding model.
    """
    stub_mgr = _stub_index()

    # We need to prevent create_app() from calling IndexManager().load(…).
    # Because IndexManager is imported locally inside create_app() we patch
    # the class at its *definition* module so the local import picks it up.
    with patch("soc_memory.index_manager.IndexManager") as MockClass:
        mock_instance = MockClass.return_value
        mock_instance._matrix = stub_mgr._matrix
        mock_instance._incidents = stub_mgr._incidents
        mock_instance.load = MagicMock()
        mock_instance.search = stub_mgr.search.__get__(stub_mgr, IndexManager)

        # Ensure vectors.npy appears to exist so create_app doesn't try to build
        with patch("soc_memory.app.Path.exists", return_value=True):
            from soc_memory.app import create_app
            flask_app = create_app()

    # Regardless of what create_app put in config, replace with our stubs
    flask_app.config["INDEX"] = stub_mgr
    flask_app.config["SUMMARIZER"] = DeterministicSummarizer()
    flask_app.config["TESTING"] = True

    yield flask_app


@pytest.fixture()
def client(app):
    """Return a Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_jira(monkeypatch):
    """Prevent any real HTTP calls to the Jira Simulator."""
    mock_conn = MagicMock()
    mock_conn.ping.return_value = False
    mock_conn.list_tickets.return_value = []
    mock_conn.get_ticket.side_effect = KeyError("TICKET-999")
    monkeypatch.setattr("soc_memory.routes.JiraSimulatorConnector", lambda: mock_conn)
    yield mock_conn


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self, client) -> None:
        """GET /health must return HTTP 200."""
        assert client.get("/health").status_code == 200

    def test_health_json_keys(self, client) -> None:
        """GET /health JSON must include status, index_size, jira_reachable."""
        data = json.loads(client.get("/health").data)
        assert "status" in data
        assert "index_size" in data
        assert "jira_reachable" in data

    def test_health_status_ok(self, client) -> None:
        """GET /health status value must be 'ok'."""
        data = json.loads(client.get("/health").data)
        assert data["status"] == "ok"

    def test_health_index_size(self, client) -> None:
        """GET /health index_size must equal the number of stub incidents (3)."""
        data = json.loads(client.get("/health").data)
        assert data["index_size"] == 3


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestHomePage:
    def test_home_returns_200(self, client) -> None:
        """GET / must return HTTP 200."""
        assert client.get("/").status_code == 200

    def test_home_contains_form(self, client) -> None:
        """GET / HTML must include an analysis form."""
        body = client.get("/").data.decode("utf-8")
        assert "<form" in body.lower()


# ---------------------------------------------------------------------------
# POST /analyze — free-text path
# ---------------------------------------------------------------------------


class TestAnalyzeFreeText:
    def test_analyze_text_returns_200(self, client) -> None:
        """POST /analyze with free-text must return HTTP 200."""
        resp = client.post(
            "/analyze",
            data={"text": "Phishing email from evil.example.com hit finance team."},
        )
        assert resp.status_code == 200

    def test_analyze_text_renders_results(self, client) -> None:
        """POST /analyze with free-text must render the results page."""
        resp = client.post(
            "/analyze",
            data={"text": "Phishing email from evil.example.com hit finance team."},
        )
        body = resp.data.decode("utf-8")
        # results.html contains match summaries; at minimum INC- IDs must appear
        assert "INC-" in body or "match" in body.lower()


# ---------------------------------------------------------------------------
# POST /analyze — ticket_id path (connector raises KeyError → error shown)
# ---------------------------------------------------------------------------


class TestAnalyzeTicketId:
    def test_analyze_unknown_ticket_shows_error(self, client) -> None:
        """POST /analyze with an unknown ticket_id must return 200 with error text."""
        resp = client.post("/analyze", data={"ticket_id": "TICKET-999"})
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert (
            "TICKET-999" in body
            or "error" in body.lower()
            or "could not" in body.lower()
        )


# ---------------------------------------------------------------------------
# POST /analyze — empty form
# ---------------------------------------------------------------------------


class TestAnalyzeEmptyForm:
    def test_analyze_empty_returns_200(self, client) -> None:
        """POST /analyze with no input must return HTTP 200."""
        assert client.post("/analyze", data={}).status_code == 200

    def test_analyze_empty_shows_error(self, client) -> None:
        """POST /analyze with no input must show an inline error."""
        body = client.post("/analyze", data={}).data.decode("utf-8")
        assert "provide" in body.lower() or "error" in body.lower()


# ---------------------------------------------------------------------------
# GET /incidents/<id>
# ---------------------------------------------------------------------------


class TestIncidentDetail:
    def test_known_incident_returns_200(self, client) -> None:
        """GET /incidents/INC-001 must return HTTP 200."""
        assert client.get("/incidents/INC-001").status_code == 200

    def test_known_incident_shows_title(self, client) -> None:
        """GET /incidents/INC-001 must include the incident ID or title."""
        body = client.get("/incidents/INC-001").data.decode("utf-8")
        assert "INC-001" in body or "Phishing" in body

    def test_unknown_incident_returns_404(self, client) -> None:
        """GET /incidents/NONEXISTENT must return HTTP 404."""
        assert client.get("/incidents/NONEXISTENT-XYZ").status_code == 404

    def test_404_page_contains_id(self, client) -> None:
        """GET /incidents/NONEXISTENT must render the 404 template with the missing ID."""
        body = client.get("/incidents/NONEXISTENT-XYZ").data.decode("utf-8")
        assert (
            "NONEXISTENT-XYZ" in body
            or "404" in body
            or "not found" in body.lower()
        )
