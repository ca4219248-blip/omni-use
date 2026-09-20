"""CSV/data toolset — inspect, filter, transform tabular data (stdlib only).

Reads CSVs with the csv module, gives column-level summaries
(types, unique counts, min/max/mean for numeric columns), filters rows
by simple expressions, selects/reorders columns, merges files and converts
to JSON. Handles real-world messy files (utf-8 fallback, sniffed dialect).
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path


def _read_rows(path: str) -> tuple[list[str], list[dict]]:
    """Returns (headers, rows-as-dicts)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    with p.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        headers = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    if not headers:
        raise ValueError("empty CSV (no header row)")
    return headers, rows


def _numify(value: str):
    s = (value or "").strip().replace(",", "")
    if not s:
        return None
    try:
        f = float(s)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


def csv_summary(path: str) -> str:
    """Column-level summary: row count, types, uniques, numeric stats."""
    try:
        headers, rows = _read_rows(path)
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except ValueError as e:
        return f"ERROR: {e}"
    lines = [f"{path}: {len(rows)} data row(s), {len(headers)} column(s)", ""]
    for col in headers:
        values = [r.get(col, "") for r in rows]
        nums = [n for n in (_numify(v) for v in values) if n is not None]
        uniques = len(set(values))
        if nums and len(nums) >= len(values) * 0.8:
            stats = (f"numeric — min {min(nums)}, max {max(nums)}, "
                     f"mean {statistics.fmean(nums):.2f}, sum {sum(nums):.2f}")
            kind = stats
        else:
            kind = "text"
        lines.append(f"- {col}: {kind}, {uniques} unique" +
                     (f", sample: {values[0][:40]!r}" if values else ""))
    return "\n".join(lines)


def csv_head(path: str, n: int = 5) -> str:
    """First N data rows, aligned columns."""
    try:
        headers, rows = _read_rows(path)
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except ValueError as e:
        return f"ERROR: {e}"
    n = max(1, min(50, int(n or 5)))
    rows = rows[:n]
    widths = {h: max([len(str(h))] + [len(str(r.get(h, ""))) for r in rows]) for h in headers}
    def fmt(row: dict) -> str:
        return " | ".join(str(row.get(h, ""))[:widths[h]].ljust(widths[h]) for h in headers)
    out = [fmt({h: h for h in headers}), "-" * (sum(widths.values()) + 3 * (len(headers) - 1))]
    out += [fmt(r) for r in rows]
    return "\n".join(out)


def csv_filter(path: str, column: str, operator: str = "equals",
               value: str = "", out_path: str = "") -> str:
    """Filter rows where COLUMN OPERATOR VALUE.
    Operators: equals, not_equals, contains, gt, lt, gte, lte (numeric)."""
    try:
        headers, rows = _read_rows(path)
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except ValueError as e:
        return f"ERROR: {e}"
    if column not in headers:
        return f"ERROR: no column '{column}'. Columns: {headers}"
    op = (operator or "equals").strip().lower()
    target = _numify(value)
    def match(row: dict) -> bool:
        cell = str(row.get(column, "")).strip()
        if op == "equals":
            return cell.lower() == value.strip().lower()
        if op == "not_equals":
            return cell.lower() != value.strip().lower()
        if op == "contains":
            return value.strip().lower() in cell.lower()
        num = _numify(cell)
        if num is None or target is None:
            return False
        if op == "gt":
            return num > target
        if op == "lt":
            return num < target
        if op == "gte":
            return num >= target
        if op == "lte":
            return num <= target
        return False
    kept = [r for r in rows if match(r)]
    if not kept:
        return f"0 of {len(rows)} rows matched ({column} {op} {value})."
    dest = Path(out_path) if out_path else Path(path).with_name(
        Path(path).stem + f"-filtered-{column}.csv")
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(kept)
    return (f"Kept {len(kept)} of {len(rows)} rows ({column} {op} {value}) → {dest}.")


