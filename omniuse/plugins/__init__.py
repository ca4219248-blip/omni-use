"""Plugin SDK — add a toolset by dropping a folder in plugins/.

    plugins/
      my_tool/
        plugin.json   ← {"name": "my_tool", "description": "...", "permissions": {"risky": "confirm"}}
        main.py       ← TOOLS = {"risky": (fn, schema), ...}   (same format as built-ins)

The loader picks the folder up automatically on the next run; tools appear
under the plugin's name in the toolset registry, and any permissions declared
in the manifest are enforced just like built-in rules.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_plugins(plugins_dir: str) -> dict[str, dict]:
    """Scan a plugins folder and return {plugin_name: TOOLS}.

    Broken plugins are skipped (with a printed warning), never fatal.
    """
    found: dict[str, dict] = {}
    root = Path(plugins_dir)
    if not root.is_dir():
        return found

    for manifest_path in sorted(root.glob("*/plugin.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = manifest["name"].strip().lower().replace(" ", "_")
            entry = manifest_path.parent / (manifest.get("entry", "main.py"))
            if not entry.is_file():
                print(f"[plugins] {manifest_path.parent.name}: missing {entry.name}, skipped")
                continue

            spec = importlib.util.spec_from_file_location(f"omniuse_plugin_{name}", entry)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tools = getattr(module, "TOOLS", None)
            if not isinstance(tools, dict) or not tools:
                print(f"[plugins] {name}: no TOOLS dict, skipped")
                continue
            found[name] = tools
            print(f"[plugins] loaded {name} ({len(tools)} tools)")
        except Exception as e:  # noqa: BLE001 — a bad plugin must not kill the agent
            print(f"[plugins] {manifest_path.parent.name}: failed to load ({e})")
    return found


def plugin_rules(manifest_path: Path) -> list[dict]:
    """Permission rules declared in a plugin manifest."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return [{"tool": tool, "level": level}
                for tool, level in (manifest.get("permissions") or {}).items()]
    except (OSError, ValueError, KeyError):
        return []
