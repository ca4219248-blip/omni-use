"""Permission system — not every tool should run blind.

Three levels per tool (optionally gated on an argument pattern):
  allow    → run it
  confirm  → needs operator approval (interactive prompt, or
             `python -m omniuse.operator approve <tool>` / `approve <tool>`
             in the console)
  deny     → never runs

Rules live in data/permissions.json and are editable at any time — the
agent re-reads them before every check. Approvals persist until revoked.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from omniuse import config

LEVELS = ("allow", "confirm", "deny")

# Shipped defaults (the operator can edit data/permissions.json freely).
DEFAULT_RULES = [
    # payments need a human in the loop
    {"tool": "wallet_send", "level": "confirm"},
    # the agent must never raise its own spend limit
    {"tool": "wallet_raise_limit", "level": "deny"},
    # arbitrary shell on the phone needs a human
    {"tool": "mobile_shell", "level": "confirm"},
    # running tools on OTHER machines needs a human
    {"tool": "remote_run", "level": "confirm"},
    # destructive shell commands need a human
    {"tool": "system_run", "pattern": r"rm\s+-rf|mkfs|dd\s+if=|>\s*/dev/sd|shutdown|reboot|halt|:\(\)\s*\{", "level": "confirm"},
    # shop: only the operator (or a verified bank SMS) may mark an order paid
    {"tool": "order_mark_paid", "level": "deny"},
]

_extra_rules: list[dict] = []      # registered by the plugin loader
_session_approved: set[str] = set()


def _data_path(name: str) -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _rules() -> list[dict]:
    p = _data_path("permissions.json")
    if not p.exists():
        p.write_text(json.dumps({"rules": DEFAULT_RULES}, indent=2), encoding="utf-8")
    try:
        return json.loads(p.read_text()).get("rules", [])
    except json.JSONDecodeError:
        return DEFAULT_RULES


def register_rules(rules: list[dict]) -> None:
    """Plugins can add rules (e.g. their own confirm-gated tools)."""
    _extra_rules.extend(rules)


def check(tool: str, arguments: dict | None = None) -> str:
    """Most restrictive matching rule wins; default is 'allow'."""
    level = "allow"
    for rule in list(_rules()) + _extra_rules:
        if rule.get("tool") != tool or rule.get("level") not in LEVELS:
            continue
        pattern = rule.get("pattern")
        if pattern and arguments is not None:
            if not re.search(pattern, json.dumps(arguments)):
                continue
        if rule["level"] == "deny":
            return "deny"
        if rule["level"] == "confirm":
            level = "confirm"
    return level

# ---------------------------------------------------------------- approvals


def _approvals_path() -> Path:
    return _data_path("approvals.json")


def _approvals() -> dict:
    p = _approvals_path()
    return json.loads(p.read_text()) if p.exists() else {"approved": []}


def is_approved(tool: str) -> bool:
    if tool in _session_approved:
        return True
    return tool in _approvals().get("approved", [])


def approve(tool: str) -> str:
    if tool not in [r.get("tool") for r in _rules() + _extra_rules]:
        return f"Note: no rule references tool '{tool}' — nothing to approve."
    data = _approvals()
    if tool not in data["approved"]:
        data["approved"].append(tool)
        data["approved_at"] = {**data.get("approved_at", {}), tool: time.time()}
        _approvals_path().write_text(json.dumps(data, indent=2))
    return f"Approved '{tool}' — the agent may use it until revoked."


def revoke(tool: str) -> str:
    data = _approvals()
    data["approved"] = [t for t in data.get("approved", []) if t != tool]
    _session_approved.discard(tool)
    _approvals_path().write_text(json.dumps(data, indent=2))
    return f"Revoked approval for '{tool}'."


def session_approve(tool: str) -> None:
    """Approve for this process only (interactive y/N prompt path)."""
    _session_approved.add(tool)
