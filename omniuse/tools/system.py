"""System toolset — run shell commands and work with files on the local machine."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def system_run(command: str, timeout: int = 60) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.getenv("OMNIUSE_WORKDIR", "."),
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"
    output = (result.stdout or "") + (("\n[stderr]\n" + result.stderr) if result.stderr.strip() else "")
    output = output.strip() or "(no output)"
    if len(output) > 6000:
        output = output[:6000] + "\n...[truncated]"
    return f"exit={result.returncode}\n{output}"


def system_write_file(path: str, content: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}"


def system_read_file(path: str, max_chars: int = 8000) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text


def system_list_dir(path: str = ".") -> str:
    entries = sorted(Path(path).iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [f"{'d' if e.is_dir() else '-'} {e.name}" for e in entries[:200]]
    return "\n".join(lines) or "(empty)"


TOOLS = {
    "system_run": (system_run, {
        "type": "function",
        "function": {
            "name": "system_run",
            "description": "Run a shell command on this computer and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Seconds (default 60)"},
                },
                "required": ["command"],
            },
        },
    }),
    "system_write_file": (system_write_file, {
        "type": "function",
        "function": {
            "name": "system_write_file",
            "description": "Write text to a file (creates directories as needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    }),
    "system_read_file": (system_read_file, {
        "type": "function",
        "function": {
            "name": "system_read_file",
            "description": "Read a text file from this computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "description": "Default 8000"},
                },
                "required": ["path"],
            },
        },
    }),
    "system_list_dir": (system_list_dir, {
        "type": "function",
        "function": {
            "name": "system_list_dir",
            "description": "List the contents of a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Default '.'"}},
            },
        },
    }),
}
