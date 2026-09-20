"""Tool registry.

Each toolset module exposes a TOOLS dict:

    TOOLS = { "tool_name": (callable, json_schema_for_function_calling), ... }
The schema format is the OpenAI function-calling format. Plugins in
plugins/*/ are loaded the same way — see omniuse/plugins/.
"""

from __future__ import annotations

import json

from omniuse import config
from omniuse.tools import browser, escalate, killswitch, memory, mobile, policy, system, team, vision, wallet
from omniuse.tools import design, ideas, payments, remote, screen, shop, universal
from omniuse.tools import text, files, media, csvdata, notes, qr, speech

TOOLSETS: dict[str, dict] = {
    "browser": browser.TOOLS,
    "mobile": mobile.TOOLS,
    "system": system.TOOLS,
    "vision": vision.TOOLS,
    "policy": policy.TOOLS,
    "wallet": wallet.TOOLS,
    "escalate": escalate.TOOLS,
    "memory": memory.TOOLS,
    "killswitch": killswitch.TOOLS,
    "screen": screen.TOOLS,
    "universal": universal.TOOLS,
    "remote": remote.TOOLS,
    "team": team.TOOLS,
    "design": design.TOOLS,
    "payments": payments.TOOLS,
    "shop": shop.TOOLS,
    "ideas": ideas.TOOLS,
    "text": text.TOOLS,
    "files": files.TOOLS,
    "media": media.TOOLS,
    "csvdata": csvdata.TOOLS,
    "notes": notes.TOOLS,
    "qr": qr.TOOLS,
    "speech": speech.TOOLS,
}

# ---- plugins (loaded from plugins/ — see omniuse/plugins/__init__.py) ----
try:
    from pathlib import Path as _Path

    from omniuse import permissions as _permissions
    from omniuse.plugins import load_plugins, plugin_rules

    for _name, _tools in load_plugins(config.plugins_dir()).items():
        TOOLSETS[_name] = _tools
    # enforce permissions declared in plugin manifests, just like built-ins
    for _manifest in _Path(config.plugins_dir()).glob("*/plugin.json"):
        _permissions.register_rules(plugin_rules(_manifest))
except Exception as _e:  # noqa: BLE001 — plugins must never break the agent
    print(f"[plugins] loader failed: {_e}")

_ALL_TOOLS: dict[str, tuple] = {}
for _tools in TOOLSETS.values():
    _ALL_TOOLS.update(_tools)


def get_tool_schemas(toolsets: list[str] | None = None) -> list[dict]:
    """OpenAI-style schemas for the selected toolsets (None = all)."""
    if toolsets is None:
        return [schema for _, schema in _ALL_TOOLS.values()]
    schemas = []
    for name in toolsets:
        name = (name or "").strip().lower()
        if not name:
            continue
        if name not in TOOLSETS:
            raise ValueError(
                f"Unknown toolset '{name}'. Available: {sorted(TOOLSETS)}"
            )
        schemas += [schema for _, schema in TOOLSETS[name].values()]
    return schemas


def run_tool(name: str, arguments: dict):
    """Execute a tool by name and return its result."""
    if name not in _ALL_TOOLS:
        return f"ERROR: unknown tool '{name}'. Available: {sorted(_ALL_TOOLS)}"
    fn, _ = _ALL_TOOLS[name]
    if not isinstance(arguments, dict):
        return f"ERROR: arguments must be a JSON object, got: {json.dumps(arguments)}"
    return fn(**arguments)
