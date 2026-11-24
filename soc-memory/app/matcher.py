"""Weighted token-overlap similarity engine for SOC Memory."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Weights — must sum to 1.0
# ---------------------------------------------------------------------------
_WEIGHTS: dict[str, float] = {
    "title": 0.40,
    "description": 0.35,
    "host": 0.15,
    "account": 0.10,
}

# ---------------------------------------------------------------------------
# Stopwords (hardcoded, no file dependency)
# ---------------------------------------------------------------------------
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "in", "on", "at", "to", "is", "was",
        "and", "or", "of", "for", "by", "with", "from", "this",
        "that", "it",
    }
)

_BASE_CASES_PATH = Path(__file__).parent / "data" / "cases.json"
_ADDITIONS_PATH = Path(__file__).parent / "data" / "additions.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ScoredCase:
    """A past case enriched with a similarity score and match reasons."""

    id: str
    title: str
    source: str
    host: str
    account: str
    description: str
    verdict: str
    client_confirmed: bool
    justification: str
    note: str
    analyst: str = ""
    date: str = ""
    team_notes: str = ""
    score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------
def tokenize(text: str) -> set[str]:
    """Lowercase, split on whitespace/punctuation, drop stopwords and short tokens."""
    tokens = re.split(r"[\s\W]+", text.lower())
    return {t for t in tokens if len(t) >= 2 and t not in _STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    """Return Jaccard similarity between two token sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def load_all_cases() -> list[dict]:
    """Load base cases.json plus additions.json (if it exists)."""
    with open(_BASE_CASES_PATH, encoding="utf-8") as fh:
        cases: list[dict] = json.load(fh)
    if _ADDITIONS_PATH.exists():
        with open(_ADDITIONS_PATH, encoding="utf-8") as fh:
            additions: list[dict] = json.load(fh)
        cases = cases + additions
    return cases


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_case(alert: dict, case: dict) -> ScoredCase:
    """Score a single past case against an incoming alert."""
    total = 0.0
    reasons: list[str] = []

    for field_name, weight in _WEIGHTS.items():
        alert_tokens = tokenize(alert.get(field_name, "") or "")
        case_tokens = tokenize(case.get(field_name, "") or "")
        sim = jaccard(alert_tokens, case_tokens)
        if sim > 0.0:
            matched = sorted(alert_tokens & case_tokens)
            reasons.append(
                f"{field_name}: matched {matched} (score {sim:.2f})"
            )
        total += weight * sim

    return ScoredCase(
        id=case["id"],
        title=case["title"],
        source=case.get("source", ""),
        host=case.get("host", ""),
        account=case.get("account", ""),
        description=case["description"],
        verdict=case["verdict"],
        client_confirmed=case.get("client_confirmed", False),
        justification=case["justification"],
        note=case["note"],
        analyst=case.get("analyst", ""),
        date=case.get("date", ""),
        team_notes=case.get("team_notes", ""),
        score=round(total, 6),
        match_reasons=reasons,
    )


def rank_cases(
    alert: dict, cases: list[dict], top_n: int = 3
) -> list[ScoredCase]:
    """Return the top-N cases sorted descending by score, ties broken by case id."""
    scored = [score_case(alert, c) for c in cases]
    scored.sort(key=lambda s: (-s.score, s.id))
    return scored[:top_n]
