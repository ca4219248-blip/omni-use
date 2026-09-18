"""Universal computer control — one API, any device.

The agent says click('Start Race'), and OmniUse decides whether that means a
browser element (Playwright text/CSS locator) or a phone UI element (located
in the Android accessibility tree, then tapped). Device defaults to the last
one used; pass device='browser'/'mobile' to be explicit.

Philosophy: the AI shouldn't have to care WHICH machine it is using.
"""

from __future__ import annotations

from omniuse.tools import browser as _browser
from omniuse.tools import mobile as _mobile
from omniuse.tools import screen as _screen

_current_device = "browser"
DEVICES = ("browser", "mobile")


def _device(device: str | None) -> str:
    dev = (device or _current_device).strip().lower()
    if dev not in DEVICES:
        return ""  # caller reports the error
    return dev


def use_device(device: str) -> str:
    global _current_device
    dev = (device or "").strip().lower()
    if dev not in DEVICES:
        return f"ERROR: device must be one of {DEVICES}, got '{device}'"
    _current_device = dev
    return f"Current device: {dev}"


def click(target: str, device: str = "") -> str:
    """Click by visible text (preferred) or CSS selector, on any device."""
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        page = _browser._get_page()
        try:
            page.locator(f"text={target}").first.click(timeout=6_000)
            return f"Clicked '{target}' (browser, by text)"
        except Exception:
            try:
                page.click(target, timeout=6_000)
                return f"Clicked '{target}' (browser, by selector)"
            except Exception as e:
                return (f"Could not click '{target}' in the browser ({type(e).__name__}). "
                        "Call screen_elements(device='browser') to see what's actually there.")
    # mobile: locate by text in the accessibility tree, tap its center
    hits = _screen.locate(target, "mobile")
    if not hits:
        return (f"No element matching '{target}' on the phone screen. "
                "Call screen_elements(device='mobile') to see what's actually there.")
    x, y = hits[0]["center"]
    _mobile.mobile_tap(x, y)
    return f"Tapped '{target}' at ({x}, {y}) (mobile, by text)"


def type_text(text: str, into: str = "", device: str = "") -> str:
    """Type text — into a named field if given, else into whatever is focused."""
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        page = _browser._get_page()
        if into:
            try:
                page.locator(f"text={into}").first.click(timeout=6_000)
            except Exception:
                pass  # fall back to whatever has focus
        page.keyboard.type(text, delay=20)
        return f"Typed {len(text)} chars into the browser"
    _mobile.mobile_type(text)
    return f"Typed {len(text)} chars into the phone"


def scroll(direction: str = "down", amount: int = 700, device: str = "") -> str:
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        return _browser.browser_scroll(direction, amount)
    x1, x2 = 540, 540
    y1, y2 = (900, 200) if direction == "down" else (200, 900)
    return _mobile.mobile_swipe(x1, y1, x2, y2, 300)


def take_screenshot(device: str = "") -> str:
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        return _browser.browser_screenshot()
    return _mobile.mobile_screenshot()


def open_target(target: str, device: str = "") -> str:
    """Open a URL (browser) or launch an app by name (mobile)."""
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        return _browser.browser_open(target)
    name = target.strip().lower().replace(" ", "")
    packages = [p.split(":", 1)[1] for p in _mobile._shell("pm list packages").splitlines()]
    matches = [p for p in packages if name in p.lower()]
    if not matches:
        return (f"No installed app matches '{target}'. "
                "Call mobile_shell('pm list packages') to list what's installed.")
    _mobile._shell(f"monkey -p {matches[0]} -c android.intent.category.LAUNCHER 1")
    return f"Opened app {matches[0]}"


def drag(x1: int, y1: int, x2: int, y2: int, device: str = "") -> str:
    dev = _device(device)
    if not dev:
        return f"ERROR: device must be one of {DEVICES}"
    if dev == "browser":
        page = _browser._get_page()
        page.mouse.move(x1, y1)
        page.mouse.down()
        page.mouse.move(x2, y2, steps=12)
        page.mouse.up()
        return f"Dragged ({x1},{y1}) → ({x2},{y2}) in the browser"
    return _mobile.mobile_swipe(x1, y1, x2, y2, 600)


TOOLS = {
    "use_device": (use_device, {
        "type": "function",
        "function": {
            "name": "use_device",
            "description": "Set the current device ('browser' or 'mobile') for universal actions.",
            "parameters": {
                "type": "object",
                "properties": {"device": {"type": "string", "enum": ["browser", "mobile"]}},
                "required": ["device"],
            },
        },
    }),
    "click": (click, {
        "type": "function",
        "function": {
            "name": "click",
            "description": (
                "Universal click: by visible text (e.g. 'Start Race') or CSS selector. "
                "Works on the browser and the phone — no coordinates needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Visible text or CSS selector"},
                    "device": {"type": "string", "enum": ["browser", "mobile"],
                               "description": "Override the current device"},
                },
                "required": ["target"],
            },
        },
    }),
    "type_text": (type_text, {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Universal typing into the focused field (or the page).",
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
    "scroll": (scroll, {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Universal scroll (browser page or phone screen).",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "amount": {"type": "integer"},
                    "device": {"type": "string", "enum": ["browser", "mobile"]},
                },
            },
        },
    }),
    "take_screenshot": (take_screenshot, {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Universal screenshot of the current device's screen.",
            "parameters": {
                "type": "object",
                "properties": {"device": {"type": "string", "enum": ["browser", "mobile"]}},
            },
        },
    }),
    "open_target": (open_target, {
        "type": "function",
        "function": {
            "name": "open_target",
            "description": "Universal open: a URL in the browser, or an app by name on the phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "URL or app name"},
                    "device": {"type": "string", "enum": ["browser", "mobile"]},
                },
                "required": ["target"],
            },
        },
    }),
    "drag": (drag, {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "Universal drag from one point to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "device": {"type": "string", "enum": ["browser", "mobile"]},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        },
    }),
}
