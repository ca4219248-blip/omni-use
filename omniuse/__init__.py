"""OmniUse — an AI agent that can actually *use* things.

It gives any LLM hands: a real browser, an Android phone (via ADB),
and the local computer (shell + files), plus eyes (vision on screenshots)
and guardrails (policy checks, capped wallet, escalation, memory, killswitch).
"""

__version__ = "0.2.0"

__all__ = ["Agent", "__version__"]


def __getattr__(name):
    # Lazy import: avoids a circular init (agent → tools → omniuse → agent).
    if name == "Agent":
        from omniuse.agent import Agent
        return Agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
