"""OmniUse — an AI agent that can actually *use* things.

It gives any LLM hands: a real browser, an Android phone (via ADB),
and the local computer (shell + files), plus eyes (vision on screenshots).
"""

__version__ = "0.1.0"

from omniuse.agent import Agent  # noqa: F401

__all__ = ["Agent", "__version__"]
