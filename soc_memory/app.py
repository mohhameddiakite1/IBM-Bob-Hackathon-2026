"""Flask app factory for SOC Memory (port 5000)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

# ---------------------------------------------------------------------------
# Cross-platform path constants
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
INDEX_DIR: Path = ROOT_DIR / "index"


def _build_index_from_seed(index_dir: Path) -> None:
    """Build and persist the vector index from seed data (inline fallback).

    Mirrors seed.py logic so the app can self-heal when index/ is missing.
    """
    data_file = ROOT_DIR / "data" / "seed_incidents.json"
    if not data_file.exists():
        raise FileNotFoundError(
            f"Seed data not found at {data_file}. Run seed.py first."
        )

    with open(data_file, encoding="utf-8") as fh:
        raw = json.load(fh)

    from soc_memory.ioc_extractor import extract_iocs
    from soc_memory.index_manager import IndexManager
    from soc_memory.models import Incident

    incidents: list[Incident] = []
    for record in raw:
        try:
            incidents.append(Incident(**record))
        except Exception:  # noqa: BLE001
            pass

    for incident in incidents:
        extracted = extract_iocs(
            incident.title + " " + incident.description + " " + incident.resolution_notes
        )
        existing_values = {ioc.value.lower() for ioc in incident.iocs}
        for ioc in extracted:
            if ioc.value.lower() not in existing_values:
                incident.iocs.append(ioc)
                existing_values.add(ioc.value.lower())

    index_dir.mkdir(parents=True, exist_ok=True)
    manager = IndexManager()
    manager.build(incidents)
    manager.save(str(index_dir))
    print(f"[app] Auto-built index from seed — {len(incidents)} incidents")


def create_app() -> Flask:
    """Create and configure the SOC Memory Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SOC_MEMORY_SECRET_KEY", "soc-memory-dev-secret")

    # ── Load (or build) the vector index on startup ───────────────────────────
    vectors_path = INDEX_DIR / "vectors.npy"
    if not vectors_path.exists():
        print("[app] Index not found — building from seed data …")
        _build_index_from_seed(INDEX_DIR)

    from soc_memory.index_manager import IndexManager
    index = IndexManager()
    index.load(str(INDEX_DIR))
    app.config["INDEX"] = index

    # ── Attach the deterministic summarizer (swap for WatsonxSummarizer here) ─
    from soc_memory.synthesizer import DeterministicSummarizer
    app.config["SUMMARIZER"] = DeterministicSummarizer()

    # ── Register blueprint ────────────────────────────────────────────────────
    from soc_memory.routes import routes_bp
    app.register_blueprint(routes_bp)

    return app
