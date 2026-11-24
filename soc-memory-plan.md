# SOC Memory — Plan

## Top-Level Overview

**Goal:** A one-page Flask web app that lets a SOC analyst paste a new alert, finds the most similar past resolved cases from a local dataset, and drafts a closing note or escalation justification grounded only in those precedents. No external APIs, no API keys, no ML libraries — the similarity engine uses weighted token-overlap (Jaccard) with match reasons displayed so ranking is fully explainable.

**Scope:** One workflow end-to-end: alert input → ranked precedents → drafted note. Fourteen synthetic past cases, two demo alerts. pytest suite that verifies the ranking on those demo alerts.

**Non-goals:** Authentication, persistence, real client data, LLM integration, any package beyond Flask and pytest.

---

## File Structure

```
soc-memory/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes.py            # Single POST route + index GET
│   ├── matcher.py           # Weighted token-overlap engine
│   ├── drafter.py           # Closing/escalation note template engine
│   └── data/
│       └── cases.json       # 14 synthetic past resolved cases
├── templates/
│   └── index.html           # Single-page UI (Jinja2, no JS framework)
├── static/
│   └── style.css            # Minimal responsive stylesheet
├── tests/
│   ├── __init__.py
│   ├── test_matcher.py      # Unit tests for similarity scoring + ranking
│   ├── test_drafter.py      # Unit tests for draft note generation
│   └── test_routes.py       # Integration tests for Flask routes
├── demo_alerts.json         # Two demo alerts with expected ranking metadata
├── requirements.txt         # flask, pytest (no others)
├── run.py                   # Entry point: `python run.py`
└── README.md                (update existing)
```

---

## Data Model

### Past Case (cases.json record)
```
{
  "id": "CASE-001",
  "title": "...",
  "host": "...",
  "account": "...",
  "description": "...",
  "verdict": "closed" | "escalated",
  "justification": "...",
  "client_confirmed": true | false,
  "note": "..."
}
```

### Incoming Alert (form fields)
- `title` (str)
- `host` (str)
- `account` (str)
- `description` (str)

### Scored Precedent (returned by matcher)
- All case fields, plus:
  - `score` (float, 0–1)
  - `match_reasons` (list[str])  — human-readable explanation per field

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold

**Intent:** Create the directory layout, empty placeholder files, `requirements.txt`, and `run.py` so every subsequent sub-task has a stable home.

**Expected Outcomes:**
- All directories and placeholder files exist.
- `python run.py` starts Flask (even with no routes returning content yet).
- `pytest` can discover the `tests/` package.

**Todo List:**
1. Create `soc-memory/` directory tree as specified above.
2. Write `requirements.txt` with `flask` and `pytest`.
3. Write `run.py` that calls `app.create_app()` and runs in debug mode on port 5000.
4. Write `app/__init__.py` with a minimal `create_app()` factory.
5. Write `tests/__init__.py` (empty).

**Relevant Context:** `pathlib.Path` must be used for all path construction (AGENTS.md §3). `encoding="utf-8"` on all file I/O.

**Status:** [ ] pending

---

### Sub-Task 2 — Sample Dataset (cases.json + demo_alerts.json)

**Intent:** Populate the authoritative dataset with 14 synthetic past cases and 2 demo alerts. This data is the ground truth for all tests — it must be defined before the matcher is written so the expected rankings are known.

> **NOTE:** The exact 14 cases and 2 demo alerts with their expected rankings will be provided by the user before this sub-task is implemented. Do not invent the data — wait for the user's specification.

**Expected Outcomes:**
- `app/data/cases.json` contains exactly 14 records conforming to the data model.
- `demo_alerts.json` contains 2 alert objects, each with an `expected_top3` list of case IDs in ranked order.
- Both files are valid JSON and load without error.

**Todo List:**
1. Receive the user-specified cases and demo alerts.
2. Write `app/data/cases.json` with the 14 synthetic cases.
3. Write `demo_alerts.json` with the 2 demo alerts and their `expected_top3` annotation.

**Relevant Context:** `encoding="utf-8"` on all JSON reads. No real client data.

**Status:** [ ] pending

---

### Sub-Task 3 — Matching Engine (`matcher.py`)

**Intent:** Implement the weighted token-overlap similarity engine that scores every past case against an incoming alert and returns the top-N results with match reasons. This is the core intelligence of the app — it must be pure Python stdlib, deterministic, and explainable.

**Expected Outcomes:**
- `score_case(alert, case)` returns a `ScoredCase` with a float score and a list of `match_reasons` strings.
- `rank_cases(alert, cases, top_n)` returns the top-N cases sorted descending by score.
- Scores are reproducible — same input always produces the same output.
- Match reasons clearly state which field matched and which tokens overlapped.

