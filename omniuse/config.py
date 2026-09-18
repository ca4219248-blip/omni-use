"""Central configuration — everything comes from environment variables.

Copy .env.example to .env and fill in your key, or export the variables:

    export OPENAI_API_KEY=sk-...
    export OPENAI_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible API
    export OMNIUSE_MODEL=gpt-4o-mini
"""

import os
from pathlib import Path


def api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")


def base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


def model() -> str:
    return os.getenv("OMNIUSE_MODEL", "gpt-4o-mini")


def max_steps() -> int:
    try:
        return int(os.getenv("OMNIUSE_MAX_STEPS", "30"))
    except ValueError:
        return 30


def screenshots_dir() -> str:
    d = os.getenv("OMNIUSE_SCREENSHOTS_DIR", "screenshots")
    Path(d).mkdir(parents=True, exist_ok=True)
    return d


def headless_browser() -> bool:
    return os.getenv("OMNIUSE_HEADLESS", "1") == "1"


def warn_if_unconfigured() -> str | None:
    if not api_key():
        return (
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or point OPENAI_BASE_URL at any OpenAI-compatible provider."
        )
    return None
