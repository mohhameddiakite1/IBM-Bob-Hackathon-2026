"""New integration tests for Task 2.5 — notices, additions merge, /remember."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app import create_app
from app.routes import _collect_alert_entities, _filter_notices

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
_DEMO_PATH = Path(__file__).parent.parent / "demo_alerts.json"
_NOTICES_PATH = Path(__file__).parent.parent / "app" / "data" / "notices.json"

with open(_DEMO_PATH, encoding="utf-8") as _fh:
    DEMO_ALERTS: list[dict] = json.load(_fh)

with open(_NOTICES_PATH, encoding="utf-8") as _fh:
    ALL_NOTICES: list[dict] = json.load(_fh)


@pytest.fixture()
def client():
    """Standard test client (no additions.json present)."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def client_with_tmp_additions(tmp_path):
    """Test client that uses a temporary additions.json via monkeypatching the path."""
    import app.routes as routes_mod
    import app.matcher as matcher_mod

    original_additions = matcher_mod._ADDITIONS_PATH
    original_route_additions = routes_mod._ADDITIONS_PATH

    tmp_additions = tmp_path / "additions.json"
    matcher_mod._ADDITIONS_PATH = tmp_additions
    routes_mod._ADDITIONS_PATH = tmp_additions

    app_ = create_app()
    app_.config["TESTING"] = True
    with app_.test_client() as c:
        yield c, tmp_additions

    # Restore
    matcher_mod._ADDITIONS_PATH = original_additions
    routes_mod._ADDITIONS_PATH = original_route_additions


# ---------------------------------------------------------------------------
# Notices unit tests
# ---------------------------------------------------------------------------
class TestNoticeFiltering:
    """Unit tests for _filter_notices and entity collection."""

    def test_demo_alert1_shows_N01(self) -> None:
        """Demo alert 1 (host=DC01) must match N-01."""
        alert = DEMO_ALERTS[0]
        entities = _collect_alert_entities(alert)
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-01" in ids, f"N-01 not in matched notices: {ids}"

    def test_demo_alert1_never_shows_expired_N07(self) -> None:
        """Demo alert 1 must never surface N-07 (expired 2026-11-20)."""
        alert = DEMO_ALERTS[0]
        entities = _collect_alert_entities(alert)
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-07" not in ids, "Expired notice N-07 must not appear"

    def test_demo_alert2_shows_N02(self) -> None:
        """Demo alert 2 (host=VPN-GW01) must match N-02."""
        alert = DEMO_ALERTS[1]
        entities = _collect_alert_entities(alert)
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-02" in ids, f"N-02 not in matched notices: {ids}"

    def test_case_insensitive_host_match(self) -> None:
        """Entity matching is case-insensitive."""
        entities = _collect_alert_entities({"host": "dc01", "account": ""})
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-01" in ids

    def test_expired_notice_filtered(self) -> None:
        """N-07 (expires 2026-11-20) is never returned."""
        # DC02 matches N-07 by entity — but it must be filtered
        entities = _collect_alert_entities({"host": "DC02", "account": ""})
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-07" not in ids

    def test_null_expiry_always_shown(self) -> None:
        """Notices with expires=null are always shown when entity matches."""
        # N-03 has entity WSUS-SCAN01, expires=null
        entities = _collect_alert_entities({"host": "WSUS-SCAN01", "account": ""})
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-03" in ids

    def test_ip_extracted_from_description(self) -> None:
        """IPv4 addresses in description are extracted and matched."""
        alert = {
            "host": "",
            "account": "",
            "title": "Spray from 185.220.101.47",
            "description": "Failed attempts from 185.220.101.47",
        }
        entities = _collect_alert_entities(alert)
        assert "185.220.101.47" in entities
        matched = _filter_notices(ALL_NOTICES, entities)
        ids = [n["id"] for n in matched]
        assert "N-04" in ids


# ---------------------------------------------------------------------------
# Notices via /search route (integration)
# ---------------------------------------------------------------------------
class TestNoticesInSearch:
    def test_demo_alert1_response_contains_N01_text(self, client) -> None:
        resp = client.post("/search", data=DEMO_ALERTS[0])
        assert resp.status_code == 200
        text = resp.data.decode("utf-8")
        # N-01 text fragment
        assert "schema updates" in text or "replication tests" in text

    def test_demo_alert1_response_no_N07_text(self, client) -> None:
        resp = client.post("/search", data=DEMO_ALERTS[0])
        text = resp.data.decode("utf-8")
        assert "Firewall maintenance on DC02" not in text

    def test_demo_alert2_response_contains_N02_text(self, client) -> None:
        resp = client.post("/search", data=DEMO_ALERTS[1])
        assert resp.status_code == 200
        text = resp.data.decode("utf-8")
        assert "patching" in text.lower() or "VPN gateway" in text


