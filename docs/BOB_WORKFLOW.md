# IBM Bob Team Workflow & Skills Guide

This repo is pre-configured with project rules (`AGENTS.md`) and custom skills (`.bob/skills/`) to keep IBM Bob accurate, fast, and aligned across macOS, Windows, and Linux.

---

## 1. Available Skills & When to Use Them

| Skill | When to Use | Example Prompt |
| :--- | :--- | :--- |
| **`grill-me`** | **Before coding** — stress-test an idea, clarify architecture, and resolve design decisions one question at a time. | *"Use the `grill-me` skill to help me design the backend and data flow for [feature/idea]."* |
| **`verify`** | **After coding** — runs syntax, import, lint, and smoke checks automatically (Bob also triggers this via `AGENTS.md`). | *"Use the `verify` skill to check the files we just modified."* |
| **`checkpoint`** | **Before starting a new chat** — saves progress, decisions, and next steps into `PROGRESS.md` (local, git-ignored). | *"Use the `checkpoint` skill to save our progress."* |
| **`pitch-readme`** | **Before wrapping up** — audits the actual codebase to generate `README.md` and `PITCH.md`. | *"Use the `pitch-readme` skill to generate README.md and PITCH.md."* |

---

## 2. Three Habits for Best Results in IBM Bob

1. **Start New Conversations Often:** Long chats degrade Bob's accuracy and burn extra tokens. Finish one feature or task, run `checkpoint`, and open a **fresh chat**.
2. **Resume via `@PROGRESS.md` & `@`-Mentions:** In a new chat, point Bob directly to the files it needs:
   > *"Read `@PROGRESS.md` and `@backend/main.py`, then implement the next step."*
3. **Edit Your Prompt Instead of Arguing:** If Bob misunderstands a request, roll back and edit your earlier message rather than debating in follow-up replies.

---

## 3. Repository Rules & Guardrails
- **`AGENTS.md` (Auto-Loaded):** Enforces Python type hints, modular structure, `pathlib.Path` + `utf-8` file handling, and secret safety. Add any tricky framework gotchas you discover to Section 6.
- **Secrets:** Never put API keys in code. Use `.env` locally (ignored by Git and `.bobignore`).
