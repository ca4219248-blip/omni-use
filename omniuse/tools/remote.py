"""Remote body — run tools on distant OmniUse Hubs, by name.

Register the machines you control:

    python -m omniuse.remote add pc1 http://192.168.1.20:8787 <token>
    python -m omniuse.remote list

Then the agent addresses them by name:

    remote_hubs()                              → which bodies exist
    remote_run("browser_open", {"url": ...}, hub="pc1")

An unnamed remote_run uses OMNIUSE_HUB_URL / OMNIUSE_HUB_TOKEN as before.
Every hub call goes through the same permission system as local calls.
The registry lives in data/hubs.json (tokens included — keep the data dir
private).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from omniuse import config


# ---------------------------------------------------------------- registry


def _registry_path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "hubs.json"


def _hubs() -> dict:
    p = _registry_path()
    return json.loads(p.read_text()) if p.exists() else {}


def _save_hubs(hubs: dict) -> None:
    _registry_path().write_text(json.dumps(hubs, indent=2))


def hub_add(name: str, url: str, token: str) -> str:
    name = name.strip().lower()
    if not name or not url.strip():
        return "ERROR: name and url are required."
    hubs = _hubs()
    hubs[name] = {"url": url.strip().rstrip("/"), "token": token.strip(),
                  "added": time.time()}
    _save_hubs(hubs)
    return f"Registered hub '{name}' → {url.strip()}"


def hub_remove(name: str) -> str:
    hubs = _hubs()
    if hubs.pop(name.strip().lower(), None) is None:
        return f"No hub named '{name}'."
    _save_hubs(hubs)
    return f"Removed hub '{name}'."


def remote_hubs() -> str:
    hubs = _hubs()
    lines = [f"- {n}: {h['url']}" for n, h in sorted(hubs.items())]
    if config.hub_url():
        lines.append(f"- (default): {config.hub_url()} (from OMNIUSE_HUB_URL)")
    return "\n".join(lines) or "No hubs registered — use `python -m omniuse.remote add <name> <url> <token>`."


# ---------------------------------------------------------------- calling


def _resolve(hub: str, hub_url: str):
    """Returns (url, token) or an error string."""
    if hub:
        entry = _hubs().get(hub.strip().lower())
        if not entry:
            return (f"ERROR: no hub named '{hub}'. Known: {sorted(_hubs())}")
        return entry["url"], entry["token"]
    url = hub_url or config.hub_url()
    if not url:
        return "ERROR: no hub configured — set OMNIUSE_HUB_URL or register hubs."
    token = config.hub_token()
    if not token:
        return "ERROR: OMNIUSE_HUB_TOKEN is not set (it must match the hub's token)."
    return url, token


def _post(url: str, payload: dict, token: str) -> dict:
    req = Request(url, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json",
                           "Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def remote_status(hub: str = "", hub_url: str = "") -> str:
    resolved = _resolve(hub, hub_url)
    if isinstance(resolved, str):
        return resolved
    url, token = resolved
    try:
        with urlopen(f"{url.rstrip('/')}/status", timeout=30) as r:
            data = json.loads(r.read())
        return (f"Hub {hub or url} is up — {data.get('toolsets')} toolsets, "
                f"version {data.get('version')}")
    except Exception as e:  # noqa: BLE001
        return f"Hub unreachable: {e}"


def remote_run(tool: str, arguments: dict | None = None,
               hub: str = "", hub_url: str = "") -> str:
    resolved = _resolve(hub, hub_url)
    if isinstance(resolved, str):
        return resolved
    url, token = resolved
    try:
        data = _post(f"{url.rstrip('/')}/run",
                     {"tool": tool, "arguments": arguments or {}}, token)
    except Exception as e:  # noqa: BLE001
        return f"Remote call failed: {e}"
    if not data.get("ok"):
        return f"REMOTE ERROR: {data.get('error')}"
    return str(data.get("result"))


TOOLS = {
    "remote_hubs": (remote_hubs, {
        "type": "function",
        "function": {
            "name": "remote_hubs",
            "description": "List the registered remote bodies (OmniUse Hubs) you can control.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "remote_status": (remote_status, {
        "type": "function",
        "function": {
            "name": "remote_status",
            "description": "Check whether a remote OmniUse Hub (body) is reachable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hub": {"type": "string", "description": "Registered hub name (optional)"},
                    "hub_url": {"type": "string", "description": "Direct URL override"},
                },
            },
        },
    }),
    "remote_run": (remote_run, {
        "type": "function",
        "function": {
            "name": "remote_run",
            "description": (
                "Run a tool on a remote machine running OmniUse Hub — the agent's "
                "distant body. Same tools as local, same permissions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "description": "Tool name, e.g. 'browser_open'"},
                    "arguments": {"type": "object", "description": "Arguments for the tool"},
                    "hub": {"type": "string", "description": "Registered hub name to run it on"},
                },
                "required": ["tool"],
            },
        },
    }),
}


# ---------------------------------------------------------------- CLI


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "add" and len(sys.argv) == 5:
        print(hub_add(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "remove" and len(sys.argv) == 3:
        print(hub_remove(sys.argv[2]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        print(remote_hubs())
    else:
        print("Usage: python -m omniuse.remote add <name> <url> <token> | list | remove <name>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
