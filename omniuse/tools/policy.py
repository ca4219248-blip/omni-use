"""Policy toolset — check the rules before acting on any platform.

The agent MUST call policy_check() before its first action on any new
platform/app, and record what it learns with policy_record(). Stances live
in a local JSON registry so they persist across runs.

NON-NEGOTIABLE RULES enforced everywhere in OmniUse:
  1. Disclose you are an AI wherever you create an account or post content.
  2. No fake engagement (followers, reviews, upvotes, likes, comments).
  3. No spam or bulk unsolicited messages.
  4. No misleading financial claims.
  5. Comply with each platform's automation rules — check first, act second.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config

STANCES = ("allows_automation", "restricted", "forbids_automation", "unknown")

RULES = [
    "Disclose you are an AI wherever you create an account or post content.",
    "No fake engagement: no fake followers, reviews, upvotes, likes or comments.",
    "No spam: no mass-DMs, unsolicited bulk posting, or repetitive content.",
    "No misleading financial claims: no guaranteed-return or get-rich promises.",
    "Comply with each platform's automation rules — check first, act second.",
]

# Seed entries are UNVERIFIED reminders — the operator must confirm each
# platform's current terms before the agent relies on them.
SEED = {
    "x.com": {"stance": "restricted", "verified": False,
              "notes": "Automation allowed under X's automation rules; automated "
                       "accounts must be labelled. VERIFY current rules first."},
    "reddit.com": {"stance": "restricted", "verified": False,
                   "notes": "Bots must be disclosed and often need moderator "
                            "approval; API use requires registration. VERIFY."},
    "youtube.com": {"stance": "restricted", "verified": False,
                   "notes": "Uploads via the official API are OK; any fake "
                            "engagement is strictly prohibited. VERIFY."},
    "upwork.com": {"stance": "forbids_automation", "verified": False,
                   "notes": "Automated applications and scraping are prohibited "
                            "by the ToS. VERIFY."},
    "fiverr.com": {"stance": "forbids_automation", "verified": False,
                   "notes": "Automated actions and scraping are prohibited by "
                            "the ToS. VERIFY."},
}


def _registry_path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "platform_policies.json"


def _load() -> dict:
    p = _registry_path()
    if not p.exists():
        p.write_text(json.dumps(SEED, indent=2), encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(registry: dict) -> None:
    _registry_path().write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _normalize(platform: str) -> str:
    p = platform.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p.split("/")[0]


def policy_rules() -> str:
    return "NON-NEGOTIABLE RULES:\n" + "\n".join(
        f"{i}. {r}" for i, r in enumerate(RULES, 1))


def policy_check(platform: str) -> str:
    entry = _load().get(_normalize(platform))
    if not entry:
        return (f"No policy recorded for '{platform}'. You MUST record its stance with "
                f"policy_record(platform, stance, notes) before your first action there. "
                f"If you cannot determine it, use escalate_to_operator().\n\n{policy_rules()}")
    verdict = {
        "allows_automation": "Automation is allowed — proceed, following the rules below.",
        "restricted": "Automation is RESTRICTED — act only within the platform's stated conditions.",
        "forbids_automation": "Automation is NOT allowed — do NOT act on this platform; report back instead.",
        "unknown": "Stance unknown — do not act until the operator records a verified stance.",
    }[entry["stance"]]
    return (f"{platform}: {entry['stance']} (verified: {entry['verified']})\n"
            f"notes: {entry['notes']}\n{verdict}\n\n{policy_rules()}")


def policy_record(platform: str, stance: str, notes: str, verified: bool = False) -> str:
    if stance not in STANCES:
        return f"ERROR: stance must be one of {STANCES}"
    registry = _load()
    registry[_normalize(platform)] = {"stance": stance, "verified": verified,
                                      "notes": notes, "recorded_at": time.time()}
    _save(registry)
    return f"Recorded {platform} → {stance} (verified: {verified})"


def status_for_host(host: str):
    """Helper for other toolsets: the recorded stance for a host, or None."""
    return _load().get(_normalize(host))


TOOLS = {
    "policy_rules": (policy_rules, {
        "type": "function",
        "function": {
            "name": "policy_rules",
            "description": "Return the non-negotiable rules the agent must always follow.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "policy_check": (policy_check, {
        "type": "function",
        "function": {
            "name": "policy_check",
            "description": (
                "Check a platform/app's recorded stance on bots/automation. "
                "MUST be called before the first action on any new platform."
            ),
            "parameters": {
                "type": "object",
                "properties": {"platform": {"type": "string", "description": "Domain or app name, e.g. 'x.com'"}},
                "required": ["platform"],
            },
        },
    }),
    "policy_record": (policy_record, {
        "type": "function",
        "function": {
            "name": "policy_record",
            "description": "Record a platform's stance on automation so future runs can check it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "stance": {"type": "string", "enum": list(STANCES)},
                    "notes": {"type": "string", "description": "What the platform allows/prohibits and where you learned it"},
                    "verified": {"type": "boolean", "description": "True only if the operator confirmed the current ToS"},
                },
                "required": ["platform", "stance", "notes"],
            },
        },
    }),
}
