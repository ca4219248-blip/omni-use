"""Escalate toolset — when something legally needs a human, stop and ask.

Anything that requires human legal identity — KYC, bank accounts, contracts,
signatures, tax forms — must be escalated with escalate_to_operator(). The
task then pauses until the operator resolves it (Telegram /resolve, or
`python -m omniuse.operator resolve`).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def _telegram_send(text: str) -> str:
    token, chat = config.telegram_bot_token(), config.telegram_chat_id()
    if not token or not chat:
        return "Telegram not configured (set OMNIUSE_TELEGRAM_BOT_TOKEN / OMNIUSE_TELEGRAM_CHAT_ID)"
    data = urlencode({"chat_id": chat, "text": text}).encode()
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urlopen(req, timeout=30) as r:
            ok = json.loads(r.read()).get("ok")
        return "Telegram: delivered" if ok else "Telegram: delivery failed"
    except Exception as e:  # report, never crash the agent
        return f"Telegram: failed ({e})"


def escalate_to_operator(reason: str, task: str = "") -> str:
    _path().write_text(json.dumps(
        {"pending": True, "reason": reason, "task": task, "ts": time.time()}, indent=2))
    delivery = _telegram_send(
        "⚠️ OmniUse escalation\n"
        f"Task: {task or '(current task)'}\nReason: {reason}\n\n"
        "The agent is PAUSED. Resolve with /resolve (or "
        "`python -m omniuse.operator resolve`), or halt it with /stop.")
    return ("TASK PAUSED pending operator resolution. Do NOT attempt the escalated "
            f"action yourself. Check with escalate_status() before doing anything else. ({delivery})")


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
