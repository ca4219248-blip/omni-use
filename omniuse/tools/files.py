"""Files toolset — everyday local-file superpowers (stdlib only).

Read/write/append, list trees, find by glob, organize a folder by file
type, find duplicates by hash, report folder sizes, and zip backups.
Everything is plain Python — no extra dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path


def _safe_root(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    return p


def files_write(path: str, content: str, append: bool = False) -> str:
    """Write (or append to) a text file, creating parent folders."""
    if not path.strip():
        return "ERROR: path is required."
    p = _safe_root(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a" if append else "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        return f"ERROR: could not write ({e})."
    return (f"Appended {len(content)} chars to {p}" if append
            else f"Wrote {len(content)} chars to {p}")


def files_read(path: str, lines: int = 0) -> str:
    """Read a text file (optionally only the first N lines)."""
    p = _safe_root(path)
    if not p.is_file():
        return f"ERROR: file not found: {path}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"ERROR: could not read ({e})."
    if lines and lines > 0:
        text = "\n".join(text.splitlines()[:lines])
    if len(text) > 8000:
        text = text[:8000] + f"\n...[truncated, file is {p.stat().st_size} bytes]"
    return text or "(empty file)"


def files_list(path: str = ".", pattern: str = "*", depth: int = 3) -> str:
    """List a folder as a tree (glob-filterable, depth-limited)."""
    root = _safe_root(path)
    if not root.is_dir():
        return f"ERROR: folder not found: {path}"
    depth = max(1, min(8, int(depth or 3)))
    entries = []
    for p in sorted(root.glob(pattern)):
        if len(p.relative_to(root).parts) > depth:
            continue
        if p.is_dir():
            entries.append(f"{p.relative_to(root)}/")
        else:
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            entries.append(f"{p.relative_to(root)}  ({size:,} bytes)")
    if not entries:
        return f"Nothing matching '{pattern}' in {root}."
    return "\n".join(entries[:300])


def files_find(root: str = ".", pattern: str = "*") -> str:
    """Recursively find files/folders matching a glob pattern."""
    base = _safe_root(root)
    if not base.is_dir():
        return f"ERROR: folder not found: {root}"
    hits = [str(p.relative_to(base)) for p in base.rglob(pattern)][:300]
    if not hits:
        return f"No matches for '{pattern}' under {base}."
    return "\n".join(hits)


def files_sizes(path: str = ".") -> str:
    """Per-subfolder size breakdown of a folder."""
    root = _safe_root(path)
    if not root.is_dir():
        return f"ERROR: folder not found: {path}"

    def dir_size(d: Path) -> int:
        total = 0
        for f in d.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
        return total

    def human(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    rows = []
    for child in sorted(root.iterdir(), key=dir_size, reverse=True):
        if child.is_dir():
            rows.append(f"{human(dir_size(child)):>10}  {child.name}/")
        else:
            rows.append(f"{child.stat().st_size:>10,}  {child.name}")
    total = dir_size(root)
    return "\n".join(rows[:100]) + f"\n{'─' * 30}\nTOTAL: {human(total)} ({total:,} bytes)"


def files_organize(path: str = ".", dry_run: bool = True) -> str:
    """Sort files in a folder into subfolders by extension
    (Downloads-cleaner style). dry_run=True only reports what would move."""
    root = _safe_root(path)
    if not root.is_dir():
        return f"ERROR: folder not found: {path}"
    category = {
        "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic"},
        "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".xlsx", ".xls", ".csv", ".ppt", ".pptx"},
        "audio": {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"},
        "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
        "archives": {".zip", ".tar", ".gz", ".rar", ".7z", ".tgz"},
        "code": {".py", ".js", ".html", ".css", ".json", ".sh", ".ts", ".java", ".c", ".cpp"},
    }
    moves = []
    for f in sorted(root.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        folder = next((name for name, exts in category.items() if ext in exts), None)
        if folder is None:
            continue
        dest_dir = root / folder
        dest = dest_dir / f.name
        n = 1
        while dest.exists():
            dest = dest_dir / f"{f.stem}-{n}{f.suffix}"
            n += 1
        moves.append((f, dest))
    if not moves:
        return "Nothing to organize — no recognized file types lying loose."
    report = "\n".join(f"{src.name} → {dst.relative_to(root)}" for src, dst in moves[:100])
    if dry_run:
        return (f"DRY RUN — {len(moves)} file(s) would be organized:\n{report}\n"
                "Run again with dry_run=false to actually move them.")
    moved = 0
    for src, dst in moves:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved += 1
        except OSError:
            pass
    return f"Moved {moved}/{len(moves)} files into category folders."


def files_duplicates(path: str = ".") -> str:
    """Find duplicate files by content hash."""
    root = _safe_root(path)
    if not root.is_dir():
        return f"ERROR: folder not found: {path}"
    seen: dict[str, list[str]] = {}
    for f in root.rglob("*"):
        try:
            if not f.is_file() or f.stat().st_size == 0:
                continue
            h = hashlib.sha256()
            with f.open("rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            seen.setdefault(h.hexdigest()[:16], []).append(str(f.relative_to(root)))
        except OSError:
            continue
    dups = {h: paths for h, paths in seen.items() if len(paths) > 1}
    if not dups:
        return "No duplicate files found (by content)."
    lines = []
    for h, paths in list(dups.items())[:50]:
        lines.append(" == ".join(paths))
    wasted = 0
    for h, paths in dups.items():
        try:
            wasted += root.joinpath(paths[0]).stat().st_size * (len(paths) - 1)
        except OSError:
            pass
    return ("\n".join(lines) +
            f"\n\n{len(dups)} duplicate group(s), ~{wasted:,} bytes wasted.")


def files_backup(path: str, zip_path: str = "") -> str:
    """Zip a folder (or a single file) into a backup archive."""
    root = _safe_root(path)
    if not root.exists():
        return f"ERROR: not found: {path}"
    dest = Path(zip_path) if zip_path else root.with_name(root.name + f"-backup-{int(root.stat().st_mtime)}.zip")
    try:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            files = ([root] if root.is_file()
                     else [p for p in root.rglob("*") if p.is_file()])
            for p in files:
                zf.write(p, p.relative_to(root.parent))
    except OSError as e:
        return f"ERROR: backup failed ({e})."
    return f"Backup written: {dest} ({dest.stat().st_size:,} bytes, {len(files)} files)."


TOOLS = {
    "files_write": (files_write, {
        "type": "function",
        "function": {
            "name": "files_write",
            "description": "Write (or append to) a text file, creating parent folders as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean", "description": "Append instead of overwrite (default false)"},
                },
                "required": ["path", "content"],
            },
        },
    }),
    "files_read": (files_read, {
        "type": "function",
        "function": {
            "name": "files_read",
            "description": "Read a text file (optionally only the first N lines).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "lines": {"type": "integer", "description": "Only read the first N lines (0 = all)"},
                },
                "required": ["path"],
            },
        },
    }),
    "files_list": (files_list, {
        "type": "function",
        "function": {
            "name": "files_list",
            "description": "List a folder as a tree, glob-filterable and depth-limited.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string", "description": "Glob, e.g. '*.png'"},
                    "depth": {"type": "integer", "description": "Max depth (default 3, max 8)"},
                },
            },
        },
    }),
    "files_find": (files_find, {
        "type": "function",
        "function": {
            "name": "files_find",
            "description": "Recursively find files/folders matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.log' or '*.pdf'"},
                },
            },
        },
    }),
    "files_sizes": (files_sizes, {
        "type": "function",
        "function": {
            "name": "files_sizes",
            "description": "Per-subfolder size breakdown of a folder (what's eating the disk).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    }),
    "files_organize": (files_organize, {
        "type": "function",
        "function": {
            "name": "files_organize",
            "description": ("Sort loose files in a folder into images/documents/audio/video/archives/code "
                            "subfolders. dry_run=true (default) only reports; false actually moves."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                },
            },
        },
    }),
    "files_duplicates": (files_duplicates, {
        "type": "function",
        "function": {
            "name": "files_duplicates",
            "description": "Find duplicate files by content hash (sha256) under a folder.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    }),
    "files_backup": (files_backup, {
        "type": "function",
        "function": {
            "name": "files_backup",
            "description": "Zip a folder (or single file) into a backup archive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "zip_path": {"type": "string", "description": "Destination .zip path (default: <name>-backup-<ts>.zip next to it)"},
                },
                "required": ["path"],
            },
        },
    }),
}
