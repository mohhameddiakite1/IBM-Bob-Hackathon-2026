"""Integration tests for SOC Memory Flask routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import create_app

_DEMO_PATH = Path(__file__).parent.parent / "demo_alerts.json"

with open(_DEMO_PATH, encoding="utf-8") as _fh:
    DEMO_ALERTS: list[dict] = json.load(_fh)


@pytest.fixture()
def client():
    """Provide a Flask test client with TESTING=True."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET / — basic health check
# ---------------------------------------------------------------------------
class TestIndexGet:
    def test_returns_200(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200

    def test_contains_form_elements(self, client) -> None:
        html = resp = client.get("/")
        text = resp.data.decode("utf-8")
        assert "<form" in text
        assert 'name="title"' in text
        assert 'name="description"' in text

    def test_contains_demo_buttons(self, client) -> None:
        resp = client.get("/")
        text = resp.data.decode("utf-8")
        assert "demo alert 1" in text.lower() or "Load demo alert 1" in text
        assert "demo alert 2" in text.lower() or "Load demo alert 2" in text


# ---------------------------------------------------------------------------
# POST /search — with demo alert 1 (should surface SOC-1041)
# ---------------------------------------------------------------------------
class TestSearchDemoAlert1:
    _ALERT = DEMO_ALERTS[0]

    def test_returns_200(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert resp.status_code == 200

    def test_contains_soc_1041(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert b"SOC-1041" in resp.data, (
            "SOC-1041 not found in response body for demo alert 1"
        )

    def test_contains_draft_textarea(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert b"draft-text" in resp.data


# ---------------------------------------------------------------------------
# POST /search — with demo alert 2 (should surface SOC-1057 and SOC-1063)
# ---------------------------------------------------------------------------
class TestSearchDemoAlert2:
    _ALERT = DEMO_ALERTS[1]

    def test_returns_200(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert resp.status_code == 200

    def test_contains_soc_1057(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert b"SOC-1057" in resp.data, (
            "SOC-1057 not found in response body for demo alert 2"
        )

    def test_contains_soc_1063(self, client) -> None:
        resp = client.post("/search", data=self._ALERT)
        assert b"SOC-1063" in resp.data, (
            "SOC-1063 not found in response body for demo alert 2"
        )


# ---------------------------------------------------------------------------
# POST /search — empty form
# ---------------------------------------------------------------------------
class TestSearchEmpty:
    def test_returns_200_not_500(self, client) -> None:
        resp = client.post("/search", data={"title": "", "description": ""})
        assert resp.status_code == 200

    def test_shows_error_message(self, client) -> None:
        resp = client.post("/search", data={"title": "", "description": ""})
        text = resp.data.decode("utf-8")
        # Should show a friendly error, not a traceback
        assert "error" in text.lower() or "please" in text.lower()
        assert "Traceback" not in text


# ---------------------------------------------------------------------------
# GET /demo/1 and GET /demo/2 — prefill routes
# ---------------------------------------------------------------------------
class TestDemoRoutes:
    def test_demo_1_returns_200(self, client) -> None:
        resp = client.get("/demo/1")
        assert resp.status_code == 200

    def test_demo_1_prefills_title(self, client) -> None:
        resp = client.get("/demo/1")
        expected_title = DEMO_ALERTS[0]["title"]
        assert expected_title.encode() in resp.data

    def test_demo_2_returns_200(self, client) -> None:
        resp = client.get("/demo/2")
        assert resp.status_code == 200

    def test_demo_invalid_returns_200_with_error(self, client) -> None:
        resp = client.get("/demo/99")
        assert resp.status_code == 200
        assert b"demo alert" in resp.data.lower() or b"No demo alert" in resp.data
