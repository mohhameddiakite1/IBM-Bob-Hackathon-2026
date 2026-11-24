# AGENTS.md — SOC Memory Project Guidelines

## 1. Project Overview
- **Goal:** Build **SOC Memory**, an intelligent historical incident retrieval and investigation assistant for Security Operations Center (SOC) analysts, paired with a standalone **Jira Simulator** ticketing service.
- **System Architecture (Strict Decoupling):**
  - **`soc_memory/` (Main Application):** Handles incident ingestion, indicator extraction (IOCs), historical similarity search, and investigation recommendations.
  - **`jira_simulator/` (Standalone Ticketing App):** Independent application with its own database, UI, and REST API simulating a ticketing platform.
  - **Integration Boundary:** `soc_memory` MUST communicate with `jira_simulator` **exclusively via its REST API** (never by importing its modules or reading its database directly), keeping the connector swappable for real Jira/ticketing APIs.
- **Primary Stack:** Python 3.11+ with modular backend/UI components.
- **Environments:** Cross-platform team working across **macOS, Windows, and Linux** in **VS Code** and **IBM Bob**.

## 2. Core Coding Standards (Python)
- **Type Hints & Clarity:** Use Python type annotations (`list[str]`, `dict[str, Any]`) on all function signatures.
- **Modular Architecture:** Maintain clean separation of concerns between ticketing connectors, IOC/similarity retrieval logic, data models, API routes, and UI components.
- **Graceful Error Handling:** Wrap all external API calls (`jira_simulator` REST calls, threat intel/public APIs such as abuse.ch/URLhaus, LLM endpoints) in `try/except` blocks with clear, actionable error handling—never expose raw stack traces.
- **Concise Docstrings:** Add clear one-line docstrings to public functions and modules.

## 3. Cross-Platform Rules (macOS, Windows, Linux)
- **File Paths:** ALWAYS use `pathlib.Path` instead of hardcoded `/` or `\` strings.
- **Encoding:** Always specify `encoding="utf-8"` when reading or writing files (`open(..., encoding="utf-8")`).
- **Shell Commands:** Provide cross-platform commands or explicitly label OS-specific ones (`source .venv/bin/activate` on macOS/Linux vs. `.venv\Scripts\activate` on Windows).

## 4. Security & Secrets Hygiene
- **Never Hardcode Secrets:** Never write API keys, tokens, or passwords in code. Load all credentials via `os.getenv()` or `python-dotenv` from `.env`.
- **Ignore Sensitive Files:** Do not read, print, or commit `.env`, `credentials.json`, or `.bob/mcp.json`.

## 5. Dependency & UI Standards
- **Track Dependencies:** Whenever you install or import a new Python package, immediately record it in `requirements.txt` (or `pyproject.toml`).
- **Clean, Responsive UI:** Keep both the SOC Memory analyst view and the Jira Simulator ticket interface well-structured, responsive, and intuitive.

## 6. Agent Behavior & Verification (Use `verify` Skill)
- **Outline First:** Briefly list the files you plan to create or modify before making multi-file edits.
- **Preserve Working Code:** Do not delete or rewrite unrelated working features when fixing a bug.
- **Run Verification Checks:** Use the `verify` skill after code changes to confirm files compile, import cleanly, and pass functional checks before finishing.
- **Document Gotchas Here:** Record any non-obvious framework behaviors, API quirks, or environment constraints discovered during development below so they are never repeated.

### Known Gotchas

| # | Gotcha | Fix |
|---|--------|-----|
| 1 | **Windows Conda interpreter** — `execute_command` runs in a non-activated subshell; `conda run` and bare `python` both fail with `ModuleNotFoundError`. | Always invoke the bobpyenv interpreter directly: `C:\ProgramData\Anaconda3\envs\bobpyenv\python.exe` (use this exact path for all `python -c`, `-m pip`, `-m pytest`, and script invocations). |
