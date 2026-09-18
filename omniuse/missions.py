"""Autonomous missions — plan → act → observe → verify → repeat → report.

A Mission is a long-running goal ("test my project and fix the bugs") that
outlives a single agent run. Each iteration the agent works toward the goal
and reports status as JSON; the mission checkpoints everything to disk so
it can be resumed, audited in the memory log, and stopped by the killswitch
or a pending escalation at any moment.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from omniuse import config
from omniuse.agent import Agent
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch
from omniuse.tools import memory as _memory

STATUS_RE = re.compile(r"\{[^{}]*\"status\"[^{}]*\}", re.DOTALL)


def _missions_dir() -> Path:
    d = Path(config.data_dir()) / "missions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return slug or "mission"


class Mission:
    """Run an autonomous, checkpointed mission.

    Each iteration the agent must reply with one JSON object:
        {"status": "done"|"in_progress"|"blocked", "summary": "..."}
    """

    def __init__(self, goal: str, toolsets: list[str] | None = None,
                 max_iterations: int = 5, verbose: bool = True):
        self.goal = goal
        self.toolsets = toolsets
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.id = f"{_slug(goal)}-{int(time.time())}"
        self.checkpoint_path = _missions_dir() / f"{self.id}.json"

    def log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def _save(self, state: dict) -> None:
        self.checkpoint_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    def _instruction(self, state: dict, iteration: int) -> str:
        history = state["iterations"]
        previous = ""
        if history:
            last = history[-1]
            previous = (f"\n\nPREVIOUS ITERATION SUMMARY: {last.get('summary', '(none)')}\n"
                        f"Progress so far: {len(history)} iteration(s) completed.")
        return (
            f"MISSION: {self.goal}{previous}\n\n"
            f"This is iteration {iteration} of at most {self.max_iterations}. "
            "Work toward the mission goal now — one step at a time, verify your work "
            "(run the code again, re-read the file, take a screenshot) before claiming success.\n\n"
            "When you finish this iteration, end your reply with EXACTLY one JSON object "
            "on its own line (nothing after it):\n"
            '{"status": "done" | "in_progress" | "blocked", "summary": "<what happened, '
            'what is next or what is blocking you>"}\n'
            "Use 'blocked' if you need the operator (permission, KYC, missing access)."
        )

    def _parse_status(self, answer: str) -> dict:
        matches = STATUS_RE.findall(answer)
        for raw in reversed(matches):
            try:
                data = json.loads(raw)
                if data.get("status") in ("done", "in_progress", "blocked"):
                    return data
            except json.JSONDecodeError:
                continue
        return {"status": "in_progress",
                "summary": answer.strip()[-300:] or "(no summary)"}

    def run(self) -> str:
        state = {"goal": self.goal, "started": time.time(), "iterations": [], "status": "in_progress"}
        self._save(state)
        _memory.log_event("mission_start", mission=self.id, goal=self.goal)

        for iteration in range(1, self.max_iterations + 1):
            if _killswitch.is_engaged():
                state["status"] = "halted"
                self._save(state)
                _memory.log_event("mission_halted", mission=self.id)
                return "MISSION HALTED by operator killswitch."

            agent = Agent(toolsets=self.toolsets, verbose=self.verbose)
            answer = agent.run(self._instruction(state, iteration))
            verdict = self._parse_status(answer)

            state["iterations"].append({"n": iteration, "ts": time.time(), **verdict})
            state["status"] = verdict["status"]
            self._save(state)
            self.log(f"\n[mission {self.id}] iteration {iteration}: {verdict['status']}"
                     f" — {verdict['summary'][:120]}")

            if verdict["status"] == "done":
                return self._finish(state, answer)
            if verdict["status"] == "blocked":
                note = (_escalate.escalate_to_operator(
                    f"Mission blocked: {verdict['summary'][:200]}", self.goal)
                    if not _escalate.is_pending() else "escalation already pending")
                state["status"] = "blocked"
                self._save(state)
                return f"MISSION BLOCKED — operator needed.\n{verdict['summary']}\n({note})"

        state["status"] = "max_iterations"
        self._save(state)
        return self._finish(state, "reached the iteration limit without reporting done")

    def _finish(self, state: dict, answer: str) -> str:
        report_path = _missions_dir() / f"{self.id}-report.md"
        iterations = "\n".join(f"{i['n']}. [{i.get('status')}] {i.get('summary', '')}"
                               for i in state["iterations"])
        report = (f"# Mission report — {self.goal}\n\n"
                  f"- id: {self.id}\n- status: {state['status']}\n"
                  f"- started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state['started']))}\n\n"
                  f"## Iterations\n{iterations}\n\n## Final answer\n{answer}\n")
        report_path.write_text(report, encoding="utf-8")
        _memory.log_event("mission_end", mission=self.id, status=state["status"])
        return f"MISSION {state['status'].upper()} — full report: {report_path}\n\n{answer}"