**Matching Algorithm — Weighted Jaccard:**

For each of the four fields:

| Field       | Weight |
|-------------|--------|
| title       | 0.40   |
| description | 0.35   |
| host        | 0.15   |
| account     | 0.10   |

Field score = Jaccard similarity of token sets (intersection / union).  
Total score = sum of (weight × field_score) across all four fields.

**Tokenization (stdlib only):**
- Lowercase the string.
- Split on whitespace and punctuation (`re.split(r'[\s\W]+', text)`).
- Drop empty strings and tokens of length < 2.
- Drop a small hardcoded stopword set: `{"the", "a", "an", "in", "on", "at", "to", "is", "was", "and", "or", "of", "for", "by", "with", "from", "this", "that", "it"}`.

**Match Reasons format (one string per field that contributed > 0):**
```
"title: matched [brute, force, login] (score 0.43)"
"host: matched [web01] (score 1.00)"
```

**Todo List:**
1. Implement `tokenize(text: str) -> set[str]` in `matcher.py`.
2. Implement `jaccard(a: set[str], b: set[str]) -> float`.
3. Implement `score_case(alert: dict, case: dict) -> ScoredCase` using the weight table above.
4. Implement `rank_cases(alert: dict, cases: list[dict], top_n: int = 5) -> list[ScoredCase]`.
5. Define `ScoredCase` as a dataclass with all case fields plus `score` and `match_reasons`.

**Relevant Context:** No third-party packages. All logic lives in `app/matcher.py`. Data loaded from `app/data/cases.json` by the route layer, not by the matcher (keep the matcher pure/testable).

**Status:** [ ] pending

---

### Sub-Task 4 — Note Drafting Engine (`drafter.py`)

**Intent:** Given the top-N ranked precedents, produce a draft closing note or escalation justification using a deterministic template. No LLM, no external call. The draft cites case numbers, states the majority verdict, quotes the most-relevant justification, and flags client confirmation status.

**Expected Outcomes:**
- `draft_note(alert: dict, precedents: list[ScoredCase]) -> str` returns a non-empty string.
- When the majority verdict in `precedents` is `"closed"`, the draft is a closing note.
- When the majority verdict is `"escalated"`, the draft is an escalation justification.
- The draft includes: the alert title, the case IDs of the precedents cited, the majority verdict, the top precedent's justification (verbatim), and whether the client confirmed the top precedent.
- Ties in verdict count → default to `"escalated"` (conservative).

**Template — Closing:**
```
Recommended action: CLOSE

Based on {N} similar past cases ({case_ids}), this alert matches a known pattern.
Closest precedent: [{top_id}] — "{top_justification}"
Client confirmed: {yes/no}.

Draft note: This alert was reviewed against precedent {top_id}. The activity is consistent
with previously approved behaviour. Recommend closing without escalation.
```

**Template — Escalation:**
```
Recommended action: ESCALATE

Based on {N} similar past cases ({case_ids}), this alert may require escalation.
Closest precedent: [{top_id}] — "{top_justification}"
Client confirmed: {yes/no}.

Draft note: This alert was reviewed against precedent {top_id}. The activity could not be
ruled out as malicious based on available context. Recommend escalation to Tier 2.
```

**Todo List:**
1. Implement `draft_note(alert: dict, precedents: list[ScoredCase]) -> str` in `drafter.py`.
2. Determine majority verdict using a simple counter.
3. Build the appropriate template string with field substitution (no f-string tricks that break on special characters — use `str.format()` with `.replace()`-safe values).
4. Return the draft string.

**Relevant Context:** `drafter.py` only imports from `app/matcher.py` (the `ScoredCase` type). No Flask imports.

**Status:** [ ] pending

---

### Sub-Task 5 — Flask Routes (`routes.py`)

**Intent:** Wire the matcher and drafter to a single Flask blueprint with two endpoints: `GET /` (render the form) and `POST /search` (run the search, return results to the same page).

**Expected Outcomes:**
- `GET /` renders `index.html` with an empty form.
- `POST /search` accepts form fields, calls `rank_cases`, calls `draft_note`, and re-renders `index.html` with results injected.
- Errors (empty form, JSON load failure) show a user-friendly message on the page — no raw tracebacks.
- Cases loaded once at app startup and stored on `app.config["CASES"]`.

