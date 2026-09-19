"""Daily budget — real autonomy needs brakes you can trust.

Counts LLM steps and tool calls per calendar day (data/budget.json) and
stops the agent when a daily cap is reached. The agent then says so and
ends gracefully; the operator can change the caps in .env at any time.

Caps (\"0\" = unlimited):
    OMNIUSE_DAILY_STEPS       default 500
    OMNIUSE_DAILY_TOOL_CALLS  default 500
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from omniuse import config


def _path() -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / "budget.json"


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if data.get("day") == _today():
                return data
        except json.JSONDecodeError:
            pass
    return {"day": _today(), "llm_steps": 0, "tool_calls": 0}


def _save(data: dict) -> None:
    _path().write_text(json.dumps(data, indent=2))


def _cap(name: str, default: int) -> int:
    """Read a cap from the environment. \"0\" = unlimited."""
    raw = os.getenv(name, "").strip()
    if raw == "0":
        return 0
    try:
        return max(1, int(raw)) if raw else default
    except ValueError:
        return default


def step_limit() -> int:
    return _cap("OMNIUSE_DAILY_STEPS", 500)


def tool_call_limit() -> int:
    return _cap("OMNIUSE_DAILY_TOOL_CALLS", 500)


def step_available() -> bool:
    limit = step_limit()
    return limit == 0 or _load()["llm_steps"] < limit


def tool_call_available() -> bool:
    limit = tool_call_limit()
    return limit == 0 or _load()["tool_calls"] < limit


def record_step() -> None:
    data = _load()
    data["llm_steps"] += 1
    _save(data)


def record_tool_call() -> None:
    data = _load()
    data["tool_calls"] += 1
    _save(data)


def status() -> str:
    data = _load()
    steps = f"{data['llm_steps']}/{step_limit() or '∞'}"
    calls = f"{data['tool_calls']}/{tool_call_limit() or '∞'}"
    return f"budget for {data['day']}: {steps} steps, {calls} tool calls"


def reset() -> str:
    _save({"day": _today(), "llm_steps": 0, "tool_calls": 0})
    return "Budget counters reset for today."
