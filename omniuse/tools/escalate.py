"""Escalate toolset — when something legally needs a human, stop and ask.

Anything that requires human legal identity — KYC, bank accounts, contracts,
signatures, tax forms — must be escalated with escalate_to_operator(). The
task then pauses until the operator resolves it (`python -m omniuse.operator
resolve` in the terminal, or /resolve in the console REPL).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from omniuse import config

HUMAN_MATTERS = (
    "KYC / identity verification",
    "opening or linking a bank account",
    "signing contracts or legal documents",
    "tax forms or government filings",
    "anything requiring a human's legal identity or signature",
)


def _path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "escalation.json"


def _read() -> dict:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else {"pending": False}


def is_pending() -> bool:
    return bool(_read().get("pending"))


def resolve(note: str = "resolved by operator") -> str:
    state = _read()
    state.update({"pending": False, "resolved_at": time.time(), "note": note})
    _path().write_text(json.dumps(state, indent=2))
    return "Escalation resolved — the agent may continue."


def _notify(reason: str, task: str) -> None:
    """Loud terminal banner + file — no external messaging service."""
    banner = ("\n" + "=" * 60 + "\n⚠️  OMNIUSE ESCALATION — OPERATOR NEEDED\n"
              f"Task: {task or '(current task)'}\nReason: {reason}\n"
              "The agent is PAUSED. Resolve with `python -m omniuse.operator resolve`\n"
              "(or /resolve in the console), or halt it with /stop.\n" + "=" * 60 + "\n")
    print(banner, file=sys.stderr, flush=True)
    try:                                    # also keep a notification file
        (_path().parent / "escalation-alert.txt").write_text(banner)
    except OSError:
        pass


def escalate_to_operator(reason: str, task: str = "") -> str:
    _path().write_text(json.dumps(
        {"pending": True, "reason": reason, "task": task, "ts": time.time()}, indent=2))
    _notify(reason, task)
    return ("TASK PAUSED pending operator resolution. Do NOT attempt the escalated "
            f"action yourself. Check with escalate_status() before doing anything else. "
            "(alert raised in the operator's terminal)")


def escalate_status() -> str:
    state = _read()
    if state.get("pending"):
        return (f"ESCALATION PENDING: {state.get('reason')} — the task stays "
                "paused until the operator resolves it.")
    return "No pending escalation — you may continue."


TOOLS = {
    "escalate_to_operator": (escalate_to_operator, {
        "type": "function",
        "function": {
            "name": "escalate_to_operator",
            "description": (
                "Pause the task and notify the operator — use for anything that "
                "legally requires a human: KYC, bank accounts, signatures, contracts, "
                "tax forms. Never attempt these yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "What human action is required and why"},
                    "task": {"type": "string", "description": "The task being paused"},
                },
                "required": ["reason"],
            },
        },
    }),
    "escalate_status": (escalate_status, {
        "type": "function",
        "function": {
            "name": "escalate_status",
            "description": "Check whether an unresolved operator escalation is still pending.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
}
