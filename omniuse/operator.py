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
    improve             review past runs/errors/lessons → writes an improvement
                         plan; `improve apply` adds its behaviour rules to the
                         agent's profile (self-improvement)
    say <anything else>  run it as an agent task (voice transcription routes here too)

    quit                 exit the console

One-shot CLI (same commands, no REPL):

    python -m omniuse.operator stop|resume|resolve|approve <tool>|revoke <tool>|
                                status|orders|paid <order_id>|say "task text"

Voice: `python -m omniuse.voice` listens and routes here / to the agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from omniuse import config, permissions as _permissions
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch

COMMAND_WORDS = ("stop", "resume", "resolve", "approve", "revoke", "status",
                 "orders", "paid", "improve", "help", "quit", "exit")

def _orders() -> str:
    from omniuse.tools import payments as _payments
    return _payments.order_status()

def _paid(order_id: str) -> str:
    from omniuse.tools import payments as _payments
    return _payments.order_mark_paid(order_id, operator_token=config.operator_token())


def _improve(apply: bool = False) -> str:
    """Self-improvement review: learn from past runs, errors and lessons.

    `improve`        → reviews history, writes data/improvement-plan.md
    `improve apply`  → also appends the plan's behaviour rules to
                       data/agent-profile.md (injected into every future task)
    """
    from omniuse.llm import chat
    from omniuse.tools import memory as _memory
    runs = _memory.recent_runs(10)
    lessons = _memory.lessons(30)
    errors = [e for e in _memory._entries()
              if e.get("kind") == "tool_call"
              and str(e.get("result", "")).startswith(("ERROR", "REFUSED"))][-30:]
    if not runs and not lessons and not errors:
        return ("Nothing to learn from yet — run some tasks first, then the agent "
                "can review its own history and improve.")
    material = json.dumps(
        {"recent_runs": runs, "lessons": lessons,
         "recent_errors": [{"tool": e.get("tool"), "result": str(e.get("result", ""))[:200]}
                           for e in errors]},
        indent=1, ensure_ascii=False)
    system = (
        "You review an AI agent's work history and propose concrete self-improvements. "
        "Reply in markdown with exactly these sections:\n"
        "## Patterns noticed\n(what worked, what kept failing)\n"
        "## Behaviour rules to add\n(each rule one imperative sentence, 3-8 rules — "
        "these get injected into the agent's system prompt)\n"
        "## Bigger changes to propose\n(for the human developer to implement by hand)"
    )
    try:
        msg = chat([{"role": "system", "content": system},
                    {"role": "user", "content": material[:8000]}], fast=True)
        plan = (msg.get("content") or "").strip()
    except Exception as e:  # noqa: BLE001
        return f"ERROR: improvement review failed ({e})."
    if not plan:
        return "ERROR: the review came back empty."
    data_dir = Path(config.data_dir())
    data_dir.mkdir(parents=True, exist_ok=True)
    plan_path = data_dir / "improvement-plan.md"
    plan_path.write_text(plan, encoding="utf-8")
    if not apply:
        return (f"Improvement plan written to {plan_path}. Read it, then run "
                "`improve apply` to add its behaviour rules to the agent's profile.")
    rules, in_rules = [], False
    for line in plan.splitlines():
        if line.startswith("##"):
            in_rules = "behaviour rules" in line.lower()
            continue
        if in_rules and line.strip().startswith(("-", "*")):
            rule = line.lstrip("-* ").strip()
            if rule:
                rules.append(rule)
    if not rules:
        return (f"Plan saved to {plan_path}, but no 'Behaviour rules to add' bullets "
                "were found — edit data/agent-profile.md by hand instead.")
    profile = data_dir / "agent-profile.md"
    with profile.open("a", encoding="utf-8") as f:
        f.write("\n".join(rules) + "\n")
    return (f"Applied {len(rules)} improvement rule(s) to data/agent-profile.md — "
            f"they are now injected into every future task. Full plan: {plan_path}")

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
    if cmd == "improve":
        return _improve(apply=rest.strip().lower() == "apply")
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
