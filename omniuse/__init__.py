"""OmniUse — an AI agent that can actually *use* things.

Hands: a real browser, an Android phone (via ADB), the local computer, and
remote machines via the Hub. Eyes: vision on screenshots + structured screen
reading. Guardrails: policy checks, a capped wallet, escalation, layered
memory, permissions, and a killswitch.
"""

__version__ = "2.0.0"

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
