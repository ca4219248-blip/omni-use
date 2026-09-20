#!/usr/bin/env python3
"""Self-starter: no idea, need ₹300 — let the agent brainstorm.

    python examples/need_money.py
"""

from omniuse import Agent

TASK = """
Bhai mujhe ₹300 chahiye, mere paas koi idea nahi hai.
"""

if __name__ == "__main__":
    # ideas → shop → design → payments: brainstorm, score, pick, work it
    print(Agent(toolsets=["ideas", "shop", "text", "files", "notes", "memory"]).run(TASK))
