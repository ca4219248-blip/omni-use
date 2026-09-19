"""Team orchestration — one planner brain, many worker agents.

The main agent can delegate a focused sub-task to a fresh worker agent
(via spawn_worker) with its own toolset and step budget. Workers are
plain Agents, so they inherit every guardrail: killswitch, permissions,
escalation pauses, memory logging, and the daily budget.
"""

from __future__ import annotations


def spawn_worker(task: str, toolsets: str = "", max_steps: int = 15) -> str:
    """Run a sub-agent on a focused task and return its final answer."""
    from omniuse.agent import Agent  # imported lazily (avoids circular init)

    if not task.strip():
        return "ERROR: task is required."
    selected = [t.strip() for t in (toolsets or "").split(",") if t.strip()] or None
    try:
        max_steps = max(1, min(int(max_steps), 50))
    except (TypeError, ValueError):
        max_steps = 15
    worker = Agent(toolsets=selected, max_steps=max_steps, verbose=False)
    answer = worker.run(task)
    return f"WORKER RESULT (toolsets={selected or 'all'}, steps≤{max_steps}):\n{answer}"


TOOLS = {
    "spawn_worker": (spawn_worker, {
        "type": "function",
        "function": {
            "name": "spawn_worker",
            "description": (
                "Delegate a focused sub-task to a fresh worker agent and get its "
                "final answer. Use for parallelizable or deep sub-problems "
                "(e.g. 'research X', 'fix file Y') while you keep the big picture."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Complete, self-contained sub-task for the worker"},
                    "toolsets": {"type": "string",
                                 "description": "Comma-separated toolsets the worker may use (default: all)"},
                    "max_steps": {"type": "integer", "description": "Worker step budget (default 15, max 50)"},
                },
                "required": ["task"],
            },
        },
    }),
}
