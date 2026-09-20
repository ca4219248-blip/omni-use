"""Ideas toolset — when the operator has no idea, think of some.

The agent brainstorms earning/project ideas, scores them, saves the good
ones, and works the best available one. This is the "free will" layer:
"bhai mujhe ₹300 chahiye" → the agent proposes ideas itself, picks the
best-scoring one, plans it, and starts working it (via missions/scheduler).

Ideas are stored in data/ideas/ideas.json so nothing is lost between runs:

    idea_save("Sell festival posters to local shops", ..., effort=2, earning=3)
    idea_list()                # ranked by score (earning*2 - effort)
    idea_update("Sell festival posters", "active")   # proposed/active/won/dropped
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config
from omniuse.tools import memory as _memory

IDEA_STATUSES = ("proposed", "active", "won", "dropped")


def _ideas_path() -> Path:
    d = Path(config.data_dir()) / "ideas"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ideas.json"


def _ideas() -> list[dict]:
    p = _ideas_path()
    return json.loads(p.read_text()) if p.exists() else []


def _save(ideas: list[dict]) -> None:
    _ideas_path().write_text(json.dumps(ideas, indent=2, ensure_ascii=False))


def _clamp(n: float) -> int:
    return max(1, min(5, int(round(float(n)))))


def idea_save(title: str, summary: str = "", effort: int = 3, earning: int = 3) -> str:
    """Save a candidate idea, scored by earning potential vs effort."""
    if not title.strip():
        return "ERROR: title is required."
    try:
        effort, earning = _clamp(effort), _clamp(earning)
    except (TypeError, ValueError):
        return "ERROR: effort and earning must be numbers (1-5)."
    ideas = _ideas()
    if any(i["title"].lower() == title.strip().lower() for i in ideas):
        return f"Note: '{title.strip()}' is already saved — use idea_update to change it."
    idea = {"title": title.strip(), "summary": summary.strip(),
            "effort": effort, "earning": earning,
            "score": earning * 2 - effort, "status": "proposed",
            "created": time.time(), "notes": []}
    ideas.append(idea)
    _save(ideas)
    _memory.log_event("idea_saved", title=idea["title"], score=idea["score"])
    best = max(i["score"] for i in ideas)
    return (f"Idea saved: '{idea['title']}' (score {idea['score']}: earning {earning}/5, "
            f"effort {effort}/5). "
            + ("This is your best-scoring idea — consider working it next."
               if idea["score"] == best else f"Best current idea scores {best}."))


def idea_list(status: str = "") -> str:
    """Show saved ideas, best score first."""
    ideas = _ideas()
    if status:
        status = status.strip().lower()
        if status not in IDEA_STATUSES:
            return f"ERROR: status must be one of {IDEA_STATUSES}"
        ideas = [i for i in ideas if i["status"] == status]
    if not ideas:
        return ("No ideas saved yet. Brainstorm honestly: what does the operator "
                "already have (skills, devices, accounts) that people nearby or "
                "online would pay a small amount for? Save candidates with idea_save.")
    ranked = sorted(ideas, key=lambda i: (-i["score"], -i["earning"]))
    lines = [f"- [{i['status']}] {i['title']} (score {i['score']}, "
             f"earning {i['earning']}/5, effort {i['effort']}/5)"
             + (f" — {i['summary']}" if i["summary"] else "")
             for i in ranked]
    return "\n".join(lines)


def idea_update(title: str, status: str, note: str = "") -> str:
    """Change an idea's status (proposed → active → won/dropped) and log notes."""
    ideas = _ideas()
    match = next((i for i in ideas if i["title"].lower() == title.strip().lower()), None)
    if not match:
        return f"ERROR: no saved idea named '{title}'."
    if status.strip().lower() not in IDEA_STATUSES:
        return f"ERROR: status must be one of {IDEA_STATUSES}"
    match["status"] = status.strip().lower()
    if note.strip():
        match["notes"] = match.get("notes", []) + [{"note": note.strip(), "ts": time.time()}]
    _save(ideas)
    _memory.log_event("idea_updated", title=match["title"], status=match["status"])
    return f"'{match['title']}' → {match['status']}" + (f" (note: {note.strip()})" if note.strip() else "")


TOOLS = {
    "idea_save": (idea_save, {
        "type": "function",
        "function": {
            "name": "idea_save",
            "description": (
                "Save a candidate idea (earning/project), scored by earning "
                "potential (1-5) vs effort (1-5). Use when the operator has no "
                "idea — brainstorm several and save the good ones."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short name of the idea"},
                    "summary": {"type": "string", "description": "What it is, in one or two lines"},
                    "effort": {"type": "integer", "description": "How much work it needs, 1 (easy) to 5 (hard)"},
                    "earning": {"type": "integer", "description": "Earning potential, 1 (low) to 5 (high)"},
                },
                "required": ["title"],
            },
        },
    }),
    "idea_list": (idea_list, {
        "type": "function",
        "function": {
            "name": "idea_list",
            "description": "Show saved ideas, best score first (optionally filtered by status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": list(IDEA_STATUSES),
                               "description": "Optional filter: proposed/active/won/dropped"},
                },
            },
        },
    }),
    "idea_update": (idea_update, {
        "type": "function",
        "function": {
            "name": "idea_update",
            "description": "Change an idea's status (proposed → active → won/dropped) and optionally add a note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "status": {"type": "string", "enum": list(IDEA_STATUSES)},
                    "note": {"type": "string", "description": "Progress note"},
                },
                "required": ["title", "status"],
            },
        },
    }),
}
