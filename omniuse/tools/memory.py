"""Memory toolset — a persistent, append-only record of what the agent did and why.

The agent loop auto-logs every tool call; memory_log() is for the agent's
explicit decisions and reasoning. Everything lands in an append-only JSONL
file the operator can review at any time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config


def _log_path() -> Path:
    d = Path(config.data_dir()) / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d / "log.jsonl"


def log_event(kind: str, **fields) -> None:
    """Append one event to the memory log (used by the agent loop and wallet)."""
    record = {"ts": time.time(), "kind": kind, **fields}
    with _log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _entries() -> list[dict]:
    p = _log_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _format(entry: dict) -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.get("ts", 0)))
    rest = ", ".join(f"{k}={str(v)[:120]}" for k, v in entry.items()
                     if k not in ("ts", "kind"))
    return f"[{stamp}] {entry.get('kind', '?')}: {rest}"


def memory_log(action: str, decision: str, reasoning: str) -> str:
    log_event("decision", action=action, decision=decision, reasoning=reasoning)
    return f"Logged decision for: {action}"


def memory_recent(n: int = 10) -> str:
    entries = _entries()[-max(1, min(n, 100)):]
    if not entries:
        return "Memory is empty."
    return "\n".join(_format(e) for e in entries)


def memory_search(query: str, limit: int = 20) -> str:
    q = query.lower()
    hits = [e for e in _entries() if q in json.dumps(e).lower()]
    if not hits:
        return f"No memory entries match '{query}'."
    return "\n".join(_format(e) for e in hits[-max(1, min(limit, 100)):])


TOOLS = {
    "memory_log": (memory_log, {
        "type": "function",
        "function": {
            "name": "memory_log",
            "description": (
                "Log a significant action, the decision taken, and your reasoning, "
                "so the operator can review the full history later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "What was done (or is about to be done)"},
                    "decision": {"type": "string", "description": "What you decided"},
                    "reasoning": {"type": "string", "description": "Why you decided that"},
                },
                "required": ["action", "decision", "reasoning"],
            },
        },
    }),
    "memory_recent": (memory_recent, {
        "type": "function",
        "function": {
            "name": "memory_recent",
            "description": "Show the most recent memory entries.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "How many entries (default 10)"}},
            },
        },
    }),
    "memory_search": (memory_search, {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search the memory log for past actions/decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": ["query"],
            },
        },
    }),
}
