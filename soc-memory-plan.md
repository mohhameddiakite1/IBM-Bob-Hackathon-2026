# SOC Memory — Implementation Plan

## Top-Level Overview

Build **SOC Memory**, an intelligent historical-incident retrieval assistant for SOC analysts, plus a companion **Jira Simulator** ticketing application. The two apps are strictly decoupled: Jira Simulator exposes a REST API; SOC Memory calls it exclusively over HTTP.

**Agreed architecture decisions:**
- **Trigger model:** Pull (analyst-driven). Analyst selects a live ticket from Jira Simulator via `GET /api/tickets` or pastes free text. No background polling.
- **Similarity engine:** `all-MiniLM-L6-v2` local embeddings + FAISS/NumPy cosine similarity. Fully offline.
- **LLM layer:** None initially. A pluggable `Summarizer` interface is defined so watsonx.ai or any LLM can be wired in later.
- **Synthesis layer:** Deterministic — aggregates shared IOCs, surfaces top past resolutions, flags potential duplicates.
- **Incident schema:** Structured (id, title, description, severity, status, iocs, tags, resolution_notes). Auto IOC extraction via regex on ingest.
- **Historical dataset:** ~50 curated synthetic tickets across 6–8 archetypes (phishing, ransomware, C2 beaconing, data exfiltration, lateral movement, insider threat, web exploit, DDoS). Realistic IOCs baked in. abuse.ch enrichment hook reserved for future use.
- **Jira Simulator stack:** Flask + Jinja2 + SQLite, port 5001. Full CRUD UI + `/api/` REST endpoints.
- **SOC Memory stack:** Flask + Jinja2, port 5000. Analyst-focused UI.
- **Vector index lifecycle:** Built from seed data via `seed.py`. Persisted to disk. Auto-rebuilt on startup if missing. Optional manual "Sync Resolved Tickets" endpoint (time-permitting).

**Non-goals (future enhancements):**
- Push/webhook automation
- Live abuse.ch enrichment at seed time
- Dynamic index growth as Jira tickets resolve
- LLM-generated summaries

---

## Sub-Task 1 — Project Scaffolding & Shared Data Model

**Status:** `[ ] pending`

### Intent
Establish the folder structure, dependency files, shared data model, and configuration so every subsequent sub-task has a stable foundation to build on.

### Expected Outcomes
- `jira_simulator/` and `soc_memory/` packages exist with correct `__init__.py` files
- `requirements.txt` lists all dependencies for both apps
- `.env.example` documents all environment variables
- A single shared `Incident` Pydantic model is defined (used by the seed loader, the SOC Memory analysis engine, and the Jira Simulator response serializer)
- Cross-platform `pathlib.Path` constants defined for data/index directories

### Todo List
1. Create top-level folder structure:
   ```
   jira_simulator/
     __init__.py
     app.py          # Flask app factory
     models.py       # SQLAlchemy Ticket model
     routes_ui.py    # HTML CRUD routes
     routes_api.py   # /api/* REST routes
     templates/
     static/
   soc_memory/
     __init__.py
     app.py          # Flask app factory
     models.py       # Pydantic Incident + IOC models
     ioc_extractor.py
     embedder.py
     index_manager.py
     connector.py    # Jira Simulator HTTP client
     synthesizer.py  # Deterministic synthesis (pluggable interface)
     routes.py
     templates/
     static/
   data/
     seed_incidents.json
   index/            # FAISS/numpy index files (gitignored)
   seed.py           # CLI: build and persist the vector index
   run_jira.py       # Entry point: python run_jira.py
   run_soc.py        # Entry point: python run_soc.py
   requirements.txt
   .env.example
   ```
2. Write `requirements.txt`:
   - `flask`, `flask-sqlalchemy`, `sqlalchemy`
   - `pydantic`
   - `sentence-transformers`
   - `faiss-cpu` (or fall back to `numpy` cosine similarity if FAISS install fails on Windows)
   - `requests`
   - `python-dotenv`
3. Write `.env.example` with `JIRA_SIMULATOR_URL=http://localhost:5001`, `SOC_MEMORY_PORT=5000`, `JIRA_SIMULATOR_PORT=5001`
4. Define `soc_memory/models.py`: `IOC(type, value)` and `Incident` Pydantic models with all fields from the agreed schema
5. Add `index/` to `.gitignore`

### Relevant Context
- AGENTS.md §3: use `pathlib.Path`, `encoding="utf-8"`, never hardcode secrets
- AGENTS.md §2: type hints on all function signatures, one-line docstrings on public functions

