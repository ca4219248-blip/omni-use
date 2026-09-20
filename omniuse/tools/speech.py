"""Speech toolset — the agent talks back (text-to-speech).

voice_speak(text) renders speech with any OpenAI-compatible audio API
(OMNIUSE_TTS_MODEL, default tts-1; OMNIUSE_TTS_VOICE, default alloy),
saves an mp3 next to the data dir, and tries to play it out loud with the
platform's player (afplay on macOS, mpg123/aplay/ffplay on Linux, no
auto-play on Windows). The file path is always returned, so even with no
player installed the operator can play it manually — or the agent can
attach it to a delivery.

Voice *input* (speech-to-text) lives in `python -m omniuse.voice`.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from omniuse import config


def _tts(text: str) -> bytes:
    """Render text to speech audio (mp3 bytes) via the configured provider."""
    from openai import OpenAI
    client = OpenAI(api_key=config.api_key(), base_url=config.base_url())
    response = client.audio.speech.create(
        model=config.tts_model(),
        voice=config.tts_voice(),
        input=text,
    )
    return response.content


def _try_play(path: Path) -> bool:
    players = [
        ["afplay", str(path)],                     # macOS
        ["mpg123", "-q", str(path)],               # Linux (mpg123)
        ["aplay", "-q", str(path)],                # Linux (ALSA; often plays mp3 via dmix)
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
    ]
    for cmd in players:
        try:
            if subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


def speak(text: str, play: bool = True) -> str:
    """Say something out loud (saves an mp3 even if no player is found)."""
    text = (text or "").strip()
    if not text:
        return "ERROR: text is required."
    if len(text) > 4000:
        text = text[:4000]
    try:
        audio = _tts(text)
    except Exception as e:  # noqa: BLE001
        return f"ERROR: speech synthesis failed ({e})."
    out_dir = Path(config.data_dir()) / "speech"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"speech-{int(time.time())}.mp3"
    out.write_bytes(audio)
    if play and _try_play(out):
        return f"Spoken aloud; audio saved to {out} ({len(audio):,} bytes)."
    return (f"Audio saved to {out} ({len(audio):,} bytes) — no audio player found, "
            "play it manually or install mpg123/ffplay to hear the agent speak.")


TOOLS = {
    "voice_speak": (speak, {
        "type": "function",
        "function": {
            "name": "voice_speak",
            "description": (
                "Speak text out loud to the operator (text-to-speech). Use it for "
                "short spoken confirmations and alerts, not for long reports — "
                "write those. The mp3 is always saved even if no player exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "What to say (keep it short)"},
                    "play": {"type": "boolean", "description": "Try to play out loud (default true)"},
                },
                "required": ["text"],
            },
        },
    }),
}
