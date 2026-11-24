
# Video Link
[https://drive.google.com/file/d/1xVJ-eveIF9GjBNtSBcPeBDYEc-S3nG13/view?usp=sharing](https://github.com/mohhameddiakite1/IBM-Bob-Hackathon-2026)
# SOC Memory

> An intelligent historical incident retrieval and investigation assistant for Security Operations Center (SOC) analysts.

SOC Memory lets a SOC analyst paste free text or select a live ticket from a Jira-like queue and instantly surface the top historically similar incidents, shared indicators of compromise (IOCs), deduplicated resolution playbooks, and near-duplicate alert flags — all without an LLM or internet connection.

---

## Key Features

- **Pull-based ticket ingestion** — analyst selects a live ticket from the Jira Simulator (`GET /api/tickets`) or pastes free text; no polling workers or background queues.
- **Hybrid similarity engine** — `all-MiniLM-L6-v2` sentence embeddings (384-dimensional) with NumPy cosine similarity; FAISS optional.
- **Regex IOC extraction** — automatically extracts IPv4, domain, URL, MD5, SHA-1, SHA-256 from incident text with overlap suppression.
- **Deterministic synthesis layer** — aggregates shared IOCs, deduplicates top-3 resolution playbooks, flags near-duplicate alerts (cosine ≥ 0.92). Zero LLM hallucination risk; pluggable `Summarizer` protocol ready for IBM watsonx.ai.
- **50-incident curated seed dataset** — 8 SOC archetypes (phishing, ransomware, C2 beaconing, lateral movement, data exfiltration, privilege escalation, web exploit, insider threat); 21 shared IOCs.
- **Standalone Jira Simulator** — independent Flask + SQLite ticketing app with full CRUD UI and REST API (port 5001). SOC Memory communicates strictly via HTTP — the connector is swappable for real Jira Cloud.
- **Offline-first** — works entirely without external API keys; enrichment boundary is clean for future abuse.ch/URLhaus integration.

---

## Architecture

```
┌───────────────────────────┐         HTTP REST only         ┌──────────────────────────┐
│      SOC Memory           │ ─────────────────────────────► │    Jira Simulator        │
│  Flask  :5000             │   GET /api/tickets             │  Flask + SQLite  :5001   │
│                           │   GET /api/tickets/<id>        │                          │
│  embedder.py              │                                │  REST API (routes_api)   │
│  ioc_extractor.py         │                                │  Web UI  (routes_ui)     │
│  index_manager.py         │                                │  Ticket CRUD             │
│  synthesizer.py           │                                └──────────────────────────┘
│  connector.py             │
│  routes.py                │
└───────────────────────────┘
         │  loads on startup
         ▼
   index/ (vectors.npy + metadata.json)
   ← built by seed.py from data/seed_incidents.json
```

**Tech stack:** Python 3.11+, Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2, Pydantic v2, sentence-transformers 3, NumPy, Requests, python-dotenv.

---

## Prerequisites

- Python 3.11+ (Conda environment `bobpyenv` recommended)
- All packages in `requirements.txt`

```bash
# macOS / Linux
python -m pip install -r requirements.txt

# Windows (Conda bobpyenv)
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe -m pip install -r requirements.txt
```

> **Note:** `sentence-transformers` downloads ~80 MB (`all-MiniLM-L6-v2`) on first use. `faiss-cpu` is optional; the app falls back to NumPy cosine similarity automatically.

---

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env if you want non-default ports
```

Key variables (all have defaults — `.env` is optional for local dev):

| Variable | Default | Purpose |
|---|---|---|
| `JIRA_SIMULATOR_URL` | `http://localhost:5001` | Base URL SOC Memory uses to call Jira Simulator |
| `JIRA_SIMULATOR_PORT` | `5001` | Port Jira Simulator listens on |
| `SOC_MEMORY_PORT` | `5000` | Port SOC Memory listens on |
| `JIRA_SECRET_KEY` | `jira-simulator-dev-secret` | Flask session secret |
| `SOC_MEMORY_SECRET_KEY` | `soc-memory-dev-secret` | Flask session secret |

### 2. Build the vector index (one-time)

```bash
# macOS / Linux
python seed.py

# Windows (Conda bobpyenv)
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe seed.py
```

This validates all 50 seed incidents, runs IOC extraction, and persists `index/vectors.npy` + `index/metadata.json` (shape `(50, 384)`).

### 3. Start the Jira Simulator

```bash
# macOS / Linux
python run_jira.py

# Windows
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe run_jira.py
```

Open [http://localhost:5001](http://localhost:5001) — 5 sample tickets are auto-seeded on first run.

### 4. Start SOC Memory

```bash
# macOS / Linux
python run_soc.py

# Windows
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe run_soc.py
```

Open [http://localhost:5000](http://localhost:5000).

> If `index/` is missing, SOC Memory auto-builds it from `data/seed_incidents.json` on startup.

---

## Usage

1. **Select a Jira ticket** from the live dropdown on the home page, or **paste free text** directly.
2. Click **Analyse**.
3. The results page shows:
   - **Top 10 historically similar incidents** with cosine similarity scores.
   - **Shared IOCs** (indicators appearing in both the query and matched historical incidents).
   - **Top 3 resolution playbooks** (deduplicated, ranked by similarity score).
   - **Near-duplicate alerts** (cosine ≥ 0.92) flagged to prevent duplicate triage effort.
4. Click any matched incident ID to view its full historical record.

---

## Project Structure

```
IBM-Bob-Hackathon-2026/
├── soc_memory/              # Main analyst application (port 5000)
│   ├── app.py               # Flask factory, index startup, blueprint registration
│   ├── routes.py            # GET /, POST /analyze, GET /incidents/<id>, GET /health
│   ├── models.py            # Pydantic: IOC, Incident, Severity, Status, IOCType
│   ├── ioc_extractor.py     # Regex IOC extraction (IPv4, domain, URL, MD5/SHA1/SHA256)
│   ├── embedder.py          # all-MiniLM-L6-v2 lazy singleton wrapper
│   ├── index_manager.py     # NumPy cosine similarity index (build/save/load/search)
│   ├── synthesizer.py       # DeterministicSummarizer + Summarizer Protocol
│   ├── connector.py         # JiraSimulatorConnector (HTTP-only Jira client)
│   └── templates/           # Jinja2 + Bootstrap 5 UI (index, results, incident_detail)
├── jira_simulator/          # Standalone ticketing app (port 5001)
│   ├── app.py               # Flask factory, SQLAlchemy init, auto-seed
│   ├── models.py            # SQLAlchemy Ticket model
│   ├── routes_api.py        # REST: GET/POST /api/tickets, GET/PATCH /api/tickets/<id>
│   ├── routes_ui.py         # HTML CRUD: ticket list, detail, create, resolve
│   └── templates/           # Jinja2 + Bootstrap 5 UI (tickets, ticket_detail, create)
├── tests/
│   ├── test_connector.py    # 12 tests — JiraSimulatorConnector (mocked HTTP)
│   ├── test_synthesizer.py  # 8 tests — DeterministicSummarizer
│   └── test_routes.py       # 15 tests — SOC Memory Flask routes
├── data/seed_incidents.json # 50 curated incidents, 8 archetypes, 21 shared IOCs
├── index/                   # Persisted vector index (vectors.npy + metadata.json)
├── seed.py                  # CLI: build & persist the vector index
├── run_jira.py              # Entry point: start Jira Simulator
├── run_soc.py               # Entry point: start SOC Memory
├── requirements.txt         # All Python dependencies (clean, cross-platform)
├── .env.example             # Environment variable template
└── AGENTS.md                # Project rules enforced by IBM Bob
```

---

## Running Tests

```bash
# macOS / Linux
python -m pytest tests/ -v

# Windows (Conda bobpyenv)
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe -m pytest tests/ -v
```

**Result: 35/35 passed** (12 connector + 15 routes + 8 synthesizer).

---

## Known Gotchas

| # | Issue | Fix |
|---|-------|-----|
| 1 | **Windows Conda interpreter** — `execute_command` runs in a non-activated subshell; bare `python` fails with `ModuleNotFoundError`. | Always use `C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe` directly. |
| 2 | **`faiss-cpu` Windows wheel** — no pre-built wheel available for all Python 3.11 builds. | `index_manager.py` uses pure NumPy cosine similarity; FAISS is not required. |
| 3 | **Model download on first run** — `all-MiniLM-L6-v2` (~80 MB) is downloaded by HuggingFace Hub. | Subsequent runs use the cached model. Run `seed.py` once before demos. |

---

## Roadmap

- **watsonx.ai LLM synthesizer** — implement `WatsonxSummarizer` satisfying the `Summarizer` protocol; swap in via `USE_WATSONX=1` env flag.
- **Live threat-intel enrichment** — abuse.ch/URLhaus API integration on IOC ingestion.
- **Real Jira Cloud connector** — replace `JiraSimulatorConnector` with an OAuth-authenticated Jira Cloud client using the same interface.
- **Live index updates** — `POST /api/ingest` to append new incidents to the in-memory index without a full rebuild.
- **Pagination** — `?page=` / `?per_page=` on ticket list endpoints.
