"""Entry point: start the Jira Simulator on port 5001.

Usage (conda env bobpyenv):
    python run_jira.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from jira_simulator.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("JIRA_SIMULATOR_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
