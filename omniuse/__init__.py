"""OmniUse — an AI agent that can actually *use* things.

Hands: a real browser, an Android phone (via ADB), the local computer, and
remote machines via the Hub. Eyes: vision on screenshots + structured screen
reading. Guardrails: policy checks, a capped wallet, escalation, layered
memory, permissions, budgets, and a killswitch. 3.0 added a design shop:
watermark-first selling over UPI with verified payments. 3.1 added a
self-starter (ideas) and operator-sent outreach. 3.2 moves all control to
the terminal + voice, and the agent verifies payments itself (payment_wait).
"""

__version__ = "3.2.0"

__all__ = ["Agent", "Mission", "__version__"]


def __getattr__(name):
    # Lazy imports: avoids circular init (agent → tools → omniuse → agent).
    if name == "Agent":
        from omniuse.agent import Agent
        return Agent
    if name == "Mission":
        from omniuse.missions import Mission
        return Mission
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
