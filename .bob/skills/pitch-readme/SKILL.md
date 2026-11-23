---
name: pitch-readme
description: Inspect the codebase to generate or update a clear, accurate README.md and a structured PITCH.md product walkthrough.
---

# Documentation & Product Walkthrough Generator

Audit the actual files, dependencies, and entrypoints in this repository to generate accurate documentation and a live product walkthrough grounded strictly in implemented functionality.

## Step 1: Audit the Codebase
Before writing anything, inspect the repository to verify:
- **Dependencies:** `requirements.txt`, `pyproject.toml`, or `package.json`.
- **Architecture & Entrypoints:** Main application files, API routes, services, and UI views that are actually wired up and working.
- **Configuration:** Environment variables referenced in the code (`os.getenv`, `process.env`) and default ports.

## Step 2: Generate or Update `README.md`
Create or update `README.md` in the repository root using clean, scannable Markdown:
- **Project Name & Overview:** Concise summary of what the application does and the problem it solves.
- **Key Features:** Bulleted list of capabilities verified in the codebase.
- **Architecture & Tech Stack:** Clear breakdown of system components, data flow, and core technologies.
- **Prerequisites & Quick Start:** Exact installation, environment variable setup (listing variable names without real secrets), and startup commands for both macOS/Linux and Windows.
- **Project Structure:** Clean directory tree highlighting key modules.

## Step 3: Generate or Update `PITCH.md`
Create or update `PITCH.md` in the repository root with a structured, ~2-minute live product walkthrough tailored for technical evaluators or stakeholders:
- **Problem & Value Proposition:** Brief context on the user need and how the application addresses it.
- **Architecture Highlight:** Concise explanation of how the system works under the hood.
- **Step-by-Step Demo Flow:** Exact sequence of user actions, inputs, and expected outputs to showcase the core capabilities smoothly.
- **Key Technical Decisions & Roadmap:** Notable engineering choices made in the current build and logical next enhancements.