**Todo List:**
1. Write `load_cases() -> list[dict]` in `routes.py` (or `app/__init__.py`) using `pathlib.Path` and `encoding="utf-8"`.
2. Register a Flask blueprint in `routes.py` with `GET /` and `POST /search`.
3. `POST /search`: validate that at least `title` or `description` is non-empty; call `rank_cases` (top_n=5); call `draft_note`; pass results to template.
4. Register the blueprint in `create_app()`.
5. Store cases on `app.config["CASES"]` during `create_app()`.

**Relevant Context:** Graceful error handling per AGENTS.md §2. No raw stack traces to the browser.

**Status:** [ ] pending

---

### Sub-Task 6 — Single-Page UI (`index.html` + `style.css`)

**Intent:** Build the one-page interface with three zones: alert input form, ranked precedents panel, and drafted note panel. Must be responsive and readable without a JS framework.

**Expected Outcomes:**
- Alert form has four fields: Title, Host, Account, Description, plus a Search button.
- Precedents panel shows up to 5 cards, each with: case ID, verdict badge (colour-coded), score (%), match reasons, justification, client confirmed, and the original note.
- Draft panel shows the generated note in an editable `<textarea>` with a "Copy to clipboard" button (vanilla JS, one line).
- Layout is usable on a 1280px screen and degrades gracefully to 768px.
- No external CDN dependencies (pure CSS, no Bootstrap, no Tailwind fetch).

**Todo List:**
1. Write `templates/index.html` with Jinja2 blocks for the three zones.
2. Render precedents conditionally (only if `results` is passed from the route).
3. Render the draft note in a `<textarea>` (only if `draft` is passed).
4. Add a one-line `<script>` for the copy button (no external JS).
5. Write `static/style.css` with a card layout, verdict badge colours (green = closed, amber = escalated), and responsive flex/grid.

**Relevant Context:** Jinja2 is bundled with Flask — no extra install. AGENTS.md §5: clean, responsive UI.

**Status:** [ ] pending

---

### Sub-Task 7 — Test Suite (`tests/`)

**Intent:** Write pytest tests that verify the matcher's scoring logic, the drafter's template selection, and the Flask routes. The demo-alert ranking tests are the acceptance criteria for the whole app.

**Expected Outcomes:**
- `test_matcher.py`: unit tests for `tokenize`, `jaccard`, `score_case`, and `rank_cases` on the demo alerts — asserts that `expected_top3` case IDs appear in the correct order.
- `test_drafter.py`: unit tests that a closed-majority precedent set produces a closing draft, an escalated-majority set produces an escalation draft, and a tie defaults to escalation.
- `test_routes.py`: integration tests that `GET /` returns 200, `POST /search` with a valid alert returns 200 and contains expected case IDs in the response body, and `POST /search` with an empty form returns a user-friendly error.
- All tests pass with `pytest` from the repo root.

**Todo List:**
1. Write `tests/test_matcher.py` with unit tests for each public function.
2. Add two parametrized tests that load `demo_alerts.json` and assert the top-3 ranking.
3. Write `tests/test_drafter.py` with closed, escalated, and tie scenarios using synthetic precedent lists.
4. Write `tests/test_routes.py` using Flask's test client (`app.test_client()`).
5. Confirm `pytest` runs green from the repo root.

**Relevant Context:** `demo_alerts.json` and `app/data/cases.json` must exist (Sub-Task 2) before these tests can pass. Test the matcher in isolation — pass dicts directly, do not hit the file system in unit tests.

**Status:** [ ] pending

---

## Build Order

```
Sub-Task 1 → Sub-Task 2 → Sub-Task 3 → Sub-Task 4 → Sub-Task 5 → Sub-Task 6 → Sub-Task 7
  Scaffold      Dataset      Matcher      Drafter       Routes         UI           Tests
```

Sub-Tasks 3 and 4 are independent of each other once the data model is known — they can be reviewed separately but should both be done before Sub-Task 5.

---

## Matching Approach — Summary

- Pure Python stdlib (`re`, `collections`, `dataclasses`).
- Four weighted fields; weights sum to 1.0.
- Jaccard similarity per field (intersection over union of token sets).
- Stopword list hardcoded (19 tokens) — no file, no external resource.
- Match reasons list tells the analyst *why* each case ranked, not just *how much*.
- Deterministic: no randomness, no ML, no embeddings.

---

## Note-Drafting Rules — Summary

- Count verdicts across top-N precedents.
- Majority verdict selects the template.
- Tie → escalate (conservative default).
- Draft cites: all precedent case IDs, top precedent's justification verbatim, client confirmation of top precedent.
- Draft is editable by the analyst before copying — the app proposes, the human decides.
- No LLM, no external call, no API key.
