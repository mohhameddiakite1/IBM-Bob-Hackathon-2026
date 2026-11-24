"""Entry point: start SOC Memory on port 5000.

Usage (conda env bobpyenv):
    python run_soc.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from soc_memory.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("SOC_MEMORY_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
