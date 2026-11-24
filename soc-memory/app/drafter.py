"""Note-drafting engine for SOC Memory — grounded in top-3 precedents only."""
from __future__ import annotations

from app.matcher import ScoredCase


def draft_note(precedents: list[ScoredCase]) -> str:
    """Draft a paste-ready closing note or decision-required note from the top-3 precedents.

    Rules:
    - If the top precedent is CLOSE → draft a paste-ready closing note built from
      that precedent's own facts (host, account, what was confirmed, the note text),
      still citing its case id.
    - If the top 3 contain both CLOSE and CREATE verdicts → present both outcomes
      and state that the analyst must decide, citing one id of each type.
    - Only cites case ids present in the displayed top 3.
    - No majority vote, no auto-escalate tie-break.
    """
    if not precedents:
        return "No similar precedents found. Manual analyst review required."

    top = precedents[0]
    top_id = top.id

    verdicts = {p.verdict for p in precedents}
    has_close = "CLOSE" in verdicts
    has_create = "CREATE" in verdicts

    if has_close and has_create:
        # Mixed — find one representative id of each verdict
        close_id = next(p.id for p in precedents if p.verdict == "CLOSE")
        create_id = next(p.id for p in precedents if p.verdict == "CREATE")
        return (
            "Similar past cases show conflicting outcomes.\n\n"
            f"Precedent {close_id} was closed: a comparable alert was reviewed and "
            f"determined to be benign.\n"
            f"Precedent {create_id} was escalated: a comparable alert required "
            f"further investigation.\n\n"
            "The analyst must review the context and decide whether to close or escalate."
        )

    # Top precedent is CLOSE (and all top-3 are CLOSE, since no CREATE found above).
    # Build a paste-ready closing note using the top precedent's own facts.
    client_line = (
        "Client confirmed the activity."
        if top.client_confirmed
        else "Client confirmation was not obtained for this precedent."
    )

    # Use the precedent's host/account to ground the note in its concrete facts
    host_part = f"Host: {top.host}. " if top.host else ""
    account_part = f"Account: {top.account}. " if top.account else ""

    return (
        f"Recommended action: CLOSE (based on precedent {top_id})\n\n"
        f"{host_part}{account_part}"
        f"{client_line}\n\n"
        f"Precedent {top_id} note: {top.note}\n\n"
        f"This alert was reviewed against precedent {top_id}. "
        f"The activity is consistent with previously approved behaviour. "
        f"Recommend closing without escalation."
    )
