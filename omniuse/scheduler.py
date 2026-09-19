"""Mission scheduler — full autonomy on a clock, with brakes.

Run missions automatically, forever (or until the killswitch):

    python -m omniuse.scheduler daemon
    python -m omniuse.scheduler add "Check server health and report" --every 60 --max-runs 10
    python -m omniuse.scheduler list
    python -m omniuse.scheduler run <id>     # trigger one now
    python -m omniuse.scheduler remove <id>

Every scheduled run goes through Mission (checkpoints + reports) and the
full guardrail stack: killswitch halts the daemon, budgets cap daily
activity, permissions still gate every tool call. Schedules live in
data/schedules.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from omniuse import config
from omniuse.tools import killswitch as _killswitch
from omniuse.tools import memory as _memory


def _path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "schedules.json"


def _load() -> list[dict]:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else []


def _save(schedules: list[dict]) -> None:
    _path().write_text(json.dumps(schedules, indent=2, ensure_ascii=False))


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def add(goal: str, every_minutes: int, toolsets: str = "",
        max_runs_per_day: int = 5) -> str:
    if not goal.strip():
        return "ERROR: goal is required."
    every_minutes = max(1, int(every_minutes))
    schedules = _load()
    entry = {
        "id": f"sched-{int(time.time())}",
        "goal": goal.strip(),
        "every_minutes": every_minutes,
        "toolsets": [t.strip() for t in toolsets.split(",") if t.strip()] or None,
        "max_runs_per_day": max(1, int(max_runs_per_day)),
        "enabled": True,
        "last_run": 0.0,
        "day": _today(),
        "runs_today": 0,
    }
    schedules.append(entry)
    _save(schedules)
    _memory.log_event("schedule_added", id=entry["id"], goal=goal)
    return (f"Added {entry['id']}: every {every_minutes} min, "
            f"max {entry['max_runs_per_day']} runs/day — '{goal.strip()[:80]}'")


def remove(schedule_id: str) -> str:
    schedules = _load()
    kept = [s for s in schedules if s["id"] != schedule_id]
    if len(kept) == len(schedules):
        return f"No schedule with id '{schedule_id}'."
    _save(kept)
    return f"Removed {schedule_id}."


def listing() -> str:
    schedules = _load()
    if not schedules:
        return "No schedules configured."
    lines = []
    for s in schedules:
        state = "enabled" if s.get("enabled") else "DISABLED"
        due = max(0, int(s["every_minutes"] - (time.time() - s.get("last_run", 0)) / 60))
        lines.append(f"- {s['id']} [{state}] every {s['every_minutes']}min "
                     f"(next in ~{due}min, {s.get('runs_today', 0)}/{s['max_runs_per_day']} today): "
                     f"{s['goal'][:70]}")
    return "\n".join(lines)


def _due(s: dict) -> bool:
    if not s.get("enabled"):
        return False
    if s.get("day") != _today():
        s["day"] = _today()
        s["runs_today"] = 0
    if s.get("runs_today", 0) >= s.get("max_runs_per_day", 5):
        return False
    return (time.time() - s.get("last_run", 0)) >= s["every_minutes"] * 60


def _persist(s: dict) -> None:
    """Update one schedule entry on disk (keeps the rest intact)."""
    schedules = _load()
    for i, entry in enumerate(schedules):
        if entry["id"] == s["id"]:
            schedules[i] = s
            break
    _save(schedules)


def run_one(s: dict) -> str:
    from omniuse.missions import Mission  # imported here to avoid circulars

    if s.get("day") != _today():
        s["day"] = _today()
        s["runs_today"] = 0
    s["last_run"] = time.time()
    s["runs_today"] = s.get("runs_today", 0) + 1
    _persist(s)  # persist the counter before running

    mission = Mission(goal=s["goal"], toolsets=s.get("toolsets"),
                       max_iterations=3, verbose=False)
    result = mission.run()
    _memory.log_event("scheduled_run", id=s["id"], goal=s["goal"],
                      result=result[:300])
    return result


def tick() -> int:
    """One scheduler pass: run everything that is due. Returns runs started."""
    if _killswitch.is_engaged():
        return 0
    schedules = _load()
    started = 0
    for s in schedules:
        if _due(s):
            print(f"[scheduler] running {s['id']}: {s['goal'][:60]}", flush=True)
            try:
                result = run_one(s)
                print(f"[scheduler] {s['id']} → {result[:150]}", flush=True)
            except Exception as e:  # noqa: BLE001 — one bad run never kills the daemon
                print(f"[scheduler] {s['id']} FAILED: {e}", flush=True)
            started += 1
    _save(schedules)
    return started


def daemon(interval_seconds: int = 30) -> int:
    print("OmniUse scheduler running — Ctrl+C to stop. "
          f"({len(_load())} schedule(s), checking every {interval_seconds}s)")
    try:
        while True:
            tick()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="omniuse-scheduler",
                                     description="Run missions on a schedule.")
    sub = parser.add_subparsers(dest="cmd")
    p_add = sub.add_parser("add", help="add a scheduled mission")
    p_add.add_argument("goal")
    p_add.add_argument("--every", type=int, required=True, help="minutes between runs")
    p_add.add_argument("--tools", default="", help="comma-separated toolsets")
    p_add.add_argument("--max-runs", type=int, default=5, help="max runs per day")
    sub.add_parser("list", help="list schedules")
    sub.add_parser("daemon", help="run the scheduling daemon")
    p_run = sub.add_parser("run", help="trigger a schedule now")
    p_run.add_argument("id")
    p_rm = sub.add_parser("remove", help="remove a schedule")
    p_rm.add_argument("id")
    args = parser.parse_args()

    if args.cmd == "add":
        print(add(args.goal, args.every, args.tools, args.max_runs))
    elif args.cmd == "list":
        print(listing())
    elif args.cmd == "daemon":
        return daemon()
    elif args.cmd == "run":
        match = [s for s in _load() if s["id"] == args.id]
        print(run_one(match[0]) if match else f"No schedule with id '{args.id}'.")
    elif args.cmd == "remove":
        print(remove(args.id))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
