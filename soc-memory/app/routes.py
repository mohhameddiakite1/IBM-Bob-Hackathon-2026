"""Flask blueprint for SOC Memory — GET /, POST /search, POST /remember."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from app.drafter import draft_note
from app.matcher import load_all_cases, rank_cases

bp = Blueprint("main", __name__)

_DEMO_PATH = Path(__file__).parent.parent / "demo_alerts.json"
_ADDITIONS_PATH = Path(__file__).parent / "data" / "additions.json"

with open(_DEMO_PATH, encoding="utf-8") as _fh:
    _DEMO_ALERTS: list[dict] = json.load(_fh)

SOURCES = ["Vectra", "Microsoft Sentinel", "Google SecOps", "Darktrace"]

# Reference date for notice expiry filtering
_TODAY = date(2026, 11, 24)


# ---------------------------------------------------------------------------
# Notice helpers
# ---------------------------------------------------------------------------
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _collect_alert_entities(form: dict) -> set[str]:
    """Return the set of entity values to match against notices (case-insensitive)."""
    entities: set[str] = set()
    host = (form.get("host") or "").strip().lower()
    account = (form.get("account") or "").strip().lower()
    if host:
        entities.add(host)
    if account:
        entities.add(account)
    # Extract any IPv4 addresses from title + description
    combined = f"{form.get('title', '')} {form.get('description', '')}"
    for ip in _IPV4_RE.findall(combined):
        entities.add(ip)
    return entities


def _filter_notices(notices: list[dict], alert_entities: set[str]) -> list[dict]:
    """Return non-expired notices whose entity matches the alert entities."""
    matched: list[dict] = []
    for notice in notices:
        # Expiry check: expired means expires < today
        expires_str = notice.get("expires")
        if expires_str is not None:
            try:
                exp = date.fromisoformat(expires_str)
                if exp < _TODAY:
                    continue
            except ValueError:
                pass
        # Entity match (case-insensitive)
        if notice["entity"].lower() in alert_entities:
            matched.append(notice)
    return matched


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@bp.route("/", methods=["GET"])
def index() -> str:
    """Render the empty alert input form."""
    return render_template(
        "index.html",
        sources=SOURCES,
        form={},
        results=None,
        draft=None,
        notices=[],
        error=None,
    )


@bp.route("/search", methods=["POST"])
def search() -> str:
    """Accept form fields, run matching, return results on the same page."""
    form = {
        "title": request.form.get("title", "").strip(),
        "source": request.form.get("source", "").strip(),
        "host": request.form.get("host", "").strip(),
        "account": request.form.get("account", "").strip(),
        "description": request.form.get("description", "").strip(),
    }

    if not form["title"] and not form["description"]:
        return render_template(
            "index.html",
            sources=SOURCES,
            form=form,
            results=None,
            draft=None,
            notices=[],
            error="Please enter at least a title or description.",
        )

    try:
        cases = current_app.config["CASES"]
        results = rank_cases(form, cases, top_n=3)
        draft = draft_note(results)
        all_notices: list[dict] = current_app.config.get("NOTICES", [])
        entities = _collect_alert_entities(form)
        notices = _filter_notices(all_notices, entities)
    except Exception as exc:  # noqa: BLE001
        return render_template(
            "index.html",
            sources=SOURCES,
            form=form,
            results=None,
            draft=None,
            notices=[],
            error=f"An error occurred while processing the alert: {exc}",
        )

    return render_template(
        "index.html",
        sources=SOURCES,
        form=form,
        results=results,
        draft=draft,
        notices=notices,
        error=None,
    )


@bp.route("/demo/<int:idx>")
def demo_alert(idx: int) -> str:
    """Prefill the form with one of the demo alerts (1-indexed)."""
    if idx < 1 or idx > len(_DEMO_ALERTS):
        return render_template(
            "index.html",
            sources=SOURCES,
            form={},
            results=None,
            draft=None,
            notices=[],
            error=f"No demo alert #{idx}.",
        )
    alert = _DEMO_ALERTS[idx - 1]
    return render_template(
        "index.html",
        sources=SOURCES,
        form=alert,
        results=None,
        draft=None,
        notices=[],
        error=None,
        prefill=True,
    )


@bp.route("/remember", methods=["POST"])
def remember() -> str:
    """Append the current alert + verdict to additions.json and return JSON confirmation."""
    data = request.get_json(force=True, silent=True) or {}

    # Load existing additions
    if _ADDITIONS_PATH.exists():
        with open(_ADDITIONS_PATH, encoding="utf-8") as fh:
            additions: list[dict] = json.load(fh)
    else:
        additions = []

    # Determine next SOC id from base cases + additions
    all_cases = load_all_cases()
    max_num = 0
    for c in all_cases:
        m = re.match(r"SOC-(\d+)", c.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))
    new_id = f"SOC-{max_num + 1}"

    today_str = date.today().isoformat()

    new_case: dict = {
        "id": new_id,
        "title": data.get("title", ""),
        "source": data.get("source", ""),
        "host": data.get("host", ""),
        "account": data.get("account", ""),
        "description": data.get("description", ""),
        "verdict": data.get("verdict", "CLOSE"),
        "analyst": data.get("analyst", ""),
        "date": today_str,
        "client_confirmed": False,
        "justification": "Added from the live workflow.",
        "note": data.get("note", ""),
        "team_notes": "",
    }

    additions.append(new_case)

    with open(_ADDITIONS_PATH, "w", encoding="utf-8") as fh:
        json.dump(additions, fh, indent=2, ensure_ascii=False)

    # Reload cases into app config so the new case is searchable immediately
    current_app.config["CASES"] = load_all_cases()

    return jsonify({"saved_as": new_id})
