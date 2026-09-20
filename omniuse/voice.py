"""Voice control — bol ke bolo.

    python -m omniuse.voice file voice.wav      # transcribe a voice file + run it
    python -m omniuse.voice listen              # record from mic (10s) + run it
    python -m omniuse.voice listen 30           # record 30s

What gets run:
  - "paid ord-..." / "orders" / "stop" / "status" ... → operator console command
  - anything else → a full agent task ("bhai mujhe ₹300 chahiye")

Transcription uses your configured provider's audio API
(OMNIUSE_STT_MODEL, default whisper-1 — any OpenAI-compatible endpoint
works). Mic recording needs `pip install sounddevice numpy` — voice files
work without it.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from omniuse import config


def transcribe(path: str) -> str:
    """Transcribe an audio file (wav/mp3/m4a/ogg/webm) to text."""
    p = Path(path)
    if not p.is_file():
        return f"ERROR: audio file not found: {path}"
    from omniuse.llm import _get_client
    with p.open("rb") as f:
        response = _get_client().audio.transcriptions.create(
            model=config.stt_model(), file=f)
    text = (getattr(response, "text", None) or str(response)).strip()
    if not text:
        return "ERROR: transcription came back empty — try speaking a bit louder."
    return text


def record(seconds: int = 10, path: str = "") -> str:
    """Record from the default microphone to a wav file (needs sounddevice)."""
    try:
        import numpy as np
        import sounddevice as sd
        from scipy.io import wavfile  # noqa: F401 — bundled with sounddevice setups
    except ImportError as e:
        return (f"ERROR: mic recording needs extra packages ({e}). "
                "Install them with: pip install sounddevice numpy scipy")
    out = Path(path or tempfile.mktemp(suffix=".wav"))
    print(f"🎙 recording {seconds}s... speak now")
    audio = sd.rec(int(seconds * 16000), samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    import wave
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(audio.tobytes())
    return f"OK {out}"


def route(text: str) -> str:
    """Voice text → console command, or agent task. Returns the outcome."""
    from omniuse import operator as _operator
    out = _operator.handle(text)
    if out is None:
        print(f"🎙 you said: {text!r}\n")
        return _operator.run_task(text)
    print(f"🎙 you said: {text!r}")
    return out or "(no output)"


def _run(audio_path: str) -> int:
    text = transcribe(audio_path)
    if text.startswith("ERROR"):
        print(text)
        return 1
    result = route(text)
    print(f"\n{result}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "file":
        if len(args) < 2:
            print("Usage: python -m omniuse.voice file <audio.wav>")
            return 1
        return _run(args[1])
    if args[0] == "listen":
        seconds = int(args[1]) if len(args) > 1 else 10
        rec = record(seconds)
        if rec.startswith("ERROR"):
            print(rec)
            return 1
        return _run(rec.split(" ", 1)[1])
    print(f"Unknown mode {args[0]!r} — use: file <path> | listen [seconds]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