---

## Sub-Task 2 — Jira Simulator: Database, REST API & CRUD UI

**Status:** `[ ] pending`

### Intent
Build the complete Jira Simulator as a standalone Flask app with SQLite persistence, a full CRUD web UI, and clean JSON REST endpoints that SOC Memory will call.

### Expected Outcomes
- App runs on port 5001 (`python run_jira.py`)
- SQLite database auto-created on first run
- Web UI: ticket list page, ticket detail page, create-ticket form, resolve/close action with resolution notes field
- REST API: `GET /api/tickets`, `GET /api/tickets/<id>`, `POST /api/tickets`, `PATCH /api/tickets/<id>`
- API responses match the shared `Incident` schema (serialized as JSON)
- All routes handle errors gracefully (404 for missing tickets, 400 for bad input)

### Todo List
1. Implement `jira_simulator/models.py`: SQLAlchemy `Ticket` model with columns matching the agreed incident schema (id, title, description, severity, status, created_at, resolved_at, iocs as JSON text, tags as JSON text, resolution_notes)
2. Implement `jira_simulator/app.py`: Flask app factory, SQLAlchemy init, `db.create_all()` on startup
3. Implement `jira_simulator/routes_api.py`: the four REST endpoints with JSON serialization; validate required fields on POST
4. Implement `jira_simulator/routes_ui.py`: ticket list, detail, create form, resolve form using Jinja2 templates
5. Create Jinja2 templates with clean, minimal HTML (Bootstrap CDN for styling): `base.html`, `tickets.html`, `ticket_detail.html`, `ticket_create.html`
6. Write `run_jira.py` entry point
7. Seed 5–10 sample tickets at first run if the database is empty (so the app is immediately usable)

### Relevant Context
- SOC Memory calls `GET /api/tickets` and `GET /api/tickets/<id>` — these are the most critical endpoints
- PATCH endpoint needs to support updating `status`, `resolution_notes`, and `resolved_at`
- IOCs and tags stored as JSON strings in SQLite; deserialized to lists on read
- `jira_simulator` must never import from `soc_memory`

---

## Sub-Task 3 — Synthetic Incident Dataset (seed_incidents.json)

**Status:** `[ ] pending`

### Intent
Create the curated historical incident dataset that powers SOC Memory's knowledge base. This is the "institutional memory" the system searches against.

### Expected Outcomes
- `data/seed_incidents.json` contains ~50 realistic SOC incidents
- Covers 6–8 archetypes: phishing, ransomware, C2 beaconing, data exfiltration, lateral movement, insider threat, web exploit, DDoS
- Each incident has: realistic title, description with narrative, severity (low/medium/high/critical), status (resolved), timestamps, structured IOCs (IPs, domains, hashes, URLs), tags, and meaningful resolution_notes
- IOC values are plausible but fictional (RFC 5737 IPs: 192.0.2.x, 198.51.100.x; .example domains; fake SHA256 hashes)
- Enough variation within each archetype that similarity search produces interesting ranked results (not all identical)

### Todo List
1. Define the 6–8 archetypes and allocate ~6–8 incidents per archetype
2. For each archetype, write incidents with deliberately overlapping IOCs and resolution patterns (so similarity search is demonstrably useful)
3. Include at least 2–3 incidents per archetype that share one or more IOCs with other incidents in the same archetype (to demonstrate IOC exact-match pre-filtering)
4. Write the full JSON array to `data/seed_incidents.json` conforming to the `Incident` Pydantic schema
5. Validate the file loads cleanly against the `Incident` model

### Relevant Context
- IOC exact-match pre-filtering is a key feature — the dataset must have enough IOC overlap to demonstrate it
- Resolution notes should be specific enough to be useful suggestions (e.g., "Blocked C2 IP at perimeter firewall; reimaged host WIN-04; reset user credentials for jsmith")
- RFC 5737 / RFC 2606 reserved ranges ensure no accidental real-world IOC exposure

---

## Sub-Task 4 — IOC Extractor & Embedding Engine

**Status:** `[ ] pending`

### Intent
Build the two core technical components of SOC Memory: the automatic IOC extractor (regex-based) and the embedding/index engine (sentence-transformers + FAISS/NumPy).

