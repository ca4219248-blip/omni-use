"""Remote body — run tools on a distant OmniUse Hub.

The AI brain can live anywhere (cloud, another machine); as long as it can
reach a device running `python -m omniuse.hub`, it gets hands there:

    🧠 AI (anywhere) ──HTTP──▶ 🦾 OmniUse Hub ──▶ 📱💻🖥️ local tools

Every hub call goes through the same permission system as local calls.
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from omniuse import config


def _hub(hub_url: str | None) -> str:
    return hub_url or config.hub_url()


def _post(url: str, payload: dict, token: str) -> dict:
    req = Request(url, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json",
                           "Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def remote_status(hub_url: str = "") -> str:
    url = _hub(hub_url)
    if not url:
        return "ERROR: no hub configured — set OMNIUSE_HUB_URL."
    try:
        with urlopen(f"{url.rstrip('/')}/status", timeout=30) as r:
            data = json.loads(r.read())
        return (f"Hub {url} is up — {data.get('toolsets')} toolsets, "
                f"version {data.get('version')}")
    except Exception as e:  # noqa: BLE001
        return f"Hub unreachable: {e}"


def remote_run(tool: str, arguments: dict | None = None, hub_url: str = "") -> str:
    url = _hub(hub_url)
    if not url:
        return "ERROR: no hub configured — set OMNIUSE_HUB_URL."
    token = config.hub_token()
    if not token:
        return "ERROR: OMNIUSE_HUB_TOKEN is not set (it must match the hub's token)."
    try:
        data = _post(f"{url.rstrip('/')}/run",
                     {"tool": tool, "arguments": arguments or {}}, token)
    except Exception as e:  # noqa: BLE001
        return f"Remote call failed: {e}"
    if not data.get("ok"):
        return f"REMOTE ERROR: {data.get('error')}"
    return str(data.get("result"))


TOOLS = {
    "remote_status": (remote_status, {
        "type": "function",
        "function": {
            "name": "remote_status",
            "description": "Check whether the configured OmniUse Hub (remote body) is reachable.",
            "parameters": {
                "type": "object",
                "properties": {"hub_url": {"type": "string", "description": "Override OMNIUSE_HUB_URL"}},
            },
        },
    }),
    "remote_run": (remote_run, {
        "type": "function",
        "function": {
            "name": "remote_run",
            "description": (
                "Run a tool on the remote machine running OmniUse Hub — the agent's "
                "distant body. Same tools as local, same permissions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "description": "Tool name, e.g. 'browser_open'"},
                    "arguments": {"type": "object", "description": "Arguments for the tool"},
                    "hub_url": {"type": "string", "description": "Override OMNIUSE_HUB_URL"},
                },
                "required": ["tool"],
            },
        },
    }),
}
