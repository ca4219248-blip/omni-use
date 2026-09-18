"""Operator console — human control over the agent.

Telegram mode (long polling; run in a terminal or as a service):

    python -m omniuse.operator

    /stop [reason]        engage the killswitch — halts the agent immediately
    /resume               disengage the killswitch
    /resolve [note]      resolve the pending escalation so the task can continue
    /approve <tool>       approve a confirm-gated tool (e.g. wallet_send)
    /revoke <tool>        revoke that approval
    /status               killswitch + escalation status

One-shot CLI (no Telegram needed):

    python -m omniuse.operator stop|resume|resolve|approve <tool>|revoke <tool>|status
"""

from __future__ import annotations

import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from omniuse import config, permissions as _permissions
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch


def _telegram_send(text: str) -> None:
    token, chat = config.telegram_bot_token(), config.telegram_chat_id()
    if not token or not chat:
        print("Telegram not configured — set OMNIUSE_TELEGRAM_BOT_TOKEN / _CHAT_ID.")
        return
    data = urlencode({"chat_id": chat, "text": text}).encode()
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    urlopen(req, timeout=30).read()


def _handle(message: str) -> str:
    cmd, _, rest = message.partition(" ")
    cmd = cmd.lower().strip()
    if cmd == "/stop":
        return _killswitch.engage(rest.strip() or "operator /stop")
    if cmd == "/resume":
        return _killswitch.disengage()
    if cmd == "/resolve":
        return _escalate.resolve(rest.strip() or "resolved via Telegram")
    if cmd == "/approve":
        return _permissions.approve(rest.strip())
    if cmd == "/revoke":
        return _permissions.revoke(rest.strip())
    if cmd == "/status":
        return (_killswitch.killswitch_status() + "\n" + _escalate.escalate_status())
    return "Unknown command. Use /stop, /resume, /resolve, /approve, /revoke or /status."


def run_cli(argv: list[str]) -> int:
    word = (argv[0] if argv else "status").lower()
    if word == "stop":
        out = _killswitch.engage("operator CLI")
    elif word == "resume":
        out = _killswitch.disengage()
    elif word == "resolve":
        out = _escalate.resolve("resolved via operator CLI")
    elif word == "approve" and len(argv) > 1:
        out = _permissions.approve(argv[1])
    elif word == "revoke" and len(argv) > 1:
        out = _permissions.revoke(argv[1])
    elif word == "status":
        out = _killswitch.killswitch_status() + "\n" + _escalate.escalate_status()
    else:
        out = "Usage: stop | resume | resolve | approve <tool> | revoke <tool> | status"
    print(out)
    return 0


def run_telegram() -> int:
    token = config.telegram_bot_token()
    if not token:
        print("Set OMNIUSE_TELEGRAM_BOT_TOKEN (and _CHAT_ID) to use Telegram mode.")
        return 1
    print("OmniUse operator daemon running — commands: /stop /resume /resolve /approve /revoke /status")
    offset = 0
    while True:
        try:
            req = Request(
                f"https://api.telegram.org/bot{token}/getUpdates?timeout=25&offset={offset}")
            updates = json.loads(urlopen(req, timeout=30).read()).get("result", [])
        except Exception as e:  # noqa: BLE001 — keep the daemon alive
            print("poll error:", e)
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            message = (update.get("message") or {}).get("text", "")
            if not message:
                continue
            try:
                reply = _handle(message)
            except Exception as e:  # noqa: BLE001
                reply = f"error: {e}"
            print(f"{message!r} -> {reply}")
            _telegram_send(reply)
        time.sleep(1)


def main() -> int:
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])
    return run_telegram()


if __name__ == "__main__":
    sys.exit(main())
