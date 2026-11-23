---
name: checkpoint
description: Save session state, decisions, and next steps to PROGRESS.md before starting a new conversation. Use only when explicitly asked to save progress or checkpoint.
---

Create or overwrite `PROGRESS.md` in the workspace root (max 60 lines) with these sections:

1. **Objective:** What we are working on, one or two lines.
2. **Done:** Completed work with file names. Mark each item `VERIFIED` or `UNVERIFIED`.
3. **Decisions:** Constraints and choices already settled.
4. **Next Steps:** Ordered checklist; the first item must be actionable immediately.
5. **Blockers:** Open questions, known bugs, or pending revisions.

## Rules
- Reference files and sections; do not paste code blocks longer than 5 lines.
- If `PROGRESS.md` already exists, keep still-relevant items and drop obsolete ones.
- If a step fails twice, stop and report. Do not retry further.

Finish by confirming the save and giving the user a short prompt to paste into a new conversation (e.g., `Read @AGENTS.md and @PROGRESS.md and continue with the first Next Step.`).
