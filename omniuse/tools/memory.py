"""Memory toolset — persistent, layered memory of facts and actions.

Layers:
  - event log: append-only log.jsonl — every tool call is auto-logged here
    by the agent loop; memory_log() adds explicit decisions and reasoning.
  - fact store: key→value memory that survives across runs, split into
    layers (preferences / device / project) so the agent can remember
    things like "my GitHub username is …" without being told twice.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config

LAYERS = ("preferences", "device", "project")


def _data_dir() -> Path:
    d = Path(config.data_dir()) / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_path() -> Path:
    return _data_dir() / "log.jsonl"


def _store_path() -> Path:
    return _data_dir() / "store.json"


# ------------------------------------------------------------ event log


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


# ------------------------------------------------------------ fact store


def _load_store() -> dict:
    p = _store_path()
    return json.loads(p.read_text()) if p.exists() else {layer: {} for layer in LAYERS}


def _save_store(store: dict) -> None:
    _store_path().write_text(json.dumps(store, indent=2, ensure_ascii=False))


def memory_save(key: str, value, layer: str = "preferences") -> str:
    if layer not in LAYERS:
        return f"ERROR: layer must be one of {LAYERS}"
    if not key.strip():
        return "ERROR: key is required."
    store = _load_store()
    store[layer][key.strip()] = value
    _save_store(store)
    log_event("memory_saved", key=key, layer=layer)
    return f"Saved {layer}/{key} — I'll remember this across runs."


def memory_get(key: str) -> str:
    key = key.strip()
    store = _load_store()
    hits = [f"{layer}/{key} = {store[layer][key]}"
            for layer in LAYERS if key in store.get(layer, {})]
    if not hits:
        return f"I don't have '{key}' in memory. Ask the user, then memory_save() it."
    return "\n".join(hits)


def memory_forget(key: str) -> str:
    store = _load_store()
    removed = [layer for layer in LAYERS if store.get(layer, {}).pop(key, None) is not None]
    _save_store(store)
    return f"Forgot '{key}' from {removed}." if removed else f"'{key}' was not in memory."


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
    "memory_save": (memory_save, {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": (
                "Remember a fact across runs (e.g. the user's GitHub username, a "
                "device quirk, a project path). Check memory_get() before asking the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"description": "The fact to remember (string/number/JSON)"},
                    "layer": {"type": "string", "enum": ["preferences", "device", "project"],
                              "description": "preferences (about the user), device (about this machine), project"},
                },
                "required": ["key", "value"],
            },
        },
    }),
    "memory_get": (memory_get, {
        "type": "function",
        "function": {
            "name": "memory_get",
            "description": "Recall a remembered fact.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    }),
    "memory_forget": (memory_forget, {
        "type": "function",
        "function": {
            "name": "memory_forget",
            "description": "Delete a remembered fact.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    }),
}
