"""pytest tests for the SOC Memory matching engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.matcher import ScoredCase, jaccard, rank_cases, score_case, tokenize

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
# Unit tests — tokenize
# ---------------------------------------------------------------------------
class TestTokenize:
    def test_lowercases(self) -> None:
        assert "replication" in tokenize("Replication")

    def test_drops_stopwords(self) -> None:
        tokens = tokenize("the quick fox")
        assert "the" not in tokens

    def test_drops_short_tokens(self) -> None:
        tokens = tokenize("a go to it x")
        assert "a" not in tokens   # single char dropped
        assert "x" not in tokens   # single char dropped
        assert "go" in tokens      # len == 2, kept (drop threshold is len < 2)

    def test_splits_on_punctuation(self) -> None:
        tokens = tokenize("brute-force,login")
        assert "brute" in tokens
        assert "force" in tokens
        assert "login" in tokens

    def test_empty_string(self) -> None:
        assert tokenize("") == set()


# ---------------------------------------------------------------------------
# Unit tests — jaccard
# ---------------------------------------------------------------------------
class TestJaccard:
    def test_identical(self) -> None:
        s = {"a", "b", "c"}
        assert jaccard(s, s) == pytest.approx(1.0)

    def test_disjoint(self) -> None:
        assert jaccard({"a"}, {"b"}) == pytest.approx(0.0)

    def test_half_overlap(self) -> None:
        # {a, b} ∩ {b, c} = {b}, union = {a,b,c} → 1/3
        assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_both_empty(self) -> None:
        assert jaccard(set(), set()) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit tests — score_case
# ---------------------------------------------------------------------------
class TestScoreCase:
    def test_returns_scored_case(self) -> None:
        alert = {
            "title": "replication traffic",
            "source": "Vectra",
            "host": "DC01",
            "account": "system",
            "description": "replication between DC01 and DC02",
        }
        case = next(c for c in ALL_CASES if c["id"] == "SOC-1041")
        result = score_case(alert, case)
        assert isinstance(result, ScoredCase)
        assert result.score > 0.0
        assert result.id == "SOC-1041"

    def test_match_reasons_format(self) -> None:
        alert = {
            "title": "replication traffic",
            "source": "Vectra",
            "host": "DC01",
            "account": "system",
            "description": "replication between DC01 and DC02",
        }
        case = next(c for c in ALL_CASES if c["id"] == "SOC-1041")
        result = score_case(alert, case)
        # At least one reason should be present given shared tokens
        assert len(result.match_reasons) > 0
        # Each reason must follow "field: matched [...] (score X.XX)" pattern
        import re
        for reason in result.match_reasons:
            assert re.match(r"\w+: matched \[.*\] \(score \d+\.\d+\)", reason), (
                f"Unexpected reason format: {reason}"
            )

    def test_zero_score_on_unrelated_alert(self) -> None:
        alert = {
            "title": "zzz",
            "source": "unknown",
            "host": "unknown",
            "account": "unknown",
            "description": "zzz",
        }
        case = next(c for c in ALL_CASES if c["id"] == "SOC-1041")
        result = score_case(alert, case)
        assert result.score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit tests — rank_cases returns ScoredCase list
# ---------------------------------------------------------------------------
class TestRankCases:
    def test_returns_top_n(self) -> None:
        alert = {"title": "test", "source": "", "host": "", "account": "", "description": "test"}
        results = rank_cases(alert, ALL_CASES, top_n=3)
        assert len(results) == 3

    def test_sorted_descending(self) -> None:
        alert = {"title": "replication DC01 DC02", "source": "Vectra", "host": "DC01",
                 "account": "system", "description": "replication traffic between DC01 and DC02"}
        results = rank_cases(alert, ALL_CASES, top_n=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_less_than_cases(self) -> None:
        alert = {"title": "test", "source": "", "host": "", "account": "", "description": "test"}
        results = rank_cases(alert, ALL_CASES, top_n=1)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Demo alert ranking tests
# ---------------------------------------------------------------------------
class TestDemoAlert1:
    """Demo alert 1: AD replication — SOC-1041 must rank first."""

    _ALERT = DEMO_ALERTS[0]

    def test_soc_1041_ranked_first(self) -> None:
        results = rank_cases(self._ALERT, ALL_CASES, top_n=3)
        assert results[0].id == "SOC-1041", (
            f"Expected SOC-1041 first, got {[r.id for r in results]}"
        )

    def test_top3_ids_printed(self) -> None:
        """Convenience: print the top-3 for the report."""
        results = rank_cases(self._ALERT, ALL_CASES, top_n=3)
        for i, r in enumerate(results, 1):
            print(f"  Demo1 #{i}: {r.id} score={r.score:.4f} verdict={r.verdict}")


class TestDemoAlert2:
    """Demo alert 2: sign-in new country — SOC-1057 and SOC-1063 must both appear in top 3."""

    _ALERT = DEMO_ALERTS[1]

    def test_soc_1057_in_top3(self) -> None:
        results = rank_cases(self._ALERT, ALL_CASES, top_n=3)
        ids = [r.id for r in results]
        assert "SOC-1057" in ids, f"SOC-1057 not in top 3: {ids}"

    def test_soc_1063_in_top3(self) -> None:
        results = rank_cases(self._ALERT, ALL_CASES, top_n=3)
        ids = [r.id for r in results]
        assert "SOC-1063" in ids, f"SOC-1063 not in top 3: {ids}"

    def test_top3_ids_printed(self) -> None:
        """Convenience: print the top-3 for the report."""
        results = rank_cases(self._ALERT, ALL_CASES, top_n=3)
        for i, r in enumerate(results, 1):
            print(f"  Demo2 #{i}: {r.id} score={r.score:.4f} verdict={r.verdict}")
