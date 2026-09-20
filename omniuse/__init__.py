"""OmniUse — an AI agent that can actually *use* things.

Hands: a real browser, an Android phone (via ADB), the local computer, and
remote machines via the Hub. Eyes: vision on screenshots + structured screen
reading. Guardrails: policy checks, a capped wallet, escalation, layered
memory, permissions, budgets, and a killswitch. A paid-work pipeline for ANY
skill (not just design) with preview-first selling and verified UPI payments.
A big local toolbox: text, files, media, CSV, notes and QR toolsets. Learns
from every task (lessons), reports as PDF, and improves itself with the
operator's approval.
"""

__version__ = "5.0.0"

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
