"""v5.0 tests: PDF reports, lessons/self-improvement, auto-router, UPI link."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import omniuse.agent as agent_mod
import omniuse.router as router_mod
from omniuse import Agent, operator
from omniuse.tools import memory, payments, reports


# ------------------------------------------------------------- PDF reports

def test_task_report_creates_valid_pdf():
    sections = json.dumps([
        {"title": "What I did", "body": "Made a Diwali poster for Sharma Sweets.",
         "bullets": ["designed 3 variants", "watermarked the preview"]},
        {"title": "What failed", "body": "First attempt had a bad font. ₹ was transliterated."},
    ])
    r = reports.task_report("Poster order report", sections, footer="OmniUse v5")
    assert r.startswith("PDF report saved to ")
    path = r.split("saved to ")[1].split(" ")[0]
    data = Path(path).read_bytes()
    assert data.startswith(b"%PDF-1.4") and b"%%EOF" in data
    assert len(data) > 1000  # real content, not an empty shell


def test_task_report_validation():
    assert "ERROR" in reports.task_report("", "[]")
    assert "ERROR" in reports.task_report("Title", "not json")
    assert "ERROR" in reports.task_report("Title", "[]")


def test_report_list():
    reports.task_report("List test report", json.dumps([{"body": "hello"}]))
    listing = reports.report_list()
    assert "report(s)" in listing and "list-test-report" in listing


def test_report_survives_special_chars():
    r = reports.task_report("Weird ₹—…'\"()\\ report", json.dumps([{"body": "quotes \" and (parens) and ₹500"}]))
    assert r.startswith("PDF report saved to ")
    data = Path(r.split("saved to ")[1].split(" ")[0]).read_bytes()
    assert b"%%EOF" in data  # parens/quotes did not corrupt the stream


# ------------------------------------------------------------- lessons

def test_lesson_save_and_injection():
    from omniuse.agent import _lessons_block
    assert "ERROR" in memory.lesson_save("", "lesson")
    r = memory.lesson_save("clicked a dead button blindly", "always screen_elements before clicking")
    assert "Lesson saved" in r
    assert "always screen_elements" in memory.lesson_list()
    block = _lessons_block()
    assert "LESSONS LEARNED" in block and "always screen_elements" in block


# ------------------------------------------------------------- auto-router

def test_router_llm_pick():
    router_mod.chat = lambda messages, tools=None, fast=False: (
        {"role": "assistant", "content": '["notes", "text"]'})
    assert router_mod.suggest_toolsets("add a note and count words") == ["notes", "text"]


def test_router_falls_back_to_keywords():
    def boom(messages, tools=None, fast=False):
        raise RuntimeError("no LLM today")
    router_mod.chat = boom
    picked = router_mod.suggest_toolsets("make me a festival poster design")
    assert "design" in picked


def test_router_falls_back_on_junk():
    router_mod.chat = lambda messages, tools=None, fast=False: (
        {"role": "assistant", "content": "blah blah no list here"})
    picked = router_mod.suggest_toolsets("read this csv file please")
    assert "csvdata" in picked or "files" in picked


def test_agent_auto_toolsets():
    router_mod.chat = lambda messages, tools=None, fast=False: (
        {"role": "assistant", "content": '["notes"]'})
    def chat(messages, tools=None):
        return {"role": "assistant", "content": "Done."}
    agent_mod.chat = chat
    a = Agent(toolsets="auto", max_steps=2, verbose=False)
    assert a.run("make a note") == "Done."
    assert a.toolsets == ["notes"]


def test_agent_auto_via_list_from_cli():
    # cli.py passes ["auto"] — must behave the same as "auto"
    router_mod.chat = lambda messages, tools=None, fast=False: (
        {"role": "assistant", "content": '["memory"]'})
    agent_mod.chat = lambda messages, tools=None: {"role": "assistant", "content": "Done."}
    assert Agent(toolsets=["auto"], max_steps=2, verbose=False).run("x") == "Done."


# ------------------------------------------------------------- UPI link

def test_payment_upi_link(monkeypatch):
    monkeypatch.setenv("OMNIUSE_UPI_VPA", "david@oktest")
    monkeypatch.setenv("OMNIUSE_PAYEE_NAME", "David")
    r = payments.payment_upi_link(149, note="poster", order_id="ord-1")
    assert r.startswith("UPI payment link") and "upi://pay?pa=david%40oktest" in r
    assert "am=149.00" in r and "ord-1" in r
    assert "ERROR" in payments.payment_upi_link(0)
    assert "ERROR" in payments.payment_upi_link("abc")


def test_payment_upi_link_unconfigured(monkeypatch):
    monkeypatch.delenv("OMNIUSE_UPI_VPA", raising=False)
    assert "ERROR" in payments.payment_upi_link(100)


# ------------------------------------------------------------- improve flow

def _seed_history():
    memory.log_event("task_start", task="make a poster")
    memory.log_event("task_end", answer="poster saved")
    memory.log_event("tool_call", step=1, tool="design_poster",
                     arguments={}, result="ERROR: font not found")
    memory.lesson_save("used a missing font", "check fonts before designing")


def test_improve_plan_and_apply(monkeypatch):
    _seed_history()
    import omniuse.llm as llmmod
    plan = ("## Patterns noticed\nfont errors repeat\n\n"
            "## Behaviour rules to add\n"
            "- Always verify fonts exist before design_poster\n"
            "- Take a screenshot after every browser action\n\n"
            "## Bigger changes to propose\nDocker sandbox")
    monkeypatch.setattr(llmmod, "chat", lambda m, tools=None, fast=False: (
        {"role": "assistant", "content": plan}))
    r = operator.handle("improve")
    assert "improvement-plan.md" in r
    from omniuse import config
    assert (Path(config.data_dir()) / "improvement-plan.md").read_text().startswith("## Patterns")
    r2 = operator.handle("improve apply")
    assert "Applied 2 improvement rule(s)" in r2
    profile = (Path(config.data_dir()) / "agent-profile.md").read_text()
    assert "verify fonts exist" in profile
    # and the profile is injected into the agent's context
    from omniuse.agent import _profile_block
    assert "verify fonts exist" in _profile_block()


def test_improve_nothing_yet(monkeypatch):
    import omniuse.llm as llmmod
    monkeypatch.setattr(llmmod, "chat", lambda m, tools=None, fast=False: (
        {"role": "assistant", "content": "## Patterns noticed\nnothing"}))
    r = operator.handle("improve")
    assert "Nothing to learn from yet" in r


# ------------------------------------------------------------- mission PDF

def test_mission_finish_writes_pdf():
    from omniuse.missions import Mission
    m = Mission("test goal for pdf", toolsets=["notes"])
    state = {"status": "done", "started": 1758300000.0, "iterations": [
        {"n": 1, "status": "working", "summary": "did step one"}]}
    out = m._finish(state, "all done")
    assert "MISSION DONE" in out and ".md" in out and ".pdf" in out
    pdf_line = [l for l in out.splitlines() if l.endswith(".pdf")][0]
    data = Path(pdf_line.strip("📄 PDF report: ").strip()).read_bytes()
    assert data.startswith(b"%PDF") and b"%%EOF" in data


# ------------------------------------------------------------- registry

def test_registry_v50():
    from omniuse.tools import TOOLSETS, get_tool_schemas
    names = [s["function"]["name"] for s in get_tool_schemas(None)]
    for t in ("task_report", "report_list", "lesson_save", "lesson_list", "payment_upi_link"):
        assert t in names, t
    assert len(TOOLSETS) >= 26
