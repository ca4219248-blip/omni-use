"""Reports toolset — turn any task/mission report into a real PDF file.

Pure-stdlib PDF writer (no fpdf/reportlab dependency): builds a valid PDF 1.4
document with Helvetica regular/bold, wrapped paragraphs, headings, bullets
and automatic page breaks. Non-latin-1 characters (₹ etc.) are transliterated
so nothing ever crashes while writing a report.

task_report(title, sections_json) is the tool the agent calls after finishing
a task: it writes data/reports/<slug>-<ts>.pdf and returns the path.
Missions also auto-generate their PDF next to the .md report.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from omniuse import config
from omniuse.tools import memory as _memory

_PAGE_W, _PAGE_H = 595, 842          # A4, points
_MARGIN, _LINE_H = 56, 15
_BODY, _H1, _H2, _BULLET = 10.5, 17, 13, 10.5


def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _latin(text: str) -> str:
    """Transliterate to latin-1 for the standard PDF fonts (₹ → Rs.)."""
    replacements = {"₹": "Rs.", "—": "-", "–": "-", "…": "...", "’": "'",
                     "‘": "'", "“": '"', "”": '"', "✓": "OK", "→": "->"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy word-wrap using the Helvetica width table (approx. per char)."""
    widths = _HELV_W.get(font, _HELV_W["F1"])
    def text_w(s: str) -> float:
        return sum(widths.get(c, size * 0.55) for c in s) / 1000 * size
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if text_w(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


# Helvetica AFM widths for the 95 printable ASCII chars (per 1000 units).
_HELV_W = {}
_EVEN = {"F1": {}, "F2": {}}
def _load_widths():
    base = (" 278,!278,\"355,#556,$556,%889,&667,'191,(333,)333,*389,+584,"
            ",278,-333,.278,/278")
    digits = "556"
    common = (":278,;278,<584,=584,>584,?556,@1015,A667,B667,C722,D722,E667,"
              "F611,G778,H722,I278,J500,K667,L556,M833,N722,O778,P667,Q778,"
              "R722,S667,T611,U722,V667,W944,X667,Y667,Z611,[278,\\278,]278,"
              "^469,_556,`333,a556,b556,c500,d556,e556,f278,g556,h556,i222,"
              "j222,j500,k500,l222,m833,n556,o556,p556,q556,r333,s500,t278,"
              "u556,v500,w722,x500,y500,z500,{334,|260,}334,~584")
    for pair in base.split(","):
        if pair:
            _EVEN["F1"][pair[0]] = int(pair[1:])
    for ch in "0123456789":
        _EVEN["F1"][ch] = 556
    for pair in common.split(","):
        if pair:
            _EVEN["F1"][pair[0]] = int(pair[1:])
    # bold: approximate by scaling regular widths ~1.08x (good enough for wrap)
    _EVEN["F2"] = {c: int(w * 1.08) for c, w in _EVEN["F1"].items()}
    _HELV_W.update(_EVEN)

_load_widths()


class _PDFBuilder:
    """A minimal but valid PDF document writer."""

    def __init__(self):
        self.pages: list[list[str]] = [[]]
        self.y = _PAGE_H - _MARGIN

    def _new_page(self):
        self.pages.append([])
        self.y = _PAGE_H - _MARGIN

    def line(self, text: str, font: str = "F1", size: float = _BODY,
             gap_after: float = 4):
        for wrapped in _wrap(_latin(text), font, size, _PAGE_W - 2 * _MARGIN):
            if self.y < _MARGIN + _LINE_H:
                self._new_page()
            self.pages[-1].append(
                f"BT /{font} {size:.1f} Tf 1 0 0 1 {_MARGIN} {self.y:.1f} Tm ({_esc(wrapped)}) Tj ET")
            self.y -= _LINE_H
        self.y -= gap_after

    def h1(self, text):
        self.y -= 8
        self.line(text, "F2", _H1, 10)

    def h2(self, text):
        self.y -= 6
        self.line(text, "F2", _H2, 6)

    def bullet(self, text):
        self.line(f"•  {text}", "F1", _BULLET, 2)

    def build(self) -> bytes:
        page_objs = []
        for page in self.pages:
            content = "\n".join(page)
            page_objs.append(content)
        # object numbering: 1=catalog 2=pages 3=F1 4=F2, then pages, then contents
        n_pages = len(page_objs)
        objs = ["", ""]
        objs[0] = "<< /Type /Catalog /Pages 2 0 R >>"
        kids = " ".join(f"{5 + 2 * i} 0 R" for i in range(n_pages))
        objs[1] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"
        objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        for i, content in enumerate(page_objs):
            objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox "
                         f"[0 0 {_PAGE_W} {_PAGE_H}] /Resources << /Font "
                         "<< /F1 3 0 R /F2 4 0 R >> >> /Contents "
                         f"{6 + 2 * i} 0 R >>"))
        for content in page_objs:
            objs.append(f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        xref_at = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_at}\n%%EOF\n").encode()
        return bytes(out)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (s[:40] or "report")


