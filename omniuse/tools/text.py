"""Text toolset — everyday text operations + LLM-powered text services.

Pure-local tools (no API needed): word counts, case, replace, regex extract,
slugify, diff.
LLM-powered tools (need a configured provider): summarize, translate.

These are the bread-and-butter operations for any writing/data work the
operator sells through the paid-work pipeline.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path


def _read_or_text(source: str) -> str:
    """Accept either the text itself or a path to a text file."""
    s = source.strip()
    try:
        if len(s) < 300 and ("/" in s or s.startswith(".")) and Path(s).is_file():
            return Path(s).read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return s


def text_wordcount(source: str) -> str:
    """Count words, characters, sentences and paragraphs."""
    text = _read_or_text(source)
    if not text.strip():
        return "ERROR: no text given."
    words = [w for w in re.split(r"\s+", text) if w]
    sentences = [s for s in re.split(r"[.!?]+(?:\s|$)", text) if s.strip()]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    longest = max(words, key=len) if words else ""
    return (f"Words: {len(words)}\nCharacters: {len(text)} (no spaces: "
            f"{len(text.replace(' ', '').replace(chr(10), ''))})\n"
            f"Sentences: {len(sentences)}\nParagraphs: {len(paragraphs)}\n"
            f"Longest word: '{longest}' ({len(longest)} chars)")


def text_case(source: str, mode: str = "upper") -> str:
    """upper / lower / title / sentence case."""
    text = _read_or_text(source)
    if not text:
        return "ERROR: no text given."
    mode = (mode or "").strip().lower()
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    if mode == "title":
        return text.title()
    if mode == "sentence":
        result = ". ".join(part.strip().capitalize() for part in text.split(". "))
        return result
    return "ERROR: mode must be one of upper, lower, title, sentence."


def text_replace(source: str, old: str, new: str, count_all: bool = True) -> str:
    """Replace every (or the first) occurrence of `old` with `new`."""
    text = _read_or_text(source)
    if not text:
        return "ERROR: no text given."
    if not old:
        return "ERROR: 'old' must not be empty."
    if count_all:
        n = text.count(old)
        return f"{text.replace(old, new)}\n\n({n} replacement{'s' if n != 1 else ''} made.)"
    return text.replace(old, new, 1)


def text_extract(source: str, pattern: str) -> str:
    """Extract everything matching a regular expression (one per line)."""
    text = _read_or_text(source)
    if not text:
        return "ERROR: no text given."
    if not pattern:
        return "ERROR: pattern must not be empty."
    try:
        matches = re.findall(pattern, text)
    except re.error as e:
        return f"ERROR: invalid regex ({e})."
    if not matches:
        return "No matches found."
    lines = []
    for m in matches:
        if isinstance(m, tuple):
            lines.append(" | ".join(str(part) for part in m if part))
        else:
            lines.append(str(m))
    return "\n".join(lines[:500])


def text_slug(source: str, max_len: int = 60) -> str:
    """Turn any text into a clean filename/URL slug."""
    text = _read_or_text(source)
    if not text:
        return "ERROR: no text given."
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    if not slug:
        return "ERROR: text has no slug-able characters (letters/digits)."
    if max_len:
        slug = slug[:max(1, int(max_len))].rstrip("-")
    return slug


def text_diff(source_a: str, source_b: str) -> str:
    """Line-by-line diff between two texts or files."""
    a = _read_or_text(source_a).splitlines()
    b = _read_or_text(source_b).splitlines()
    diff = list(difflib.unified_diff(a, b, fromfile="a", tofile="b", lineterm=""))
    if not diff:
        return "The two texts are identical."
    if len(diff) > 300:
        diff = diff[:300] + [f"... (+{len(diff) - 300} more diff lines)"]
    return "\n".join(diff)


def text_head(source: str, lines: int = 10) -> str:
    """First N lines of a text or file (peeking into deliverables)."""
    text = _read_or_text(source)
    if not text:
        return "ERROR: no text given."
    n = max(1, min(500, int(lines or 10)))
    head = "\n".join(text.splitlines()[:n])
    total = len(text.splitlines())
    return head + (f"\n... ({total} lines total)" if total > n else "")


def text_summarize(source: str, style: str = "bullet") -> str:
    """Summarize a text or file with the LLM (bullet / paragraph / tldr)."""
    text = _read_or_text(source)
    if not text.strip():
        return "ERROR: no text to summarize."
    if len(text) > 12000:
        text = text[:12000] + "\n...[truncated]"
    style_map = {
        "bullet": "as 5-8 short bullet points",
        "paragraph": "as one tight paragraph",
        "tldr": "as a single sentence TL;DR",
    }
    how = style_map.get((style or "").strip().lower())
    if not how:
        return "ERROR: style must be one of bullet, paragraph, tldr."
    from omniuse.llm import chat
    try:
        reply = chat([
            {"role": "system", "content": "You summarize text faithfully and concisely. Never invent facts that are not in the text."},
            {"role": "user", "content": f"Summarize the following {how}:\n\n{text}"},
        ])
    except Exception as e:  # noqa: BLE001
        return f"ERROR: summarization failed ({e})."
    return reply or "ERROR: empty response from the model."


def text_translate(source: str, to: str = "hindi", keep_format: bool = True) -> str:
    """Translate a text or file with the LLM."""
    text = _read_or_text(source)
    if not text.strip():
        return "ERROR: no text to translate."
    if len(text) > 10000:
        text = text[:10000] + "\n...[truncated]"
    fmt = ("Keep the original formatting, tone and structure. "
           if keep_format else "")
    from omniuse.llm import chat
    try:
        reply = chat([
            {"role": "system", "content": "You are a careful translator. Translate faithfully — do not add, remove or 'improve' content."},
            {"role": "user", "content": f"Translate the following text to {to}. {fmt}\n\n{text}"},
        ])
    except Exception as e:  # noqa: BLE001
        return f"ERROR: translation failed ({e})."
    return reply or "ERROR: empty response from the model."


TOOLS = {
    "text_wordcount": (text_wordcount, {
        "type": "function",
        "function": {
            "name": "text_wordcount",
            "description": "Count words, characters, sentences and paragraphs of a text or text file.",
            "parameters": {
                "type": "object",
                "properties": {"source": {"type": "string", "description": "The text, or a path to a text file"}},
                "required": ["source"],
            },
        },
    }),
    "text_case": (text_case, {
        "type": "function",
        "function": {
            "name": "text_case",
            "description": "Convert text to UPPER / lower / Title / Sentence case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "The text, or a path to a text file"},
                    "mode": {"type": "string", "enum": ["upper", "lower", "title", "sentence"]},
                },
                "required": ["source"],
            },
        },
    }),
    "text_replace": (text_replace, {
        "type": "function",
        "function": {
            "name": "text_replace",
            "description": "Replace every (or only the first) occurrence of a substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "The text, or a path to a text file"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "count_all": {"type": "boolean", "description": "Replace all occurrences (default true)"},
                },
                "required": ["source", "old", "new"],
            },
        },
    }),
    "text_extract": (text_extract, {
        "type": "function",
        "function": {
            "name": "text_extract",
            "description": "Extract everything matching a regular expression (one match per line).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "The text, or a path to a text file"},
                    "pattern": {"type": "string", "description": "Python regex"},
                },
                "required": ["source", "pattern"],
            },
        },
    }),
    "text_slug": (text_slug, {
        "type": "function",
        "function": {
            "name": "text_slug",
            "description": "Turn any text into a clean filename/URL slug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "max_len": {"type": "integer", "description": "Max slug length (default 60)"},
                },
                "required": ["source"],
            },
        },
    }),
    "text_diff": (text_diff, {
        "type": "function",
        "function": {
            "name": "text_diff",
            "description": "Line-by-line unified diff between two texts or files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_a": {"type": "string", "description": "First text (or path)"},
                    "source_b": {"type": "string", "description": "Second text (or path)"},
                },
                "required": ["source_a", "source_b"],
            },
        },
    }),
    "text_head": (text_head, {
        "type": "function",
        "function": {
            "name": "text_head",
            "description": "Show the first N lines of a text or file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "lines": {"type": "integer", "description": "How many lines (default 10)"},
                },
                "required": ["source"],
            },
        },
    }),
    "text_summarize": (text_summarize, {
        "type": "function",
        "function": {
            "name": "text_summarize",
            "description": "Summarize a text or file with the LLM (bullet points / paragraph / one-line TL;DR).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "style": {"type": "string", "enum": ["bullet", "paragraph", "tldr"]},
                },
                "required": ["source"],
            },
        },
    }),
    "text_translate": (text_translate, {
        "type": "function",
        "function": {
            "name": "text_translate",
            "description": "Translate a text or file with the LLM, keeping formatting and meaning intact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "to": {"type": "string", "description": "Target language, e.g. 'hindi', 'english', 'tamil'"},
                },
                "required": ["source"],
            },
        },
    }),
}
