"""Browser toolset — drive a real Chromium browser via Playwright.

Setup:
    pip install playwright
    playwright install chromium

Set OMNIUSE_HEADLESS=0 to actually watch the browser.
Set OMNIUSE_PROFILE_DIR to a folder to keep a persistent profile — logins,
cookies and storage then survive across runs.
"""

from __future__ import annotations

import os
import time
from urllib.parse import quote_plus

from omniuse import config

_pw = None
_browser = None
_context = None
_page = None


def _get_page():
    global _pw, _browser, _context, _page
    if _page is None:
        from playwright.sync_api import sync_playwright

        _pw = sync_playwright().start()
        profile = os.getenv("OMNIUSE_PROFILE_DIR", "")
        if profile:
            # persistent profile → logins, cookies and storage survive restarts
            _context = _pw.chromium.launch_persistent_context(
                profile, headless=config.headless_browser(),
                viewport={"width": 1280, "height": 800})
            _page = _context.pages[0] if _context.pages else _context.new_page()
        else:
            _browser = _pw.chromium.launch(headless=config.headless_browser())
            _context = _browser.new_context(viewport={"width": 1280, "height": 800})
            _page = _context.new_page()
    return _page


def _all_pages():
    if _context is not None:
        return _context.pages
    return [_page] if _page is not None else []


# ---------------------------------------------------------------- actions


def browser_open(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _get_page()
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    return f"Opened {url}\nTitle: {page.title()}"


def browser_search(query: str) -> str:
    return browser_open("https://duckduckgo.com/html/?q=" + quote_plus(query))


def browser_click(selector: str) -> str:
    page = _get_page()
    page.click(selector, timeout=10_000)
    page.wait_for_load_state("domcontentloaded")
    return f"Clicked {selector}"


def browser_type(selector: str, text: str, press_enter: bool = False) -> str:
    page = _get_page()
    page.fill(selector, text, timeout=10_000)
    if press_enter:
        page.press(selector, "Enter")
        page.wait_for_load_state("domcontentloaded")
    return f"Typed into {selector}" + (" and pressed Enter" if press_enter else "")


def browser_scroll(direction: str = "down", amount: int = 700) -> str:
    page = _get_page()
    dy = amount if direction == "down" else -amount
    page.mouse.wheel(0, dy)
    page.wait_for_timeout(400)
    return f"Scrolled {direction} by {amount}px"


def browser_back() -> str:
    _get_page().go_back(wait_until="domcontentloaded")
    return "Went back"


def browser_screenshot() -> str:
    path = os.path.join(config.screenshots_dir(), f"browser_{int(time.time())}.png")
    _get_page().screenshot(path=path, full_page=False)
    return f"Screenshot saved to {path} — use look_at_image(path) to see it."


# ---------------------------------------------------------------- reading


def browser_text(selector: str = "body", max_chars: int = 4000) -> str:
    page = _get_page()
    text = page.inner_text(selector) or "(empty)"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text


def browser_links(max_links: int = 20) -> str:
    page = _get_page()
    links = page.eval_on_selector_all(
        "a[href]",
        "els => els.slice(0, 300).map(e => [e.innerText.trim(), e.href])",
    )
    lines = [f"- {text or '(no text)'} -> {href}" for text, href in links if text]
    if not lines:
        return "No links found."
    return "\n".join(lines[:max_links])


def browser_url() -> str:
    page = _get_page()
    return f"URL: {page.url}\nTitle: {page.title()}"


def browser_wait_for(text: str, timeout: int = 10) -> str:
    _get_page().wait_for_selector(f"text={text}", timeout=max(1, timeout) * 1000)
    return f"'{text}' appeared on the page."


def browser_tabs() -> str:
    pages = _all_pages()
    if not pages:
        return "No open tabs."
    return "\n".join(f"{i}: {p.url}" for i, p in enumerate(pages))


def browser_switch_tab(index: int = 0) -> str:
    global _page
    pages = _all_pages()
    if not pages or not (0 <= int(index) < len(pages)):
        return f"ERROR: tab index out of range (0-{max(0, len(pages) - 1)})."
    _page = pages[int(index)]
    try:
        _page.bring_to_front()
    except Exception:
        pass
    return f"Switched to tab {index}: {_page.url}"


def browser_eval(js: str) -> str:
    if not js.strip():
        return "ERROR: js is required."
    try:
        result = _get_page().evaluate(js)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    text = repr(result)
    return text[:4000] if len(text) > 4000 else text or "(undefined)"


# ---------------------------------------------------------------- registry

TOOLS = {
    "browser_open": (browser_open, {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "Open a URL in the browser and return the page title.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL, e.g. example.com"}},
                "required": ["url"],
            },
        },
    }),
    "browser_search": (browser_search, {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Search the web (DuckDuckGo) and return the results page.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }),
    "browser_click": (browser_click, {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element using a CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {"selector": {"type": "string", "description": "CSS selector, e.g. 'a.login' or '#search button'"}},
                "required": ["selector"],
            },
        },
    }),
    "browser_type": (browser_type, {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text into a form field (clears it first).",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input"},
                    "text": {"type": "string"},
                    "press_enter": {"type": "boolean", "description": "Press Enter after typing"},
                },
                "required": ["selector", "text"],
            },
        },
    }),
    "browser_scroll": (browser_scroll, {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the page up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "amount": {"type": "integer", "description": "Pixels (default 700)"},
                },
            },
        },
    }),
    "browser_back": (browser_back, {
        "type": "function",
        "function": {
            "name": "browser_back",
            "description": "Go back to the previous page.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "browser_screenshot": (browser_screenshot, {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current page and save it to disk.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "browser_text": (browser_text, {
        "type": "function",
        "function": {
            "name": "browser_text",
            "description": "Read the visible text of the page (or of one element).",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (default whole body)"},
                    "max_chars": {"type": "integer", "description": "Truncation limit (default 4000)"},
                },
            },
        },
    }),
    "browser_links": (browser_links, {
        "type": "function",
        "function": {
            "name": "browser_links",
            "description": "List the visible links (text + URL) on the current page.",
            "parameters": {
                "type": "object",
                "properties": {"max_links": {"type": "integer", "description": "Default 20"}},
            },
        },
    }),
    "browser_url": (browser_url, {
        "type": "function",
        "function": {
            "name": "browser_url",
            "description": "Get the current page's URL and title.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "browser_wait_for": (browser_wait_for, {
        "type": "function",
        "function": {
            "name": "browser_wait_for",
            "description": "Wait until text appears on the page (e.g. after a click loads something).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Seconds (default 10)"},
                },
                "required": ["text"],
            },
        },
    }),
    "browser_tabs": (browser_tabs, {
        "type": "function",
        "function": {
            "name": "browser_tabs",
            "description": "List the open browser tabs.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "browser_switch_tab": (browser_switch_tab, {
        "type": "function",
        "function": {
            "name": "browser_switch_tab",
            "description": "Switch the active browser tab by index (see browser_tabs).",
            "parameters": {
                "type": "object",
                "properties": {"index": {"type": "integer"}},
            },
        },
    }),
    "browser_eval": (browser_eval, {
        "type": "function",
        "function": {
            "name": "browser_eval",
            "description": "Run JavaScript in the current page and return the result.",
            "parameters": {
                "type": "object",
                "properties": {"js": {"type": "string", "description": "JavaScript expression to evaluate"}},
                "required": ["js"],
            },
        },
    }),
}