### Expected Outcomes
- `soc_memory/ioc_extractor.py`: `extract_iocs(text: str) -> list[IOC]` using regex patterns for IPv4, domains, URLs, MD5/SHA1/SHA256 hashes
- `soc_memory/embedder.py`: loads `all-MiniLM-L6-v2` once at import time; exposes `embed(texts: list[str]) -> np.ndarray`
- `soc_memory/index_manager.py`: builds index from `list[Incident]`, saves/loads to `index/` directory, exposes `search(query_incident: Incident, top_k: int) -> list[tuple[Incident, float]]`
- Search combines IOC exact-match pre-filtering with semantic similarity ranking
- `seed.py`: loads `seed_incidents.json`, runs IOC extractor on each incident, builds and saves the index

### Todo List
1. Implement `ioc_extractor.py` with regex patterns for: IPv4 addresses, FQDNs/domains, HTTP/HTTPS URLs, MD5 (32 hex), SHA1 (40 hex), SHA256 (64 hex); merge extracted IOCs with any structured `iocs` already on the incident, deduplicate
2. Implement `embedder.py`: lazy-load `SentenceTransformer("all-MiniLM-L6-v2")`; embed text as `title + " " + description + " " + resolution_notes`
3. Implement `index_manager.py`:
   - `build(incidents)`: embed all incidents, store vectors + metadata
   - `save(path)` / `load(path)`: persist index (numpy `.npy` for vectors, JSON for metadata) — use numpy save/load as FAISS fallback for Windows compatibility
   - `search(query, top_k)`: IOC pre-filter → cosine similarity → return ranked results with scores
4. Implement `seed.py`: CLI script that loads JSON, validates against Pydantic model, runs extractor, calls `index_manager.build()`, saves to `index/`
5. Add auto-build-on-startup guard in SOC Memory's `app.py`: if `index/` is missing or empty, run seed automatically

### Relevant Context
- Use numpy cosine similarity as the primary implementation; wrap FAISS as an optional accelerator if available
- The index must store enough metadata to reconstruct the full `Incident` object for display (store as JSON alongside the vectors)
- `pathlib.Path` for all file I/O; `encoding="utf-8"` for all JSON reads/writes

---

## Sub-Task 5 — Deterministic Synthesis Layer

**Status:** `[ ] pending`

### Intent
Build the pluggable synthesis layer that turns raw similarity results into actionable analyst intelligence: shared IOC aggregation, top past resolutions, and duplicate flagging.

### Expected Outcomes
- `soc_memory/synthesizer.py`: defines `Summarizer` protocol/ABC and a `DeterministicSummarizer` implementation
- `DeterministicSummarizer.synthesize(query: Incident, matches: list[tuple[Incident, float]]) -> SynthesisResult`
- `SynthesisResult` contains: `shared_iocs` (IOCs appearing in both query and ≥1 match), `top_resolutions` (resolution_notes from top matches, deduplicated), `duplicate_candidates` (matches with score above a high threshold, e.g., 0.92), `match_summary` (list of match metadata for display)
- The `Summarizer` protocol is the only interface SOC Memory's routes ever call — swapping in an LLM summarizer requires only a new class, not route changes

### Todo List
1. Define `Summarizer` as a `typing.Protocol` with a single `synthesize(query, matches) -> SynthesisResult` method
2. Define `SynthesisResult` as a Pydantic model (or dataclass) with the four fields above
3. Implement `DeterministicSummarizer`:
   - Shared IOC aggregation: compare `query.iocs` against each match's IOCs, collect matches with IOC overlap
   - Top resolutions: take `resolution_notes` from top-3 matches by score (skip empty notes)
   - Duplicate candidates: matches with cosine similarity ≥ 0.92
   - Match summary: title, score, severity, IOC overlap count, ticket id for each match
4. Wire `DeterministicSummarizer` as the default in SOC Memory's app config; document the swap point

### Relevant Context
- IOC comparison should be case-insensitive for domains/URLs; exact for IPs and hashes
- The `Summarizer` protocol is the future integration point for watsonx.ai — keep its signature minimal and serialization-friendly

---

## Sub-Task 6 — Jira Simulator HTTP Connector

**Status:** `[ ] pending`

### Intent
Build the HTTP client in SOC Memory that calls the Jira Simulator REST API, with graceful error handling and clean conversion to the internal `Incident` model.

### Expected Outcomes
- `soc_memory/connector.py`: `JiraSimulatorConnector` class
- `list_tickets() -> list[Incident]`: calls `GET /api/tickets`, maps JSON → `Incident`
- `get_ticket(ticket_id: str) -> Incident`: calls `GET /api/tickets/<id>`, maps JSON → `Incident`
- All calls wrapped in `try/except` with meaningful error messages (never raw stack traces)
- Base URL loaded from environment variable `JIRA_SIMULATOR_URL` (default `http://localhost:5001`)
- The connector is the **only** place in `soc_memory` that knows about the Jira Simulator's URL structure — all other code uses `Incident` objects

