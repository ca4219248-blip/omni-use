"""v4.1 tests: stuck detection, runs injection, allowlist, SoM, TTS, mobile_connect."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import omniuse.agent as agent_mod
from omniuse import Agent
from omniuse.tools import memory, mobile, screen, system
from omniuse.tools import speech


# ------------------------------------------------------- stuck detection

def _looping_chat(name="notes_add", arguments=None):
    arguments = arguments or {"text": "loop note"}
    def chat(messages, tools=None):
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{len(messages)}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(arguments)}}]}
    return chat


def test_stuck_nudge_then_stop():
    agent_mod.chat = _looping_chat()
    agent = Agent(toolsets=["notes"], max_steps=10, verbose=False)
    r = agent.run("keep doing the same thing")
    assert "TASK STOPPED" in r and "same action" in r
    # the nudge fired before the stop
    kinds = [e["kind"] for e in memory._entries()]
    assert "stuck_nudge" in kinds and "stuck_stop" in kinds


def test_stuck_reset_by_different_action():
    calls = {"i": 0}
    def chat(messages, tools=None):
        calls["i"] += 1
        # same, same, DIFFERENT, same, same, DIFFERENT ... never 3-in-a-row identical
        text = "DIFFERENT" if calls["i"] % 3 == 0 else "same"
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{calls['i']}", "type": "function",
             "function": {"name": "notes_add", "arguments": json.dumps({"text": text})}}]}
    agent_mod.chat = chat
    r = Agent(toolsets=["notes"], max_steps=10, verbose=False).run("mixed actions")
    # never hit 4-in-a-row of the same call → no TASK STOPPED
    assert "TASK STOPPED" not in r
    kinds = [e["kind"] for e in memory._entries()]
    assert "stuck_stop" not in kinds


# ------------------------------------------------------- runs injection

def test_recent_runs_and_injection():
    from omniuse.agent import _runs_block
    memory.log_event("task_start", task="find top HN story")
    memory.log_event("task_end", answer="Story X is top")
    memory.log_event("task_start", task="make a poster")
    memory.log_event("task_end", answer="saved poster.png")
    runs = memory.recent_runs(2)
    assert len(runs) == 2 and runs[0]["task"] == "find top HN story"
    block = _runs_block()
    assert "RECENT RUNS" in block and "find top HN story" in block and "poster.png" in block


def test_runs_block_empty_when_no_history():
    from omniuse.agent import _runs_block
    assert _runs_block() == ""


# ------------------------------------------------------- system allowlist

def test_allowlist_blocks_and_allows(monkeypatch):
    monkeypatch.setenv("OMNIUSE_SYSTEM_ALLOWLIST", "ls*,cat*,python*")
    assert "REFUSED" in system.system_run("rm -rf /tmp/x")
    assert system.system_run("ls -la /tmp").startswith("exit=")
    assert system.system_run("cat /etc/hostname").startswith("exit=")


def test_no_allowlist_unrestricted(monkeypatch):
    monkeypatch.delenv("OMNIUSE_SYSTEM_ALLOWLIST", raising=False)
    assert system.system_run("echo hi").startswith("exit=0")


# ------------------------------------------------------- set-of-marks

def test_annotate_draws_numbers(tmp_path):
    shot = tmp_path / "shot.png"
    Image.new("RGB", (800, 600), (255, 255, 255)).save(shot)
    marks = [{"text": "Start Race", "x": 100, "y": 150, "w": 200, "h": 40},
             {"text": "Settings", "x": 100, "y": 400, "w": 120, "h": 36}]
    out = screen._annotate(str(shot), marks)
    assert out.endswith("-marks.png")
    # annotated image exists and differs from the blank one
    assert Image.open(out).size == (800, 600)
    import os
    assert os.path.getsize(out) > os.path.getsize(shot)


def test_bounds_rect():
    assert screen._bounds_rect("[10,20][110,70]") == (10, 20, 100, 50)
    assert screen._bounds_rect("garbage") is None


def test_screen_marks_bad_device():
    assert "ERROR" in screen.screen_marks(device="toaster")


# ------------------------------------------------------- speech (TTS)

def test_voice_speak_saves_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(speech, "_tts", lambda text: b"FAKE-MP3-BYTES")
    monkeypatch.setattr(speech, "_try_play", lambda p: False)
    r = speech.speak("hello operator", play=True)
    assert r.startswith("Audio saved to ")
    path = r.split("Audio saved to ")[1].split(" ")[0]
    assert open(path, "rb").read() == b"FAKE-MP3-BYTES"


def test_voice_speak_empty():
    assert "ERROR" in speech.speak("  ")


# ------------------------------------------------------- mobile_connect

def test_mobile_connect(monkeypatch):
    seen = {}
    monkeypatch.setattr(mobile, "_adb", lambda *a, timeout=30: seen.update(cmd=a) or "connected to 192.168.1.5:5555")
    r = mobile.mobile_connect("192.168.1.5:5555")
    assert r.startswith("Connected to 192.168.1.5:5555")
    assert seen["cmd"] == ("connect", "192.168.1.5:5555")


def test_mobile_connect_bad_args():
    assert "ERROR" in mobile.mobile_connect("no-port-here")


# ------------------------------------------------------- registry + prompt

def test_registry_counts():
    from omniuse.tools import TOOLSETS, get_tool_schemas
    names = [s["function"]["name"] for s in get_tool_schemas(None)]
    for t in ("screen_marks", "voice_speak", "mobile_connect"):
        assert t in names, t
    assert len(TOOLSETS) >= 25


def test_fast_model_config(monkeypatch):
    from omniuse import config
    monkeypatch.delenv("OMNIUSE_FAST_MODEL", raising=False)
    assert config.fast_model() == config.model()
    monkeypatch.setenv("OMNIUSE_FAST_MODEL", "llama-fast")
    assert config.fast_model() == "llama-fast"


def test_fast_chat_uses_fast_model(monkeypatch):
    import omniuse.llm as llmmod
    captured = {}

    class FakeCompletions:
        def create(self, **kw):
            captured["model"] = kw["model"]
            class Msg:
                def model_dump(self, exclude_none=None):
                    return {"role": "assistant", "content": "ok"}
            class Choice:
                message = Msg()
            class Resp:
                choices = [Choice()]
            return Resp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llmmod, "_client", FakeClient())
    monkeypatch.setenv("OMNIUSE_FAST_MODEL", "fast-model-x")
    assert llmmod.chat([], fast=True) == {"role": "assistant", "content": "ok"}
    assert captured["model"] == "fast-model-x"
    llmmod.chat([], fast=False)
    assert captured["model"] != "fast-model-x"
