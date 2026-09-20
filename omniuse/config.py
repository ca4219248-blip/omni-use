"""Central configuration — environment variables FIRST, runtime overrides SECOND.

Copy .env.example to .env and fill in your key, or export the variables:

    export OPENAI_API_KEY=sk-...
    export OPENAI_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible API
    export OMNIUSE_MODEL=gpt-4o-mini

Runtime overrides (v5.1): the operator can change live details in conversation
("is UPI pe mat le, naya QR deta hun") — the agent writes them to
<data>/runtime.json via the settings toolset, and those values take priority
over the env vars. No .env editing, no restart — the next tool call sees it.
"""

import json
import os
from pathlib import Path

def _runtime_overrides() -> dict:
    """Live settings the operator changed in conversation (data/runtime.json)."""
    try:
        p = Path(data_dir()) / "runtime.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}

def _rt_or_env(key: str, env_var: str, default: str = "") -> str:
    """Runtime override first (operator said so just now), then env."""
    override = _runtime_overrides().get(key)
    return str(override) if override not in (None, "") else os.getenv(env_var, default)


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

def operator_token() -> str:
    """Secret token only the human operator knows (for raising spend limits)."""
    return os.getenv("OMNIUSE_OPERATOR_TOKEN", "")

def stt_model() -> str:
    """Speech-to-text model for voice control (runtime override wins)."""
    return _rt_or_env("stt_model", "OMNIUSE_STT_MODEL", "whisper-1")

def tts_model() -> str:
    """Text-to-speech model for voice_speak (runtime override wins)."""
    return _rt_or_env("tts_model", "OMNIUSE_TTS_MODEL", "tts-1")

def tts_voice() -> str:
    """Voice for text-to-speech (runtime override wins)."""
    return _rt_or_env("tts_voice", "OMNIUSE_TTS_VOICE", "alloy")

def fast_model() -> str:
    """A cheaper/faster model for routine steps (defaults to the main model).

    Speed pattern: set OMNIUSE_FAST_MODEL to something like a Groq-hosted
    llama and the agent uses it for routine turns, keeping OMNIUSE_MODEL
    for planning and vision.
    """
    return os.getenv("OMNIUSE_FAST_MODEL") or model()

def system_allowlist() -> list[str]:
    """Optional fnmatch patterns restricting system_run (empty = unrestricted).

    Example: OMNIUSE_SYSTEM_ALLOWLIST="ls*,cat*,git status,git diff*,python*"
    A command runs only if the full command (or its first word) matches at
    least one pattern. A sandbox without Docker — the poor man's container.
    """
    raw = os.getenv("OMNIUSE_SYSTEM_ALLOWLIST", "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


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

def upi_vpa() -> str:
    """The operator's UPI ID (e.g. name@okhdfcbank) for shop payments.

    Reads the runtime override first — if the operator just gave a new UPI/QR
    in conversation, that one wins over .env, immediately, no restart.
    """
    return _rt_or_env("upi_vpa", "OMNIUSE_UPI_VPA")

def payee_name() -> str:
    """Name shown on UPI payment requests / watermarks (runtime override wins)."""
    return _rt_or_env("payee_name", "OMNIUSE_PAYEE_NAME")

def warn_if_unconfigured() -> str | None:
    if not api_key():
        return (
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or point OPENAI_BASE_URL at any OpenAI-compatible provider."
        )
    return None
