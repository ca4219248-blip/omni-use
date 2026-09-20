"""Settings toolset — runtime knowledge the agent picks up in conversation.

The operator talks like a human: "is UPI pe mat le, naya QR deta hun",
"meri gallery mein pada hai, dekh lo". The agent should adopt that on the
spot — look at the file (vision), read the UPI ID out of the QR, and use the
new value for every following payment_qr / payment_upi_link / watermark.
.env is only the FIRST-TIME bootstrap; after that, conversation is king:

    setting_set(key, value)   live-override a setting (allowlisted keys only)
    setting_get(key)          current effective value + where it came from
    settings_list()           all changeable settings, runtime vs env vs unset
    upi_read_qr(image_path)   LOOK at a QR image (gallery/download/screenshot),
                              pull the UPI ID out of it, adopt it immediately

Guardrail: only receiving-side / harmless keys are changeable at runtime.
Money caps (wallet max, operator token, allowlists) stay in .env — the agent
can never talk its way around those.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from omniuse import config
from omniuse.tools import memory as _memory

# What the operator may change live, in conversation. Deliberately small.
CHANGEABLE = {
    "upi_vpa": "the UPI ID money should ARRIVE on (receiving — safe)",
    "payee_name": "name shown on payment requests / watermarks",
    "tts_model": "text-to-speech model",
    "tts_voice": "text-to-speech voice",
    "stt_model": "speech-to-text model",
}

_ENV_FOR = {"upi_vpa": "OMNIUSE_UPI_VPA", "payee_name": "OMNIUSE_PAYEE_NAME",
            "tts_model": "OMNIUSE_TTS_MODEL", "tts_voice": "OMNIUSE_TTS_VOICE",
            "stt_model": "OMNIUSE_STT_MODEL"}

_VPA_RE = re.compile(r"[A-Za-z0-9._\-]{2,}@[A-Za-z]{2,}")


def _runtime_path() -> Path:
    p = Path(config.data_dir()) / "runtime.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_runtime() -> dict:
    try:
        return json.loads(_runtime_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def setting_set(key: str, value: str) -> str:
    """Adopt a live setting from conversation — effective from the NEXT call."""
    key = (key or "").strip().lower()
    value = (value or "").strip()
    if key not in CHANGEABLE:
        return (f"ERROR: '{key}' cannot be changed at runtime. Changeable: "
                f"{', '.join(sorted(CHANGEABLE))}. Money-critical settings "
                "(wallet caps, operator token) only live in .env — on purpose.")
    if not value:
        return "ERROR: value is required (empty would clear the setting)."
    if key == "upi_vpa" and not _VPA_RE.fullmatch(value):
        return ("ERROR: that doesn't look like a UPI ID (expected something "
                "like name@okhdfcbank). Ask the operator to confirm it.")
    data = _load_runtime()
    data[key] = value
    _runtime_path().write_text(json.dumps(data, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    _memory.log_event("setting_set", key=key, value=value)
    extra = ""
    if key == "upi_vpa":
        extra = (" All payment_qr / payment_upi_link calls now use this ID — "
                  "no restart, no .env.")
    return (f"Setting '{key}' updated to {value} — effective immediately.{extra}")


def setting_get(key: str) -> str:
    """Current effective value of a setting + where it came from."""
    key = (key or "").strip().lower()
    if key not in CHANGEABLE:
        return f"ERROR: unknown setting '{key}'. Changeable: {', '.join(sorted(CHANGEABLE))}."
    runtime = _load_runtime().get(key)
    import os
    env_val = os.getenv(_ENV_FOR.get(key, ""), "")
    if runtime:
        return (f"{key} = {runtime}  (source: RUNTIME — the operator set this "
                "in conversation; .env value was: "
                f"{env_val or 'unset'})")
    if env_val:
        return f"{key} = {env_val}  (source: .env / environment)"
    return (f"{key} is not set anywhere. If the operator just gave it, "
            "setting_set it now.")


def settings_list() -> str:
    """All live-changeable settings and their current effective values."""
    runtime = _load_runtime()
    import os
    lines = []
    for key in sorted(CHANGEABLE):
        env_val = os.getenv(_ENV_FOR.get(key, ""), "")
        if key in runtime:
            lines.append(f"- {key} = {runtime[key]}  (RUNTIME — set in conversation; env: {env_val or 'unset'})")
        elif env_val:
            lines.append(f"- {key} = {env_val}  (env)")
        else:
            lines.append(f"- {key} — unset")
    return ("Live-changeable settings (setting_set to change, effective "
            "immediately):\n" + "\n".join(lines) +
            "\n(Money caps and the operator token are NOT changeable here — .env only.")


def upi_read_qr(image_path: str) -> str:
    """Look at a QR image the operator pointed at, adopt the UPI ID from it.

    Works on anything the operator hands over — a gallery photo, a download,
    a screenshot. Tries a local decode first (pyzbar if installed), then the
    vision model. On success the UPI ID goes live immediately via setting_set.
    """
    p = Path(image_path or "")
    if not p.is_file():
        return (f"ERROR: file not found: {image_path}. Ask the operator for the "
                "exact file name, or find it with files_recent / files_find.")
    # 1) local decode if possible
    try:
        from PIL import Image
        try:
            import pyzbar.pyzbar as pyzbar  # type: ignore
            img = Image.open(p)
            for obj in pyzbar.decode(img):
                text = (obj.data or b"").decode("utf-8", "replace")
                if text.startswith("upi://"):
                    vpa = re.search(r"pa=([^&]+)", text)
                    if vpa:
                        return setting_set("upi_vpa", vpa.group(1))
                m = _VPA_RE.search(text)
                if m:
                    return setting_set("upi_vpa", m.group(0))
        except ImportError:
            pass
    except Exception:  # noqa: BLE001 — fall through to vision
        pass
    # 2) vision: QRs usually print the ID, and vision can read the surroundings
    from omniuse.llm import describe_image
    question = ("Look at this QR code image. It is a UPI payment QR. Find the "
                "UPI ID / VPA printed on or near it (format like name@okhdfcbank, "
                "name@paytm, 98xxxxxx@ybl). Reply with ONLY the UPI ID, nothing "
                "else. If you cannot find any UPI ID, reply exactly: NOT FOUND")
    try:
        answer = (describe_image(image_path, question) or "").strip()
    except Exception as e:  # noqa: BLE001
        return (f"ERROR reading the QR image: {e}. Ask the operator to just "
                "SAY the new UPI ID, then setting_set it.")
    m = _VPA_RE.search(answer)
    if m:
        return setting_set("upi_vpa", m.group(0))
    return ("Could not read a UPI ID from that image (vision said: "
            f"{answer[:120]}). The QR might not print the ID. Ask the operator "
            "to say the UPI ID out loud / type it, then setting_set('upi_vpa', it). "
            "If the operator simply wants THIS QR image sent to clients, no "
            "reading is needed — just send the file itself.")


TOOLS = {
    "setting_set": (setting_set, {
        "type": "function",
        "function": {
            "name": "setting_set",
            "description": (
                "Adopt a live setting the operator just gave in conversation "
                "(e.g. a new UPI ID). Effective from the very next tool call — "
                "no .env, no restart. Only receiving-side/harmless keys are "
                "changeable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": sorted(CHANGEABLE),
                            "description": "Which setting to change"},
                    "value": {"type": "string", "description": "The new value"},
                },
                "required": ["key", "value"],
            },
        },
    }),
    "setting_get": (setting_get, {
        "type": "function",
        "function": {
            "name": "setting_get",
            "description": "Current effective value of a live-changeable setting + where it came from (runtime vs env).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": sorted(CHANGEABLE)},
                },
                "required": ["key"],
            },
        },
    }),
    "settings_list": (settings_list, {
        "type": "function",
        "function": {
            "name": "settings_list",
            "description": "Show all live-changeable settings and their current values.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }),
    "upi_read_qr": (upi_read_qr, {
        "type": "function",
        "function": {
            "name": "upi_read_qr",
            "description": (
                "The operator pointed at a UPI QR image (gallery photo, download, "
                "screenshot). Look at it, pull the UPI ID out of it, and adopt it "
                "live so all following payment QRs/links use the new ID. Give the "
                "exact file path — find it first with files_recent if needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the QR image file"},
                },
                "required": ["image_path"],
            },
        },
    }),
}
