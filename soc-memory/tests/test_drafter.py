"""pytest tests for the SOC Memory note-drafting engine."""
from __future__ import annotations

import json
from pathlib import Path

from app.drafter import draft_note
from app.matcher import ScoredCase, rank_cases

# ---------------------------------------------------------------------------
# Load shared fixtures
# ---------------------------------------------------------------------------
_CASES_PATH = Path(__file__).parent.parent / "app" / "data" / "cases.json"
_DEMO_PATH = Path(__file__).parent.parent / "demo_alerts.json"

with open(_CASES_PATH, encoding="utf-8") as _fh:
    ALL_CASES: list[dict] = json.load(_fh)

with open(_DEMO_PATH, encoding="utf-8") as _fh:
    DEMO_ALERTS: list[dict] = json.load(_fh)


# ---------------------------------------------------------------------------
# Helpers to build minimal ScoredCase objects for unit tests
# ---------------------------------------------------------------------------
def _make_scored(case_id: str, verdict: str, client_confirmed: bool = False) -> ScoredCase:
    return ScoredCase(
        id=case_id,
        title="Test alert",
        source="Test",
        host="HOST01",
        account="user",
        description="test description",
        verdict=verdict,
        client_confirmed=client_confirmed,
        justification="test justification",
        note="test note",
        score=0.9,
        match_reasons=["title: matched ['test'] (score 0.50)"],
    )


# ---------------------------------------------------------------------------
# Tests — draft when all top-3 are CLOSE
# ---------------------------------------------------------------------------
class TestAllClose:
    def test_draft_mentions_top_case_id(self) -> None:
        precedents = [
            _make_scored("SOC-0001", "CLOSE", client_confirmed=True),
            _make_scored("SOC-0002", "CLOSE"),
            _make_scored("SOC-0003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        assert "SOC-0001" in draft

    def test_draft_does_not_cite_outside_top3(self) -> None:
        precedents = [
            _make_scored("SOC-0001", "CLOSE"),
            _make_scored("SOC-0002", "CLOSE"),
            _make_scored("SOC-0003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        assert "SOC-9999" not in draft

    def test_draft_recommends_close(self) -> None:
        precedents = [_make_scored("SOC-0001", "CLOSE")]
        draft = draft_note(precedents)
        assert "closing" in draft.lower() or "close" in draft.lower()


# ---------------------------------------------------------------------------
# Tests — draft when top-3 contain both CLOSE and CREATE
# ---------------------------------------------------------------------------
class TestMixedVerdicts:
    def test_draft_cites_both_close_and_create(self) -> None:
        precedents = [
            _make_scored("SOC-0001", "CLOSE"),
            _make_scored("SOC-0002", "CREATE"),
            _make_scored("SOC-0003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        assert "SOC-0001" in draft
        assert "SOC-0002" in draft

    def test_draft_tells_analyst_to_decide(self) -> None:
        precedents = [
            _make_scored("SOC-0001", "CLOSE"),
            _make_scored("SOC-0002", "CREATE"),
        ]
        draft = draft_note(precedents)
        assert "analyst" in draft.lower() or "decide" in draft.lower()

    def test_draft_does_not_cite_outside_top3(self) -> None:
        precedents = [
            _make_scored("SOC-0001", "CLOSE"),
            _make_scored("SOC-0002", "CREATE"),
            _make_scored("SOC-0003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        # SOC-9999 was never in precedents — must not appear
        assert "SOC-9999" not in draft


# ---------------------------------------------------------------------------
# Tests — empty precedents
# ---------------------------------------------------------------------------
class TestNoPrecedents:
    def test_returns_non_empty_string(self) -> None:
        draft = draft_note([])
        assert isinstance(draft, str)
        assert len(draft) > 0


# ---------------------------------------------------------------------------
# Tests — draft only cites ids from displayed top 3 (generic guard)
# ---------------------------------------------------------------------------
class TestNoCitationOutsideTop3:
    """Ensure the draft never references a case id not in the input list."""

    def test_all_close_no_phantom_id(self) -> None:
        precedents = [
            _make_scored("SOC-A001", "CLOSE"),
            _make_scored("SOC-A002", "CLOSE"),
            _make_scored("SOC-A003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        # Build set of ids that appear in the draft as SOC-XXXX patterns
        import re
        cited = set(re.findall(r"SOC-\w+", draft))
        allowed = {p.id for p in precedents}
        assert cited.issubset(allowed), (
            f"Draft cited ids outside top 3: {cited - allowed}"
        )

    def test_mixed_no_phantom_id(self) -> None:
        precedents = [
            _make_scored("SOC-B001", "CLOSE"),
            _make_scored("SOC-B002", "CREATE"),
            _make_scored("SOC-B003", "CLOSE"),
        ]
        draft = draft_note(precedents)
        import re
        cited = set(re.findall(r"SOC-\w+", draft))
        allowed = {p.id for p in precedents}
        assert cited.issubset(allowed), (
            f"Draft cited ids outside top 3: {cited - allowed}"
        )


# ---------------------------------------------------------------------------
# Demo alert drafting integration tests
# ---------------------------------------------------------------------------
class TestDemoAlert1Draft:
    """Demo alert 1 — all top-3 should be CLOSE, draft must cite SOC-1041."""

    def test_draft_cites_soc_1041(self) -> None:
        results = rank_cases(DEMO_ALERTS[0], ALL_CASES, top_n=3)
        draft = draft_note(results)
        assert "SOC-1041" in draft, (
            f"SOC-1041 not cited in draft. Top 3: {[r.id for r in results]}\nDraft:\n{draft}"
        )

    def test_draft_no_citation_outside_top3(self) -> None:
        import re
        results = rank_cases(DEMO_ALERTS[0], ALL_CASES, top_n=3)
        draft = draft_note(results)
        cited = set(re.findall(r"SOC-\d+", draft))
        allowed = {r.id for r in results}
        assert cited.issubset(allowed), (
            f"Draft cited ids outside top 3: {cited - allowed}"
        )


class TestDemoAlert2Draft:
    """Demo alert 2 — top-3 contains both CLOSE and CREATE; draft must present both outcomes."""

    def test_draft_cites_both_soc_1057_and_soc_1063(self) -> None:
        results = rank_cases(DEMO_ALERTS[1], ALL_CASES, top_n=3)
        draft = draft_note(results)
        ids = [r.id for r in results]
        assert "SOC-1057" in ids, f"SOC-1057 not in top 3: {ids}"
        assert "SOC-1063" in ids, f"SOC-1063 not in top 3: {ids}"
        # Both should be cited in the draft
        assert "SOC-1057" in draft, f"SOC-1057 not cited in draft:\n{draft}"
        assert "SOC-1063" in draft, f"SOC-1063 not cited in draft:\n{draft}"

    def test_draft_no_citation_outside_top3(self) -> None:
        import re
        results = rank_cases(DEMO_ALERTS[1], ALL_CASES, top_n=3)
        draft = draft_note(results)
        cited = set(re.findall(r"SOC-\d+", draft))
        allowed = {r.id for r in results}
        assert cited.issubset(allowed), (
            f"Draft cited ids outside top 3: {cited - allowed}"
        )
