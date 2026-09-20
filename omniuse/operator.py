"""Operator console — human control over the agent, terminal only.

Interactive console (run in a terminal):

    python -m omniuse.operator

    stop [reason]        engage the killswitch — halts the agent immediately
    resume               disengage the killswitch
    resolve [note]       resolve the pending escalation so the task can continue
    approve <tool>       approve a confirm-gated tool (e.g. wallet_send)
    revoke <tool>        revoke that approval
    status               killswitch + escalation status
    orders               list shop orders (design shop pipeline)
    paid <order_id>      YOU confirming a payment arrived — marks the order paid
                         so the agent can deliver the final design
    say <anything else>  run it as an agent task (voice transcription routes here too)

    quit                 exit the console

One-shot CLI (same commands, no REPL):

    python -m omniuse.operator stop|resume|resolve|approve <tool>|revoke <tool>|
                                status|orders|paid <order_id>|say "task text"

Voice: `python -m omniuse.voice` listens and routes here / to the agent.
"""

from __future__ import annotations

import sys

from omniuse import config, permissions as _permissions
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch

COMMAND_WORDS = ("stop", "resume", "resolve", "approve", "revoke", "status",
                 "orders", "paid", "help", "quit", "exit")


def _orders() -> str:
    from omniuse.tools import payments as _payments
    return _payments.order_status()


def _paid(order_id: str) -> str:
    from omniuse.tools import payments as _payments
    return _payments.order_mark_paid(order_id, operator_token=config.operator_token())


def handle(line: str) -> str | None:
    """Route one console line. Returns None if it's not a command
    (the caller may then run it as an agent task)."""
    text = line.strip()
    if not text:
        return ""
    if text.lower() in ("quit", "exit"):
        raise SystemExit(0)
    cmd, _, rest = text.partition(" ")
    cmd = cmd.lower().lstrip("/").strip()
    if cmd not in COMMAND_WORDS and not text.startswith("/"):
        return None  # free text → agent task
    if cmd == "stop":
        return _killswitch.engage(rest.strip() or "operator console")
    if cmd == "resume":
        return _killswitch.disengage()
    if cmd == "resolve":
        return _escalate.resolve(rest.strip() or "resolved via console")
    if cmd == "approve":
        return _permissions.approve(rest.strip())
    if cmd == "revoke":
        return _permissions.revoke(rest.strip())
    if cmd == "status":
        return (_killswitch.killswitch_status() + "\n" + _escalate.escalate_status())
    if cmd == "orders":
        return _orders()
    if cmd == "paid":
        order_id = rest.strip()
        if not order_id:
            return "Usage: paid <order_id> — run orders first to see the ids."
        return _paid(order_id)
    if cmd == "help":
        return __doc__.split("Interactive console")[1].split("Voice:")[0].strip()
    return None  # unknown word → treat as free text


def run_task(text: str) -> str:
    """Run a free-text line as an agent task."""
    from omniuse import Agent
    return Agent().run(text)  # all toolsets, default step cap


def run_cli(argv: list[str]) -> int:
    word = (argv[0] if argv else "").lower()
    if word == "say":
        if len(argv) < 2:
            print("Usage: say <task text>")
            return 1
        print(run_task(" ".join(argv[1:])))
        return 0
    out = handle(" ".join(argv))
    if out is None:
        print(run_task(" ".join(argv)))
        return 0
    print(out)
    return 0


def run_console() -> int:
    print("OmniUse operator console — type a command, or anything else to run it "
          "as a task. help for commands, quit to exit.")
    while True:
        try:
            line = input("\nomniuse> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            out = handle(line)
        except SystemExit:
            break
        if out is None:
            if not line:
                continue
            print(run_task(line))
        elif out:
            print(out)
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])
    return run_console()


if __name__ == "__main__":
    sys.exit(main())
