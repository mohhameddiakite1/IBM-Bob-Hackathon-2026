"""Vector index manager — build, persist, load, and query the incident embedding index."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from soc_memory.models import Incident

_VECTORS_FILE = "vectors.npy"
_METADATA_FILE = "metadata.json"


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Return cosine similarity between *query* (1-D) and each row of *matrix*.

    Both inputs are assumed to be float32. Returns a 1-D array of scores in
    ``[-1, 1]`` with the same length as the number of rows in *matrix*.
    """
    q_norm = np.linalg.norm(query)
    if q_norm == 0.0:
        return np.zeros(len(matrix), dtype=np.float32)
    q_unit = query / q_norm
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # Avoid division by zero for zero vectors
    safe_norms = np.where(norms == 0, 1.0, norms)
    m_unit = matrix / safe_norms
    return (m_unit @ q_unit).astype(np.float32)


class IndexManager:
    """Manages the NumPy vector index for historical incident similarity search.

    Workflow
    --------
    1. ``build(incidents)`` — embed all incidents and store the matrix + metadata.
    2. ``save(directory)`` — persist ``vectors.npy`` + ``metadata.json`` to disk.
    3. ``load(directory)`` — restore index from disk.
    4. ``query(text, top_k)`` — embed *text* on-the-fly and return ranked results.
    """

    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None          # shape (N, D)
        self._incidents: list[Incident] | None = None   # parallel list

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self, incidents: list[Incident]) -> None:
        """Embed *incidents* and populate the in-memory index.

        Uses :func:`soc_memory.embedder.embed_incident` for each record.
        A progress line is printed every 10 incidents.
        """
        from soc_memory.embedder import embed_incident

        if not incidents:
            self._matrix = np.empty((0, 384), dtype=np.float32)
            self._incidents = []
            return

        vectors: list[np.ndarray] = []
        for i, inc in enumerate(incidents, 1):
            vectors.append(embed_incident(inc))
            if i % 10 == 0 or i == len(incidents):
                print(f"[index] Embedded {i}/{len(incidents)} incidents …")

        self._matrix = np.stack(vectors, axis=0).astype(np.float32)
        self._incidents = list(incidents)
        print(f"[index] Index built — shape {self._matrix.shape}")

    # ── Persist ───────────────────────────────────────────────────────────────

    def save(self, directory: str) -> None:
        """Save ``vectors.npy`` and ``metadata.json`` to *directory*.

        Raises
        ------
        RuntimeError
            If the index has not been built yet.
        """
        if self._matrix is None or self._incidents is None:
            raise RuntimeError("Index not built. Call build() first.")

        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)

        np.save(str(out / _VECTORS_FILE), self._matrix)

        metadata = [inc.model_dump(mode="json") for inc in self._incidents]
        with open(out / _METADATA_FILE, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)

        print(f"[index] Saved {len(self._incidents)} entries to {out}")

    # ── Load ──────────────────────────────────────────────────────────────────

    def load(self, directory: str) -> None:
        """Load a previously saved index from *directory*.

        Raises
        ------
        FileNotFoundError
            If the expected files are missing from *directory*.
        """
        src = Path(directory)
        vec_path = src / _VECTORS_FILE
        meta_path = src / _METADATA_FILE

        if not vec_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Index files not found in {src}. Run seed.py first."
            )

        self._matrix = np.load(str(vec_path)).astype(np.float32)

        with open(meta_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self._incidents = [Incident(**r) for r in raw]

        print(f"[index] Loaded {len(self._incidents)} incidents from {src}")

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(self, text: str, top_k: int = 5) -> list[tuple[Incident, float]]:
        """Embed *text* and return the top-k most similar incidents.

        Parameters
        ----------
        text:
            Free-text query (incident description, ticket body, analyst note, …).
        top_k:
            Number of results to return.

        Returns
        -------
        list[tuple[Incident, float]]
            Ranked list of ``(incident, cosine_score)`` pairs, highest score first.

        Raises
        ------
        RuntimeError
            If no index is loaded.
        """
        if self._matrix is None or self._incidents is None:
            raise RuntimeError("Index not loaded. Call build() or load() first.")

        from soc_memory.embedder import embed

        q_vec = embed([text])[0]
        scores = _cosine_similarity(q_vec, self._matrix)

        k = min(top_k, len(self._incidents))
        top_indices = np.argsort(scores)[::-1][:k]

        return [(self._incidents[i], float(scores[i])) for i in top_indices]

    # ── Convenience alias kept for seed.py compatibility ──────────────────────

    def search(
        self, query_incident: Incident, top_k: int = 5
    ) -> list[tuple[Incident, float]]:
        """Similarity search using an :class:`~soc_memory.models.Incident` as query.

        Builds a combined text from the incident's title, description, tags,
        and resolution_notes, then delegates to :meth:`query`.
        """
        parts = [
            query_incident.title,
            query_incident.description,
            " ".join(query_incident.tags),
            query_incident.resolution_notes,
        ]
        text = " ".join(p for p in parts if p)
        return self.query(text, top_k=top_k)