def _report_pdf(title: str, sections: list[dict], footer: str = "") -> str:
    """sections: [{"title": ..., "body": ..., "bullets": [...]}] → PDF path."""
    pdf = _PDFBuilder()
    pdf.h1(title)
    pdf.line(time.strftime("Generated: %d %b %Y, %H:%M"), "F1", 9, 8)
    for sec in sections:
        if sec.get("title"):
            pdf.h2(str(sec["title"]))
        for para in str(sec.get("body", "")).split("\n"):
            if para.strip():
                pdf.line(para.strip())
        for b in sec.get("bullets", [])[:30]:
            pdf.bullet(str(b))
    if footer:
        pdf.y -= 6
        pdf.line(footer, "F1", 9)
    out_dir = Path(config.data_dir()) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{_slug(title)}-{int(time.time())}.pdf"
    out.write_bytes(pdf.build())
    return str(out)


def task_report(title: str, sections_json: str, footer: str = "") -> str:
    """Write a full task report as a PDF the operator can read and keep.

    sections_json: [{"title": "What I did", "body": "...", "bullets": ["..."]}]
    """
    if not (title or "").strip():
        return "ERROR: title is required."
    try:
        sections = json.loads(sections_json or "[]")
        if not isinstance(sections, list):
            raise ValueError("sections_json must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        return f"ERROR: sections_json must be a JSON array like [{{\"title\":..., \"body\":...}}] ({e})."
    if not sections:
        return "ERROR: at least one section is required."
    for sec in sections:
        if not isinstance(sec, dict):
            return "ERROR: every section must be a JSON object."
    path = _report_pdf(title.strip(), sections, footer)
    _memory.log_event("report_pdf", title=title[:100], path=path)
    return f"PDF report saved to {path} — give this to the operator."


def report_list() -> str:
    """List the PDF reports generated so far."""
    out_dir = Path(config.data_dir()) / "reports"
    if not out_dir.is_dir():
        return "No reports yet (task_report creates them)."
    files = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "No reports yet (task_report creates them)."
    lines = []
    for f in files[:50]:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
        lines.append(f"- {f.name}  ({f.stat().st_size:,} bytes, {stamp})")
    return f"{len(files)} report(s) in {out_dir}:\n" + "\n".join(lines)


TOOLS = {
    "task_report": (task_report, {
        "type": "function",
        "function": {
            "name": "task_report",
            "description": (
                "Write a complete PDF report of a finished task/mission for the operator: "
                "what was done, how, what failed, what was learned. sections_json is a JSON "
                "array like [{\"title\": \"What I did\", \"body\": \"...\", \"bullets\": [\"step 1\", ...]}]. "
                "Call it when a significant task completes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Report title, e.g. 'Poster order for Sharma Sweets'"},
                    "sections_json": {"type": "string", "description": "JSON array of sections"},
                    "footer": {"type": "string", "description": "Optional footer note"},
                },
                "required": ["title", "sections_json"],
            },
        },
    }),
    "report_list": (report_list, {
        "type": "function",
        "function": {
            "name": "report_list",
            "description": "List the PDF reports generated so far.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }),
}
