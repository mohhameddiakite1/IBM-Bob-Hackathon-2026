# PITCH.md — SOC Memory: 2-Minute Live Walkthrough

## Problem & Value Proposition

Security Operations Center analysts are drowning in alert noise. When a critical incident arrives, an analyst must manually recall whether a similar attack was seen before, what IOCs it shared, and how it was resolved — all while the clock is ticking.

**SOC Memory** solves this with a pull-based, offline-first investigation assistant. An analyst selects (or pastes) an open ticket and instantly receives:

- The **top 10 historically similar incidents** ranked by semantic similarity.
- **Shared IOCs** (IP addresses, domains, URLs, file hashes) that connect the current alert to past cases.
- **Top 3 resolution playbooks** surfaced from closed matching cases.
- **Near-duplicate flags** (cosine ≥ 0.92) so the analyst knows immediately whether this is a repeated alert.

No LLM. No hallucinations. No internet required. All answers are grounded in the organization's own incident history.

---

## Architecture Highlight

Two Flask services, **strictly decoupled** via HTTP REST.

```
  Analyst Browser
       │
       ├─── :5000 ──► SOC Memory (soc_memory/)
       │                │  loads index/ on startup
       │                │  REST GET /api/tickets  ──────────────────────►  Jira Simulator
       │                │  REST GET /api/tickets/<id> ─────────────────►  (jira_simulator/)
       │                                                                   :5001  SQLite DB
       └─── :5001 ──► Jira Simulator (HTML CRUD UI)
```

Under the hood:

1. **`seed.py`** loads `data/seed_incidents.json` (50 incidents, 8 archetypes), runs regex IOC extraction, and embeds every incident via `all-MiniLM-L6-v2` → `index/vectors.npy` (shape `(50, 384)`).
2. **`soc_memory/app.py`** loads `index/` on startup and attaches `DeterministicSummarizer` to `app.config`.
3. **`POST /analyze`** in `routes.py` embeds the query, runs NumPy cosine similarity, and feeds the top-10 matches to the synthesizer.
4. **`DeterministicSummarizer`** extracts shared IOCs, deduplicates resolutions, and flags duplicates — zero LLM needed.
5. **`JiraSimulatorConnector`** calls `GET /api/tickets` and `GET /api/tickets/<id>` on the Jira Simulator; swapping to real Jira Cloud requires changing only this class.

---

## Step-by-Step Demo Flow

### Setup (run once)

```bash
# Terminal 1 — build the vector index
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe seed.py
# Output: [index] Index built — shape (50, 384)

# Terminal 2 — start Jira Simulator
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe run_jira.py
# → http://localhost:5001  (5 sample tickets auto-seeded)

# Terminal 3 — start SOC Memory
C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe run_soc.py
# → http://localhost:5000
```

### Live Demo Sequence

**Step 1 — Open the analyst home**
Navigate to `http://localhost:5000`. The page shows a free-text analysis box and a live dropdown populated with open tickets from the Jira Simulator.

**Step 2 — Paste free text**
Paste: `Outbound connection from 198.51.100.23 on port 4444, process tree shows powershell spawning cmd.`

Click **Analyse**.

**Expected results page:**
- Top match: *"Ransomware detected on workstation WIN-07"* — cosine ~0.91
- Shared IOC: `198.51.100.23` (IPv4)
- Resolution playbook: "Isolate endpoint, snapshot memory, restore from clean backup."
- Near-duplicate flag if score ≥ 0.92.

**Step 3 — Load a Jira ticket**
Select *"Phishing email targeting finance department"* from the dropdown.
Click **Analyse**.

Results highlight shared domain IOCs (e.g., `login.corp-portal.example`) with their historical matches.

**Step 4 — View incident detail**
Click any matched incident ID (e.g., `INC-012`) to view the full historical record: description, IOCs, tags, resolution notes.

**Step 5 — Health check**
`GET http://localhost:5000/health` returns:
```json
{ "status": "ok", "index_size": 50, "jira_reachable": true }
```

**Step 6 — Jira Simulator CRUD**
Navigate to `http://localhost:5001`, create a new ticket (title, description, severity, IOC strings), and it immediately appears in SOC Memory's dropdown.

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| **Pull model, not push** | Analyst-driven on demand; no background workers or race conditions |
| **Deterministic synthesis, not LLM** | Zero hallucination risk; grounded exclusively in historical data |
| **`Summarizer` Protocol** | Pluggable interface: swap `DeterministicSummarizer` for `WatsonxSummarizer` with one line in `app.py` |
| **NumPy cosine similarity** | Cross-platform, no FAISS wheel dependency; sufficient for 50–50 k incidents |
| **Pydantic v2 `Incident` model** | Type-safe data flow from seed → index → synthesis → templates |
| **HTTP REST boundary** | `jira_simulator` connector is entirely swappable for real Jira Cloud or ServiceNow |

---

## Logical Next Enhancements

1. **IBM watsonx.ai synthesis** — `WatsonxSummarizer` satisfying the `Summarizer` protocol; controlled via `USE_WATSONX=1` env flag.
2. **Live threat-intel enrichment** — abuse.ch/URLhaus API called on IOC ingestion for automatic reputation scoring.
3. **Real Jira Cloud connector** — OAuth 2.0 Jira Cloud client behind the same `JiraSimulatorConnector` interface.
4. **Live index updates** — `POST /api/ingest` to append new resolved incidents without a full `seed.py` rebuild.
5. **Pagination** — `?page=` / `?per_page=` on all list endpoints.
