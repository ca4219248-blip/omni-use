"""Mobile toolset — control an Android phone over ADB (USB or Wi-Fi).

Setup:
    1. Install the `adb` tool (Android platform-tools).
    2. On the phone: Settings → About phone → tap "Build number" 7 times,
       then Settings → Developer options → enable USB debugging.
    3. Connect via USB and accept the debugging prompt on the phone.

Everything here runs plain `adb` commands, so it works on Linux, macOS and Windows.
"""

from __future__ import annotations

import os
import subprocess
import time

from omniuse import config

_KEYCODES = {
    "back": 4, "home": 3, "enter": 66, "tab": 61, "escape": 111,
    "delete": 67, "volume_up": 24, "volume_down": 25, "power": 26,
}

def _adb(*args: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["adb", *args], capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        raise RuntimeError("`adb` not found. Install Android platform-tools first.")
    if result.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.strip()}")
    return (result.stdout or "").strip()

def _shell(command: str, timeout: int = 30) -> str:
    return _adb("shell", command, timeout=timeout)


# ---------------------------------------------------------------- tools


def mobile_devices() -> str:
    return _adb("devices") or "No devices found."

def mobile_connect(ip_port: str) -> str:
    """Connect to a phone over WiFi (wireless ADB) — no USB cable needed.

    On the phone: Developer options → Wireless debugging → Pair/enable, then
    pass the ip:port shown there (or run `adb pair` once on this machine).
    On the phone itself (Termux): pkg install adb works too.
    """
    target = (ip_port or "").strip()
    if not target or ":" not in target:
        return "ERROR: give the phone's ip:port, e.g. 192.168.1.5:5555"
    out = _adb("connect", target)
    if "connected" not in out.lower():
        return (f"Could not connect to {target} ({out}). Enable Wireless debugging "
                "on the phone (Developer options) and try again; `adb pair` may "
                "be needed first.")
    return f"Connected to {target}. mobile_devices / screen_elements(device='mobile') now work over WiFi."


def mobile_tap(x: int, y: int) -> str:
    _shell(f"input tap {int(x)} {int(y)}")
    return f"Tapped ({x}, {y})"


def mobile_swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    _shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")
    return f"Swiped ({x1},{y1}) → ({x2},{y2})"


def mobile_type(text: str) -> str:
    # Spaces must be escaped for `input text`.
    safe = text.replace(" ", "%s").replace("'", "")
    _shell(f"input text '{safe}'")
    return f"Typed: {text!r}"


def mobile_key(key: str) -> str:
    key = key.strip().lower()
    if key not in _KEYCODES:
        return f"ERROR: unknown key '{key}'. Available: {sorted(_KEYCODES)}"
    _shell(f"input keyevent {_KEYCODES[key]}")
    return f"Pressed {key}"


def mobile_screenshot() -> str:
    path = os.path.join(config.screenshots_dir(), f"mobile_{int(time.time())}.png")
    result = subprocess.run(
        ["adb", "exec-out", "screencap", "-p"],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.startswith(b"\x89PNG"):
        raise RuntimeError("Screenshot failed — is a device connected? (mobile_devices)")
    with open(path, "wb") as f:
        f.write(result.stdout)
    return f"Screenshot saved to {path} — use look_at_image(path) to see it."


def mobile_shell(command: str) -> str:
    out = _shell(command)
    return (out[:4000] + "\n...[truncated]") if len(out) > 4000 else out or "(no output)"


# ---------------------------------------------------------------- registry

TOOLS = {
    "mobile_devices": (mobile_devices, {
        "type": "function",
        "function": {
            "name": "mobile_devices",
            "description": "List the Android devices currently connected over ADB.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "mobile_connect": (mobile_connect, {
        "type": "function",
        "function": {
            "name": "mobile_connect",
            "description": ("Connect to an Android phone over WiFi (wireless ADB) — no USB "
                            "cable needed. Give the ip:port from Developer options → Wireless "
                            "debugging."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ip_port": {"type": "string", "description": "e.g. 192.168.1.5:5555"},
                },
                "required": ["ip_port"],
            },
        },
    }),
    "mobile_tap": (mobile_tap, {
        "type": "function",
        "function": {
            "name": "mobile_tap",
            "description": "Tap the phone screen at pixel coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    }),
    "mobile_swipe": (mobile_swipe, {
        "type": "function",
        "function": {
            "name": "mobile_swipe",
            "description": "Swipe from one point to another (scroll, open drawer, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "duration_ms": {"type": "integer", "description": "Default 300"},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        },
    }),
    "mobile_type": (mobile_type, {
        "type": "function",
        "function": {
            "name": "mobile_type",
            "description": "Type text into the currently focused field on the phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    }),
    "mobile_key": (mobile_key, {
        "type": "function",
        "function": {
            "name": "mobile_key",
            "description": "Press a hardware/nav key: back, home, enter, tab, escape, delete, volume_up, volume_down, power.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                },
                "required": ["key"],
            },
        },
    }),
    "mobile_screenshot": (mobile_screenshot, {
        "type": "function",
        "function": {
            "name": "mobile_screenshot",
            "description": "Take a screenshot of the phone screen and save it to disk.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "mobile_shell": (mobile_shell, {
        "type": "function",
        "function": {
            "name": "mobile_shell",
            "description": "Run an arbitrary `adb shell` command on the phone (e.g. 'dumpsys battery', 'pm list packages').",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    }),
}
