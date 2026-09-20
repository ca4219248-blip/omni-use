"""Auto-router — pick the toolsets a task actually needs, before the agent runs.

Giving an LLM all 100+ tool schemas wastes tokens and confuses tool choice.
The router fixes that: ONE cheap call (the fast model, no tools attached)
reads the task, looks at a compact catalog of toolsets, and returns a short
list of relevant ones. The agent then runs with just those schemas.

Usage:
    Agent(toolsets="auto").run(task)          # router picks, then the agent runs
    python cli.py --tools auto "task..."      # same from the CLI

If the LLM call fails or returns junk, a keyword heuristic picks instead —
the router NEVER blocks a task, it only narrows the menu.
"""

from __future__ import annotations

import json

from omniuse.llm import chat
from omniuse.tools import TOOLSETS
from omniuse.tools import memory as _memory

# Keyword fallback: obvious task words → toolsets that certainly help.
_KEYWORDS = {
    "browser": ("browser", "website", "open ", "url", "google", "youtube",
                "search online", "login", "web page"),
    "screen": ("screen", "element", "button", "click on", "ui", "menu", "clickable"),
    "universal": ("tap ", "swipe", "click the"),
    "mobile": ("phone", "android", "sms", "whatsapp", "notification", "adb", "mobile"),
    "system": ("shell", "command", "terminal", "install", "process", "run this"),
    "vision": ("image", "photo", "screenshot", "look at", "picture", "see "),
    "files": ("file", "folder", "directory", "organize", "duplicate", "backup", "zip"),
    "media": ("resize", "crop", "compress image", "convert to png", "jpg", "webp",
              "thumbnail grid", "contact sheet"),
    "csvdata": ("csv", "spreadsheet", "excel", "table data", "row", "column", "json convert"),
    "text": ("summarize", "translate", "word count", "rewrite", "proofread", "slug",
             "diff", "essay", "article", "write a"),
    "notes": ("note", "notebook", "remember to do", "to-do", "todo"),
    "qr": ("qr code", "wifi password share", "vcard", "contact card"),
    "design": ("poster", "design", "banner", "logo", "watermark", "flyer", "thumbnail"),
    "payments": ("payment", "upi", "qr for payment", "paid", "₹", "rupees", "order"),
    "shop": ("order", "client", "catalog", "prospect", "outreach", "sell", "customer"),
    "ideas": ("idea", "brainstorm", "no idea", "kuch kar", "earn", "paisa", "money"),
    "speech": ("speak", "say out loud", "voice reply", "bol "),
    "memory": ("remember", "yaad", "recall", "last time", "history"),
    "policy": ("terms of service", "allowed to automate", "policy check"),
    "escalate": ("kyc", "bank account", "signature", "legal"),
    "remote": ("remote machine", "vps", "server"),
}


def _catalog() -> str:
    """One line per toolset: name + first few tool names (cheap for the LLM)."""
    lines = []
    for name, tools in TOOLSETS.items():
        sample = ", ".join(list(tools)[:6])
        lines.append(f"- {name}: {sample}")
    return "\n".join(lines)


def _heuristic(task: str, k: int = 6) -> list[str]:
    t = f" {task.lower()} "
    scores: dict[str, int] = {}
    for toolset, words in _KEYWORDS.items():
        for w in words:
            if w in t:
                scores[toolset] = scores.get(toolset, 0) + 1
    ranked = sorted(scores, key=lambda s: -scores[s])
    picked = [s for s in ranked if s in TOOLSETS][:k]
    return picked or ["memory", "system"]


def _parse_names(raw: str) -> list[str]:
    """Extract toolset names from whatever the LLM replied with."""
    raw = (raw or "").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            if isinstance(data, list):
                return [str(x).strip().lower() for x in data if isinstance(x, (str,))]
        except json.JSONDecodeError:
            pass
    return [name for name in TOOLSETS if name in raw.lower()]


def suggest_toolsets(task: str, k: int = 6) -> list[str]:
    """Pick the toolsets this task needs. Never raises; falls back to keywords."""
    if not task or not task.strip():
        return ["memory"]
    system = (
        "You pick toolsets for an AI agent. Given a task and a catalog of toolsets "
        "(name: sample tools), reply with ONLY a JSON array of the 3-6 toolset names "
        "the task genuinely needs — no explanation, no extra text.\n"
        "Rules: include 'memory' only if the task mentions remembering/recalling; "
        "include 'screen' or 'universal' when interacting with pages/apps; "
        "when unsure, prefer fewer but sufficient toolsets.\n\nCatalog:\n"
        + _catalog()
    )
    try:
        message = chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": task[:2000]}],
            fast=True,
        )
        names = _parse_names(message.get("content") or "")
    except Exception:  # noqa: BLE001 — router must never block a task
        names = []
    picked = [n for n in names if n in TOOLSETS][:max(1, k)] if names else []
    if not picked:
        picked = _heuristic(task, k)
    _memory.log_event("router_selection", task=task[:200], toolsets=picked)
    return picked
