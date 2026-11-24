"""CLI script: build and persist the SOC Memory vector index from seed data.

Usage (conda env bobpyenv):
    python seed.py

This script:
1. Loads data/seed_incidents.json
2. Validates each record against the Incident Pydantic model
3. Runs the IOC extractor to populate structured IOCs
4. Builds the FAISS/NumPy vector index via IndexManager
5. Persists the index to index/

Full implementation requires Sub-tasks 3 and 4 to be complete.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "seed_incidents.json"
INDEX_DIR = ROOT / "index"


def main() -> None:
    """Build and save the vector index from seed_incidents.json."""
    if not DATA_FILE.exists():
        print(f"[seed] ERROR: {DATA_FILE} not found. Complete Sub-task 3 first.")
        sys.exit(1)

    with open(DATA_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)

    print(f"[seed] Loaded {len(raw)} raw incidents from {DATA_FILE}")

    # Validate against Pydantic model
    from soc_memory.models import Incident

    incidents: list[Incident] = []
    for i, record in enumerate(raw):
        try:
            incidents.append(Incident(**record))
        except Exception as exc:  # noqa: BLE001
            print(f"[seed] WARN: incident[{i}] validation failed — {exc}")

    print(f"[seed] {len(incidents)} incidents passed validation")

    # Run IOC extractor on each incident
    from soc_memory.ioc_extractor import extract_iocs

    for incident in incidents:
        extracted = extract_iocs(incident.title + " " + incident.description + " " + incident.resolution_notes)
        existing_values = {ioc.value.lower() for ioc in incident.iocs}
        for ioc in extracted:
            if ioc.value.lower() not in existing_values:
                incident.iocs.append(ioc)
                existing_values.add(ioc.value.lower())

    # Build and save the index
    from soc_memory.index_manager import IndexManager

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    manager = IndexManager()
    manager.build(incidents)
    manager.save(str(INDEX_DIR))
    print(f"[seed] Index saved to {INDEX_DIR}")


if __name__ == "__main__":
    main()