def csv_select(path: str, columns: str, out_path: str = "") -> str:
    """Select/reorder columns (comma-separated list), save as a new CSV."""
    try:
        headers, rows = _read_rows(path)
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except ValueError as e:
        return f"ERROR: {e}"
    wanted = [c.strip() for c in columns.split(",") if c.strip()]
    missing = [c for c in wanted if c not in headers]
    if missing:
        return f"ERROR: columns not found: {missing}. Available: {headers}"
    dest = Path(out_path) if out_path else Path(path).with_name(
        Path(path).stem + "-selected.csv")
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=wanted, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return f"Wrote {len(rows)} rows with columns {wanted} → {dest}."


def csv_merge(path_a: str, path_b: str, out_path: str = "") -> str:
    """Merge two CSVs with the same columns, skipping duplicates in b."""
    try:
        headers_a, rows_a = _read_rows(path_a)
        headers_b, rows_b = _read_rows(path_b)
    except FileNotFoundError as e:
        return f"ERROR: file not found: {e}"
    except ValueError as e:
        return f"ERROR: {e}"
    if headers_a != headers_b:
        return (f"ERROR: columns differ.\nA: {headers_a}\nB: {headers_b}\n"
                "Use csv_select first to make them match.")
    seen = {json.dumps(r, sort_keys=True) for r in rows_a}
    added = 0
    for r in rows_b:
        key = json.dumps(r, sort_keys=True)
        if key not in seen:
            rows_a.append(r)
            seen.add(key)
            added += 1
    dest = Path(out_path) if out_path else Path(path_a).with_name("merged.csv")
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers_a)
        writer.writeheader()
        writer.writerows(rows_a)
    return (f"Merged: {len(rows_a)} total rows ({added} added from {path_b}, "
            f"{len(rows_b) - added} duplicate(s) skipped) → {dest}.")


def csv_to_json(path: str, out_path: str = "") -> str:
    """Convert a CSV to a JSON array (pretty-printed, utf-8)."""
    try:
        _, rows = _read_rows(path)
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except ValueError as e:
        return f"ERROR: {e}"
    dest = Path(out_path) if out_path else Path(path).with_suffix(".json")
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"Converted {len(rows)} row(s) → {dest}."


TOOLS = {
    "csv_summary": (csv_summary, {
        "type": "function",
        "function": {
            "name": "csv_summary",
            "description": "Column-level summary of a CSV: row count, types, unique counts, numeric min/max/mean/sum.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }),
    "csv_head": (csv_head, {
        "type": "function",
        "function": {
            "name": "csv_head",
            "description": "Show the first N rows of a CSV, aligned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "n": {"type": "integer", "description": "Rows to show (default 5, max 50)"},
                },
                "required": ["path"],
            },
        },
    }),
    "csv_filter": (csv_filter, {
        "type": "function",
        "function": {
            "name": "csv_filter",
            "description": ("Filter rows where a column matches a condition "
                            "(equals / not_equals / contains / gt / lt / gte / lte) and save the result."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "column": {"type": "string"},
                    "operator": {"type": "string", "enum": ["equals", "not_equals", "contains", "gt", "lt", "gte", "lte"]},
                    "value": {"type": "string"},
                    "out_path": {"type": "string"},
                },
                "required": ["path", "column", "value"],
            },
        },
    }),
    "csv_select": (csv_select, {
        "type": "function",
        "function": {
            "name": "csv_select",
            "description": "Select and/or reorder columns (comma-separated) into a new CSV.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "columns": {"type": "string", "description": "Comma-separated column names"},
                    "out_path": {"type": "string"},
                },
                "required": ["path", "columns"],
            },
        },
    }),
    "csv_merge": (csv_merge, {
        "type": "function",
        "function": {
            "name": "csv_merge",
            "description": "Merge two CSVs with identical columns, skipping duplicate rows from the second file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path_a": {"type": "string"},
                    "path_b": {"type": "string"},
                    "out_path": {"type": "string"},
                },
                "required": ["path_a", "path_b"],
            },
        },
    }),
    "csv_to_json": (csv_to_json, {
        "type": "function",
        "function": {
            "name": "csv_to_json",
            "description": "Convert a CSV file to a pretty-printed JSON array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "out_path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    }),
}
