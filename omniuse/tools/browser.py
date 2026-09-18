"""Browser toolset — drive a real Chromium browser via Playwright.

Setup:
    pip install playwright
    playwright install chromium

Set OMNIUSE_HEADLESS=0 to actually watch the browser.
"""

from __future__ import annotations

import os
import time
from urllib.parse import quote_plus

from omniuse import config

_pw = None
_browser = None
_page = None


def _get_page():
    global _pw, _browser, _page
    if _page is None:
        from playwright.sync_api import sync_playwright

        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=config.headless_browser())
        _page = _browser.new_page(viewport={"width": 1280, "height": 800})
    return _page


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
}
