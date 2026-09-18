"""Tool registry.

Each toolset module exposes a TOOLS dict:

    TOOLS = { "tool_name": (callable, json_schema_for_function_calling), ... }

The schema format is the OpenAI function-calling format.
"""

from __future__ import annotations

import json

from omniuse.tools import browser, escalate, killswitch, memory, mobile, policy, system, vision, wallet

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
}

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
