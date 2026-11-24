"""Unit tests for soc_memory.synthesizer.DeterministicSummarizer.

Runs without loading the embedding model — uses the pre-built index on disk
(``index/``) and an Incident object constructed directly from the seed data
to validate that the synthesis layer produces meaningful, populated results.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soc_memory.index_manager import IndexManager
from soc_memory.models import IOC, Incident
from soc_memory.synthesizer import DeterministicSummarizer, SynthesisResult

# ── Helpers ───────────────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).parent.parent
INDEX_DIR = WORKSPACE / "index"
SEED_FILE = WORKSPACE / "data" / "seed_incidents.json"


def _load_inc001() -> Incident:
    """Load INC-001 directly from the seed JSON (no network / model needed)."""
    with open(SEED_FILE, encoding="utf-8") as fh:
        records = json.load(fh)
    for rec in records:
        if rec["id"] == "INC-001":
            return Incident(**rec)
    raise ValueError("INC-001 not found in seed data")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def index() -> IndexManager:
    """Load the pre-built index from disk (built by seed.py)."""
    if not INDEX_DIR.exists():
        pytest.skip(
            "Index directory not found — run seed.py first: "
            "C:\\ProgramData\\Anaconda3\\envs\\bobpyenv\\python.exe seed.py"
        )
    mgr = IndexManager()
    mgr.load(str(INDEX_DIR))
    return mgr


@pytest.fixture(scope="module")
def synthesis_result(index: IndexManager) -> SynthesisResult:
    """Run synthesizer against INC-001 with top-10 matches."""
    query = _load_inc001()
    matches = index.search(query, top_k=10)
    summarizer = DeterministicSummarizer()
    return summarizer.synthesize(query, matches)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDeterministicSummarizer:
    def test_shared_iocs_populated(self, synthesis_result: SynthesisResult) -> None:
        """shared_iocs must contain at least one IOC from INC-001."""
        assert len(synthesis_result.shared_iocs) > 0, (
            "Expected at least one shared IOC with INC-001 matches"
        )

    def test_shared_ioc_values_match_inc001(self, synthesis_result: SynthesisResult) -> None:
        """Every shared IOC must appear in INC-001's own IOC list."""
        query = _load_inc001()
        query_keys = {
            (ioc.type if isinstance(ioc.type, str) else ioc.type.value,
             ioc.value.lower())
            for ioc in query.iocs
        }
        for ioc in synthesis_result.shared_iocs:
            ioc_type = ioc.type if isinstance(ioc.type, str) else ioc.type.value
            assert (ioc_type, ioc.value.lower()) in query_keys, (
                f"IOC {ioc} is in shared_iocs but not in INC-001's IOC list"
            )

    def test_top_resolutions_populated(self, synthesis_result: SynthesisResult) -> None:
        """top_resolutions must contain at least one non-empty string."""
        assert len(synthesis_result.top_resolutions) > 0, (
            "Expected at least one resolution note from matches"
        )
        for note in synthesis_result.top_resolutions:
            assert note.strip(), "Resolution notes must not be blank strings"

    def test_top_resolutions_capped_at_3(self, synthesis_result: SynthesisResult) -> None:
        """top_resolutions must have at most 3 entries."""
        assert len(synthesis_result.top_resolutions) <= 3

    def test_match_summary_populated(self, synthesis_result: SynthesisResult) -> None:
        """match_summary must have one entry per match (up to top_k=10)."""
        assert 1 <= len(synthesis_result.match_summary) <= 10

    def test_match_summary_scores_in_range(self, synthesis_result: SynthesisResult) -> None:
        """All cosine scores must be in [-1, 1]."""
        for ms in synthesis_result.match_summary:
            assert -1.0 <= ms.score <= 1.0, f"Score out of range: {ms.score}"

    def test_duplicate_candidates_above_threshold(self, synthesis_result: SynthesisResult) -> None:
        """Every duplicate candidate must have score ≥ DUPLICATE_THRESHOLD."""
        threshold = DeterministicSummarizer.DUPLICATE_THRESHOLD
        for ms in synthesis_result.duplicate_candidates:
            assert ms.score >= threshold, (
                f"{ms.incident_id} in duplicate_candidates but score {ms.score} < {threshold}"
            )

    def test_synthesizer_satisfies_protocol(self) -> None:
        """DeterministicSummarizer must satisfy the Summarizer Protocol."""
        from soc_memory.synthesizer import Summarizer
        assert isinstance(DeterministicSummarizer(), Summarizer)
