"""Killswitch — one switch, zero activity.

The agent loop checks is_engaged() before EVERY tool call and halts
immediately if it is on. Engaging is open to anyone (including the agent
itself — halting is always safe). Disengaging is operator-only, via
`python -m omniuse.operator resume` (or `resume` in the console).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config

def _path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "killswitch.json"

def _read() -> dict:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else {"engaged": False}

def engage(reason: str = "") -> str:
    _path().write_text(json.dumps(
        {"engaged": True, "reason": reason, "ts": time.time()}, indent=2))
    return "KILLSWITCH ENGAGED — all agent activity halts immediately."

def disengage(reason: str = "operator resumed") -> str:
    _path().write_text(json.dumps(
        {"engaged": False, "reason": reason, "ts": time.time()}, indent=2))
    return "Killswitch disengaged — agent may resume."

def is_engaged() -> bool:
    return bool(_read().get("engaged"))

def killswitch_status() -> str:
    state = _read()
    if not state.get("engaged"):
        return "Killswitch: OFF (agent running normally)"
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.get("ts", 0)))
    return f"Killswitch: ON — reason: {state.get('reason') or 'unspecified'} (engaged {when})"


TOOLS = {
    "killswitch_engage": (engage, {
        "type": "function",
        "function": {
            "name": "killswitch_engage",
            "description": "Engage the killswitch to immediately halt ALL agent activity (e.g. if something looks wrong).",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    }),
    "killswitch_status": (killswitch_status, {
        "type": "function",
        "function": {
            "name": "killswitch_status",
            "description": "Check whether the operator killswitch is currently engaged.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
}