# ---------------------------------------------------------------------------
# Additions merge tests
# ---------------------------------------------------------------------------
class TestAdditionsMerge:
    def test_additions_included_in_search(self, client_with_tmp_additions) -> None:
        """A case saved via /remember appears in subsequent search results."""
        c, tmp_path = client_with_tmp_additions

        # Save a highly distinctive case
        payload = {
            "title": "Zorbax fluxwave anomaly on TESTHOST99",
            "source": "Vectra",
            "host": "TESTHOST99",
            "account": "zorbax.user",
            "description": "Zorbax fluxwave pattern detected on TESTHOST99 from zorbax.user",
            "analyst": "T. Tester",
            "verdict": "CLOSE",
            "note": "Test addition note.",
        }
        resp = c.post(
            "/remember",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        saved = json.loads(resp.data)
        new_id = saved["saved_as"]
        assert new_id.startswith("SOC-")

        # Verify the file was created
        assert tmp_path.exists()
        additions = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert len(additions) == 1
        assert additions[0]["id"] == new_id

        # Search for it
        search_data = {
            "title": "Zorbax fluxwave anomaly on TESTHOST99",
            "source": "Vectra",
            "host": "TESTHOST99",
            "account": "zorbax.user",
            "description": "Zorbax fluxwave pattern detected on TESTHOST99",
        }
        resp2 = c.post("/search", data=search_data)
        assert resp2.status_code == 200
        assert new_id.encode() in resp2.data, (
            f"Saved case {new_id} not found in search results"
        )


# ---------------------------------------------------------------------------
# /remember route tests
# ---------------------------------------------------------------------------
class TestRememberRoute:
    def test_returns_saved_as_id(self, client_with_tmp_additions) -> None:
        c, _tmp = client_with_tmp_additions
        payload = {
            "title": "Test alert title",
            "source": "Vectra",
            "host": "HOST01",
            "account": "user.test",
            "description": "Test description.",
            "analyst": "R. Novak",
            "verdict": "CLOSE",
            "note": "Test note.",
        }
        resp = c.post(
            "/remember",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "saved_as" in data
        assert data["saved_as"].startswith("SOC-")

    def test_id_is_next_after_highest(self, client_with_tmp_additions) -> None:
        """The new id must be SOC-1190 (highest base is SOC-1189)."""
        c, _tmp = client_with_tmp_additions
        payload = {
            "title": "X",
            "source": "",
            "host": "",
            "account": "",
            "description": "X",
            "analyst": "A",
            "verdict": "CLOSE",
            "note": "",
        }
        resp = c.post(
            "/remember",
            data=json.dumps(payload),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert data["saved_as"] == "SOC-1190"

    def test_verdict_stored_correctly(self, client_with_tmp_additions) -> None:
        c, tmp_path = client_with_tmp_additions
        payload = {
            "title": "Phish test",
            "source": "Google SecOps",
            "host": "WS-0001",
            "account": "user.phish",
            "description": "Phishing test.",
            "analyst": "M. Okafor",
            "verdict": "CREATE",
            "note": "Escalated.",
        }
        c.post("/remember", data=json.dumps(payload), content_type="application/json")
        additions = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert additions[0]["verdict"] == "CREATE"
        assert additions[0]["analyst"] == "M. Okafor"
        assert additions[0]["justification"] == "Added from the live workflow."
        assert additions[0]["client_confirmed"] is False
        assert additions[0]["team_notes"] == ""

    def test_saves_confirmation_text_for_demo_alert1(self, client_with_tmp_additions) -> None:
        """Test the confirmation line from saving demo alert 1."""
        c, _tmp = client_with_tmp_additions
        alert = DEMO_ALERTS[0]
        payload = {
            "title": alert["title"],
            "source": alert["source"],
            "host": alert["host"],
            "account": alert["account"],
            "description": alert["description"],
            "analyst": "S. Bergeron",
            "verdict": "CLOSE",
            "note": "Closing after precedent review.",
        }
        resp = c.post(
            "/remember",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        saved_id = data["saved_as"]
        confirmation = f"Saved to team memory as {saved_id}."
        print(confirmation)  # surfaced in pytest -s output
        assert saved_id.startswith("SOC-")

    def test_base_cases_json_unmodified(self, client_with_tmp_additions) -> None:
        """Base cases.json must never be touched by /remember."""
        from pathlib import Path
        cases_path = Path(__file__).parent.parent / "app" / "data" / "cases.json"
        original = cases_path.read_text(encoding="utf-8")

        c, _tmp = client_with_tmp_additions
        payload = {
            "title": "X", "source": "", "host": "", "account": "",
            "description": "X", "analyst": "A", "verdict": "CLOSE", "note": "",
        }
        c.post("/remember", data=json.dumps(payload), content_type="application/json")

        after = cases_path.read_text(encoding="utf-8")
        assert original == after, "cases.json was modified by /remember!"