### Todo List
1. Implement `JiraSimulatorConnector.__init__`: read `JIRA_SIMULATOR_URL` from env
2. Implement `list_tickets()`: GET request, parse JSON array, map each item to `Incident` using the IOC extractor to auto-extract any IOCs missing from the structured field
3. Implement `get_ticket(ticket_id)`: GET request, parse single ticket
4. Add connection error handling: if Jira Simulator is unreachable, return empty list / raise with a user-friendly message that the UI can display
5. Add a `ping() -> bool` method for the UI to check connectivity and show a warning banner if Jira Simulator is offline

### Relevant Context
- The connector must call `ioc_extractor.extract_iocs()` on fetched tickets to ensure IOCs are populated even if the Jira Simulator ticket has no structured IOCs
- Never import from `jira_simulator` directly — only HTTP calls

---

## Sub-Task 7 — SOC Memory Flask App & Analyst UI

**Status:** `[ ] pending`

### Intent
Build the SOC Memory analyst interface: the Flask app that ties together the connector, index manager, and synthesis layer into a usable, demo-ready UI.

### Expected Outcomes
- App runs on port 5000 (`python run_soc.py`)
- Home page: live ticket selector (dropdown populated from Jira Simulator) + free-text paste area; Jira Simulator offline warning banner if unreachable
- Results page: top-N similar incidents with similarity scores and severity badges; shared IOCs section; top past resolutions section; duplicate candidate alerts
- Ticket detail modal/page: full details of a selected historical match
- Optional: "Sync Resolved Tickets" button that calls a `/sync` endpoint (ingests resolved Jira Simulator tickets into the index)
- All pages use a consistent, analyst-focused dark-ish theme (Bootstrap CDN)

### Todo List
1. Implement `soc_memory/app.py`: Flask app factory, load connector + index_manager + synthesizer as app-level singletons; auto-build index on startup if missing
2. Implement `soc_memory/routes.py`:
   - `GET /`: render home page, fetch ticket list from connector
   - `POST /analyze`: accept `ticket_id` or `free_text`, fetch or construct `Incident`, run IOC extraction, call `index_manager.search()`, call `synthesizer.synthesize()`, render results
   - `GET /ticket/<id>`: render historical ticket detail (from index metadata)
   - `POST /sync` (optional): fetch resolved tickets from Jira Simulator, ingest into index
3. Create Jinja2 templates: `base.html`, `index.html`, `results.html`, `ticket_detail.html`
4. Style with Bootstrap 5 CDN; add severity colour badges (critical=red, high=orange, medium=yellow, low=green); highlight IOC matches
5. Write `run_soc.py` entry point
6. Add a `/health` endpoint returning JSON `{"status": "ok", "index_size": N}` for quick validation

### Relevant Context
- Index manager and synthesizer must be initialized once at startup, not per-request (embedding model load is expensive)
- Free-text input path: construct a minimal `Incident` with just `title=""` and `description=<pasted text>`, run IOC extractor, then search
- Display similarity scores as percentages (multiply cosine similarity by 100, round to 1 decimal)

---

## Sub-Task 8 — Integration, Validation & README

**Status:** `[ ] pending`

### Intent
Verify the full end-to-end workflow works, fix any integration issues, and produce project documentation.

### Expected Outcomes
- Full flow works: `seed.py` → `run_jira.py` → `run_soc.py` → analyst selects ticket → results displayed
- Both apps start cleanly on a fresh clone with `pip install -r requirements.txt` + `python seed.py`
- `README.md` updated with: project description, architecture diagram (ASCII or Mermaid), quickstart steps, and feature list
- `AGENTS.md` updated with any discovered gotchas (e.g., FAISS Windows install quirks, sentence-transformers first-run download)

### Todo List
1. Run the `verify` skill to check all Python files for import errors and syntax issues
2. Test the full analyst flow manually: seed → start Jira Simulator → start SOC Memory → select a ticket → verify results appear
3. Test the free-text paste path with a manually typed incident description
4. Test graceful degradation: start SOC Memory with Jira Simulator offline → verify warning banner appears, free-text path still works
5. Test auto-build-on-startup: delete `index/` directory → restart SOC Memory → verify index is rebuilt
6. Update `README.md` with quickstart, architecture overview, and feature list
7. Update `AGENTS.md` §6 with any gotchas discovered during integration
