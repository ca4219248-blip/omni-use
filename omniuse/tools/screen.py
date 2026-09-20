"""Screen understanding — turn a screen into structured elements.

Instead of "screenshot → guess coordinates", the agent asks screen_elements()
and gets a structured view:

    Screen
     ├── <button> Start Race
     ├── <input>  Username
     ├── <a>      Settings
     └── ...

Browser: extracted from the live DOM (Playwright).
Mobile:  extracted from Android's accessibility tree (uiautomator dump).

Set-of-Marks: screen_marks() takes a screenshot and draws numbered boxes on
every interactive element, so the model can reason "element #7" instead of
"pixel (340,220)" — much more reliable clicking.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET

from omniuse.tools import browser as _browser
from omniuse.tools import mobile as _mobile

_JS_EXTRACT = """
() => {
  const out = [];
  const els = document.querySelectorAll(
    'a, button, input, select, textarea, [role=button], [onclick], h1, h2, h3');
  for (const e of els) {
    const text = (e.innerText || e.value || e.placeholder ||
                  e.getAttribute('aria-label') || '').trim().slice(0, 80);
    const tag = e.tagName.toLowerCase();
    const sel = e.id ? '#' + e.id : (e.getAttribute('name') ?
                `${tag}[name="${e.getAttribute('name')}"]` : '');
    if (text || sel) out.push({tag, text, sel});
    if (out.length >= 60) break;
  }
  return out;
}
"""

_JS_MARKS = """
() => {
  const out = [];
  const els = document.querySelectorAll(
    'a, button, input, select, textarea, [role=button], [onclick]');
  for (const e of els) {
    const text = (e.innerText || e.value || e.placeholder ||
                  e.getAttribute('aria-label') || '').trim().slice(0, 80);
    if (!text) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 5 || r.height < 5) continue;
    out.push({text, x: Math.round(r.x), y: Math.round(r.y),
              w: Math.round(r.width), h: Math.round(r.height)});
    if (out.length >= 40) break;
  }
  return out;
}
"""

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _center(bounds: str):
    m = _BOUNDS_RE.match(bounds or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def _mobile_tree() -> list[dict]:
    _mobile._shell("uiautomator dump /sdcard/omniuse_dump.xml")
    raw = _mobile._adb("shell", "cat /sdcard/omniuse_dump.xml")
    root = ET.fromstring(raw)
    elements = []
    for node in root.iter("node"):
        text = (node.get("text") or node.get("content-desc") or "").strip()
        center = _center(node.get("bounds", ""))
        if center and (text or node.get("clickable") == "true"):
            elements.append({"tag": node.get("class", "?").split(".")[-1].lower(),
                             "text": text, "center": center,
                             "bounds": node.get("bounds", "")})
    return elements


def _bounds_rect(bounds: str):
    """'[x1,y1][x2,y2]' → (x, y, w, h), or None."""
    m = _BOUNDS_RE.match(bounds or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1, y1, x2 - x1, y2 - y1)


def _annotate(screenshot_path: str, marks: list[dict], out_path: str = "") -> str:
    """Draw numbered boxes on a screenshot (Set-of-Marks).

    marks: [{text, x, y, w, h}, ...] in screenshot pixel coordinates.
    Returns the annotated image path. Pure Pillow — no browser/device needed.
    """
    from PIL import Image, ImageDraw
    img = Image.open(screenshot_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for i, m in enumerate(marks, start=1):
        x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        draw.rectangle([x, y, x + w, y + h], outline=(255, 40, 40), width=3)
        label = f"{i}"
        draw.rectangle([x, max(0, y - 16), x + 14 + 8 * len(label), max(0, y - 16) + 18],
                       fill=(255, 40, 40))
        draw.text((x + 3, max(0, y - 15)), label, fill=(255, 255, 255))
    out = out_path or screenshot_path.rsplit(".", 1)[0] + "-marks.png"
    img.save(out)
    return out


def screen_marks(device: str = "browser") -> str:
    """Set-of-Marks: screenshot + numbered boxes on every clickable element.

    Look at the returned image with look_at_image(), then act by number —
    'element #7' beats guessing pixel coordinates. Far more reliable.
    """
    if device == "browser":
        shot = _browser.browser_screenshot()  # "Screenshot saved to <path> — ..."
        screenshot_path = shot.split("saved to ")[1].split(" ")[0].rstrip("—").strip()
        marks = _browser._get_page().evaluate(_JS_MARKS)
    elif device == "mobile":
        shot = _mobile.mobile_screenshot()
        screenshot_path = shot.split("saved to ")[1].split(" ")[0].rstrip("—").strip()
        marks = []
        for e in _mobile_tree():
            rect = _bounds_rect(e.get("bounds", ""))
            if rect and e.get("text"):
                marks.append({"text": e["text"],
                              "x": rect[0], "y": rect[1], "w": rect[2], "h": rect[3]})
    else:
        return f"ERROR: device must be 'browser' or 'mobile', got '{device}'"
    if not marks:
        return ("No interactive elements found to mark. Take a fresh screenshot "
                "(browser_screenshot / mobile_screenshot) and look at it directly.")
    annotated = _annotate(screenshot_path, marks[:40])
    lines = [f"#{i}: {m['text']}" for i, m in enumerate(marks[:40], start=1)]
    return (f"Set-of-Marks image saved to {annotated} — look_at_image it, then "
            f"act on elements BY NUMBER:\n" + "\n".join(lines))


def screen_elements(device: str = "browser") -> str:
    if device == "browser":
        elements = _browser._get_page().evaluate(_JS_EXTRACT)
        if not elements:
            return "No interactive elements found on the page."
        lines = [f"- <{e['tag']}> {e['text'] or e['sel']}"
                 + (f"  (selector: {e['sel']})" if e["sel"] else "")
                 for e in elements]
        return f"Browser screen ({len(lines)} elements):\n" + "\n".join(lines[:60])

    if device == "mobile":
        elements = _mobile_tree()
        if not elements:
            return "No elements found — is a device connected?"
        lines = [f"- <{e['tag']}> {e['text']}  at ({e['center'][0]},{e['center'][1]})"
                 for e in elements]
        return f"Phone screen ({len(lines)} elements):\n" + "\n".join(lines[:60])

    return f"ERROR: device must be 'browser' or 'mobile', got '{device}'"


def find_element(text: str, device: str = "browser") -> str:
    """Locate elements whose text matches (case-insensitive substring)."""
    needle = text.strip().lower()
    if not needle:
        return "ERROR: text is required."
    hits = []

    if device == "browser":
        for e in _browser._get_page().evaluate(_JS_EXTRACT):
            if needle in e["text"].lower():
                hits.append(f"- <{e['tag']}> {e['text']}"
                            + (f"  (selector: {e['sel']})" if e["sel"] else ""))
    elif device == "mobile":
        for e in _mobile_tree():
            if needle in e["text"].lower():
                hits.append(f"- {e['text']} at ({e['center'][0]},{e['center'][1]})")
    else:
        return f"ERROR: device must be 'browser' or 'mobile', got '{device}'"

    if not hits:
        return (f"No element matching '{text}' on the {device} screen. "
                f"Call screen_elements(device='{device}') to see what IS there.")
    return f"Found {len(hits)} match(es) for '{text}':\n" + "\n".join(hits[:15])


def locate(text: str, device: str) -> list[dict]:
    """Internal helper for the universal toolset: matches with coordinates."""
    needle = text.strip().lower()
    if device == "mobile":
        return [e for e in _mobile_tree() if needle in e["text"].lower()]
    return []


TOOLS = {
    "screen_marks": (screen_marks, {
        "type": "function",
        "function": {
            "name": "screen_marks",
            "description": (
                "Set-of-Marks: take a screenshot and draw NUMBERED boxes on every "
                "interactive element (browser DOM or phone UI). Look at the image, then "
                "act by element number/text instead of guessing pixel coordinates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "enum": ["browser", "mobile"]},
                },
            },
        },
    }),
    "screen_elements": (screen_elements, {
        "type": "function",
        "function": {
            "name": "screen_elements",
            "description": (
                "Get a structured list of interactive elements on the current screen "
                "(buttons, inputs, links, menus) — browser DOM or Android UI tree. "
                "Prefer this over raw screenshots for finding what to click."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "enum": ["browser", "mobile"],
                               "description": "Which screen to read (default browser)"},
                },
            },
        },
    }),
    "find_element": (find_element, {
        "type": "function",
        "function": {
            "name": "find_element",
            "description": "Find an element by its visible text and report where it is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "device": {"type": "string", "enum": ["browser", "mobile"]},
                },
                "required": ["text"],
            },
        },
    }),
}
