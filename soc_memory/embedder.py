"""Sentence-transformer embedding engine for SOC Memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from soc_memory.models import Incident

# Lazy singleton — model loaded once on first call
_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    """Load and cache the SentenceTransformer model."""
    global _model  # noqa: PLW0603
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            ) from exc
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of texts into dense vectors using all-MiniLM-L6-v2.

    Parameters
    ----------
    texts:
        List of plain-text strings to embed.

    Returns
    -------
    np.ndarray
        Float32 array of shape ``(N, D)`` where ``D`` is the model dimension
        (384 for all-MiniLM-L6-v2).
    """
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return vectors.astype(np.float32)


def embed_incident(incident: "Incident") -> np.ndarray:
    """Build a single embedding vector for one incident.

    Concatenates ``title``, ``description``, ``tags`` (space-joined),
    and ``resolution_notes`` into a single string, then embeds it.

    Returns
    -------
    np.ndarray
        Float32 array of shape ``(D,)``.
    """
    parts = [
        incident.title,
        incident.description,
        " ".join(incident.tags),
        incident.resolution_notes,
    ]
    text = " ".join(p for p in parts if p)
    result = embed([text])
    return result[0]
