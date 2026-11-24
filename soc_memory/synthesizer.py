"""Synthesis layer — aggregates similarity matches into actionable analyst intelligence.

Defines:
- ``SynthesisResult``      — Pydantic output model.
- ``MatchSummary``         — per-match metadata for display.
- ``Summarizer``           — typing.Protocol (swap point for watsonx.ai).
- ``DeterministicSummarizer`` — default implementation (no LLM required).

Watsonx.ai swap point
---------------------
To replace the deterministic engine with an LLM-backed one, create a class
that satisfies the ``Summarizer`` protocol::

    class WatsonxSummarizer:
        def synthesize(self, query, matches) -> SynthesisResult: ...

Then set ``app.config["SUMMARIZER"] = WatsonxSummarizer()`` in ``app.py``.
No route changes are required.
"""

from __future__ import annotations

from collections import Counter
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from soc_memory.models import IOC, Incident


class MatchSummary(BaseModel):
    """Lightweight summary of a single historical match for display."""

    incident_id: str
    title: str
    severity: str
    score: float
    ioc_overlap_count: int


class SynthesisResult(BaseModel):
    """Structured output from the synthesis layer."""

    shared_iocs: list[IOC]
    top_resolutions: list[str]
    duplicate_candidates: list[MatchSummary]
    match_summary: list[MatchSummary]


@runtime_checkable
class Summarizer(Protocol):
    """Protocol (interface) for all synthesis implementations.

    Swap in a watsonx.ai implementation by creating a class that satisfies
    this protocol — no route changes required.
    """

    def synthesize(
        self,
        query: Incident,
        matches: list[tuple[Incident, float]],
    ) -> SynthesisResult:
        """Produce a SynthesisResult from query incident and similarity matches."""
        ...


class DeterministicSummarizer:
    """Deterministic implementation of the Summarizer protocol.

    Algorithm
    ---------
    1. **Shared IOCs** — collect IOCs from every matched incident; keep those
       that also appear in the query incident.  Comparison is case-insensitive
       for domains/URLs; exact for hashes.  Returned in descending frequency
       order (most-seen-across-matches first).
    2. **Top resolutions** — collect non-empty ``resolution_notes`` from all
       matches, deduplicate by exact string, return up to 3 in score order.
    3. **Duplicate candidates** — matches with cosine score ≥ ``DUPLICATE_THRESHOLD``.
    4. **Match summary** — full ranked ``MatchSummary`` list for every match.
    """

    DUPLICATE_THRESHOLD: float = 0.92

    def synthesize(
        self,
        query: Incident,
        matches: list[tuple[Incident, float]],
    ) -> SynthesisResult:
        """Return a deterministic SynthesisResult for the given query and matches."""

        # ── Normalise query IOC keys (type, lower-value) ──────────────────────
        query_ioc_keys: set[tuple[str, str]] = {
            (ioc.type if isinstance(ioc.type, str) else ioc.type.value,
             ioc.value.lower())
            for ioc in query.iocs
        }

        # ── Count how often each matched-incident IOC appears across matches ──
        ioc_counter: Counter[tuple[str, str]] = Counter()
        ioc_objects: dict[tuple[str, str], IOC] = {}

        for incident, _score in matches:
            seen_in_this = set()
            for ioc in incident.iocs:
                ioc_type = ioc.type if isinstance(ioc.type, str) else ioc.type.value
                key = (ioc_type, ioc.value.lower())
                if key not in seen_in_this:
                    ioc_counter[key] += 1
                    seen_in_this.add(key)
                    ioc_objects[key] = ioc

        # Keep only IOCs that also appear in the query incident
        shared_keys = [k for k in ioc_counter if k in query_ioc_keys]
        shared_keys.sort(key=lambda k: -ioc_counter[k])
        shared_iocs: list[IOC] = [ioc_objects[k] for k in shared_keys]

        # ── Top-3 resolutions (non-empty, deduplicated, score order) ──────────
        seen_resolutions: set[str] = set()
        top_resolutions: list[str] = []
        for incident, _score in matches:
            notes = incident.resolution_notes.strip()
            if notes and notes not in seen_resolutions:
                seen_resolutions.add(notes)
                top_resolutions.append(notes)
            if len(top_resolutions) == 3:
                break

        # ── Build per-match metadata ───────────────────────────────────────────
        match_summary: list[MatchSummary] = []
        duplicate_candidates: list[MatchSummary] = []

        for incident, score in matches:
            ioc_overlap = sum(
                1 for ioc in incident.iocs
                if (
                    (ioc.type if isinstance(ioc.type, str) else ioc.type.value),
                    ioc.value.lower(),
                ) in query_ioc_keys
            )
            severity_val = (
                incident.severity
                if isinstance(incident.severity, str)
                else incident.severity.value
            )
            summary = MatchSummary(
                incident_id=incident.id,
                title=incident.title,
                severity=severity_val,
                score=round(score, 4),
                ioc_overlap_count=ioc_overlap,
            )
            match_summary.append(summary)
            if score >= self.DUPLICATE_THRESHOLD:
                duplicate_candidates.append(summary)

        return SynthesisResult(
            shared_iocs=shared_iocs,
            top_resolutions=top_resolutions,
            duplicate_candidates=duplicate_candidates,
            match_summary=match_summary,
        )
