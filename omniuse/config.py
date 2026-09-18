"""Central configuration — everything comes from environment variables.

Copy .env.example to .env and fill in your key, or export the variables:

    export OPENAI_API_KEY=sk-...
    export OPENAI_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible API
    export OMNIUSE_MODEL=gpt-4o-mini
"""

import os
from pathlib import Path


# ------------------------------------------------------------------ core

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


# ------------------------------------------------- guardrails & control

def data_dir() -> str:
    """Where policies, memory, killswitch state and payment queue live."""
    return os.getenv("OMNIUSE_DATA_DIR", "data")


def telegram_bot_token() -> str:
    return os.getenv("OMNIUSE_TELEGRAM_BOT_TOKEN", "")


def telegram_chat_id() -> str:
    return os.getenv("OMNIUSE_TELEGRAM_CHAT_ID", "")


def operator_token() -> str:
    """Secret token only the human operator knows (for raising spend limits)."""
    return os.getenv("OMNIUSE_OPERATOR_TOKEN", "")


# ---------------------------------------------------------------- wallet

def rpc_url() -> str:
    return os.getenv("OMNIUSE_RPC_URL", "https://cloudflare-eth.com")


def wallet_address() -> str:
    return os.getenv("OMNIUSE_WALLET_ADDRESS", "")


def wallet_currency() -> str:
    return os.getenv("OMNIUSE_WALLET_CURRENCY", "ETH")


def wallet_max_tx_default() -> float:
    try:
        return float(os.getenv("OMNIUSE_WALLET_MAX_TX", "0.01"))
    except ValueError:
        return 0.01


def autopay_min():
    value = os.getenv("OMNIUSE_AUTOPAY_MIN", "")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def send_cmd() -> str:
    """Operator-configured command that actually signs/sends payments.

    OmniUse never touches private keys itself — it runs this command as:
        <cmd> <to> <amount> <purpose>
    e.g. a hardware-wallet CLI. Empty = payments are only queued.
    """
    return os.getenv("OMNIUSE_SEND_CMD", "")


# --------------------------------------------------------- hub / plugins

def hub_url() -> str:
    """URL of a remote OmniUse Hub (the agent's distant body)."""
    return os.getenv("OMNIUSE_HUB_URL", "")


def hub_token() -> str:
    """Shared secret for the hub (must match on both ends)."""
    return os.getenv("OMNIUSE_HUB_TOKEN", "")


def plugins_dir() -> str:
    """Folder scanned for plugin toolsets (each: plugin.json + main.py)."""
    return os.getenv("OMNIUSE_PLUGINS_DIR", "plugins")


def warn_if_unconfigured() -> str | None:
    if not api_key():
        return (
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or point OPENAI_BASE_URL at any OpenAI-compatible provider."
        )
    return None
