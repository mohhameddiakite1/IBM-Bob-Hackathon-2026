---
name: verify
description: Run syntax, type, lint, and functional checks to verify code changes before concluding a task.
---

# Verification Skill

Verify all created or modified files using deterministic checks ("sensors") before reporting a task as complete. Run every applicable check below based on the files changed and the tools available in the project.

## 1. Python Verification (If `.py` files were modified)
1. **Syntax & Bytecode Check (Always run):**
   `python -m py_compile <modified_file.py>`
2. **Import & Startup Sanity Check (Always run):**
   Import the modified module (e.g., `python -c "import <module>"`) to confirm there are no missing dependencies, circular imports, or top-level runtime errors.
3. **Linter & Type Checks (Run if installed in the environment):**
   - `ruff check <modified_file.py>`
   - `mypy <modified_file.py>`
4. **Automated Tests (Run if a test suite exists):**
   - If `pytest` is installed and tests exist (`tests/` or `test_*.py`), run `pytest` on relevant test files.

## 2. Frontend / JS Verification (If `.ts`, `.tsx`, `.js`, or `.jsx` files were modified)
1. **Type Check & Build (If `package.json` exists):**
   Run `npm run build` (or `npx tsc --noEmit`) to verify types and bundle compilation.
2. **Linter (If configured in `package.json`):**
   Run `npm run lint`.

## 3. Functional Smoke Check (For New Endpoints, Services, or Scripts)
- When adding or modifying an API endpoint, service function, or CLI script, execute a targeted smoke check (such as calling the function with sample inputs or hitting the local endpoint) to confirm expected behavior and error handling.

## 4. Failure Policy
- If any check fails, diagnose the root cause from the error output, fix the code properly, and re-run the failing check until it passes cleanly.
- Never suppress errors with broad `except: pass` blocks or `# type: ignore` comments unless strictly necessary and documented.
