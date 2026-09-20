"""Notes toolset — a fast, searchable personal notebook for the operator.

Plain JSONL storage in the data dir (one JSON object per line): every note
has an id, text, optional tags and a timestamp. Add, list, search
(case-insensitive, tag-aware), and delete. The agent uses this to keep
running notes on clients, ideas, to-dos — anything it should remember in
human-readable form (facts it must recall later belong in memory_save).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config


def _notes_path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "notes.jsonl"


def _notes() -> list[dict]:
    p = _notes_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _save_notes(notes: list[dict]) -> None:
    _notes_path().write_text(
        "\n".join(json.dumps(n, ensure_ascii=False) for n in notes) + "\n",
        encoding="utf-8")


def _next_id(notes: list[dict]) -> int:
    return max((int(n.get("id", 0)) for n in notes), default=0) + 1


def notes_add(text: str, tags: str = "") -> str:
    """Add a note. Tags are comma-separated, optional."""
    text = (text or "").strip()
    if not text:
        return "ERROR: note text is required."
    notes = _notes()
    note = {"id": _next_id(notes),
            "text": text,
            "tags": [t.strip().lower() for t in (tags or "").split(",") if t.strip()],
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts": time.time()}
    notes.append(note)
    _save_notes(notes)
    return f"Note #{note['id']} saved" + (f" {note['tags']}" if note["tags"] else "") + "."


def notes_list(tag: str = "", limit: int = 20) -> str:
    """List notes — newest last — optionally filtered by tag."""
    notes = _notes()
    if not notes:
        return "No notes yet (notes_add to create one)."
    if tag.strip():
        t = tag.strip().lower()
        notes = [n for n in notes if t in n.get("tags", [])]
        if not notes:
            return f"No notes tagged '{tag}'."
    limit = max(1, min(200, int(limit or 20)))
    notes = notes[-limit:]
    lines = []
    for n in notes:
        tag_str = f" {n['tags']}" if n.get("tags") else ""
        lines.append(f"#{n['id']} [{n.get('created', '?')}]{tag_str} {n['text']}")
    return "\n".join(lines)


def notes_search(query: str, tag: str = "") -> str:
    """Case-insensitive full-text search through notes."""
    query = (query or "").strip().lower()
    if not query and not tag.strip():
        return "ERROR: give me something to search for."
    hits = []
    for n in _notes():
        if tag.strip() and tag.strip().lower() not in n.get("tags", []):
            continue
        if query and query not in n.get("text", "").lower():
            continue
        hits.append(n)
    if not hits:
        return "No matching notes."
    lines = [f"#{n['id']} {n['text']}" for n in hits[:50]]
    return "\n".join(lines) + (f"\n({len(hits)} match{'es' if len(hits) != 1 else ''})")


def notes_delete(note_id: int) -> str:
    """Delete a note by its id."""
    try:
        note_id = int(note_id)
    except (TypeError, ValueError):
        return "ERROR: note id must be a number."
    notes = _notes()
    kept = [n for n in notes if int(n.get("id", 0)) != note_id]
    if len(kept) == len(notes):
        return f"ERROR: no note #{note_id}."
    _save_notes(kept)
    return f"Note #{note_id} deleted ({len(kept)} notes left)."


TOOLS = {
    "notes_add": (notes_add, {
        "type": "function",
        "function": {
            "name": "notes_add",
            "description": "Add a note (text + optional comma-separated tags) to the operator's notebook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "tags": {"type": "string", "description": "e.g. 'client, followup'"},
                },
                "required": ["text"],
            },
        },
    }),
    "notes_list": (notes_list, {
        "type": "function",
        "function": {
            "name": "notes_list",
            "description": "List notes, optionally filtered by tag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "limit": {"type": "integer", "description": "Most recent N notes (default 20)"},
                },
            },
        },
    }),
    "notes_search": (notes_search, {
        "type": "function",
        "function": {
            "name": "notes_search",
            "description": "Case-insensitive full-text search through the notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tag": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }),
    "notes_delete": (notes_delete, {
        "type": "function",
        "function": {
            "name": "notes_delete",
            "description": "Delete a note by id.",
            "parameters": {
                "type": "object",
                "properties": {"note_id": {"type": "integer"}},
                "required": ["note_id"],
            },
        },
    }),
}
