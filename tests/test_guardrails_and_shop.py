"""The rules that must never break: paid-work pipeline, guardrails, agent loop.

These use a scripted fake LLM (omniuse.agent.chat patched) — no API calls.
"""

from __future__ import annotations

import json

import pytest

import omniuse.agent as agent_mod
from omniuse import Agent
from omniuse import operator
from omniuse.tools import design, escalate, killswitch, payments, shop
from omniuse.tools import mobile as _mobile


@pytest.fixture
def poster_and_wm(tmp_path):
    out = design.design_poster("Test Poster", size="square")
    poster = out.split("saved to ")[1].split(" ")[0]
    wm = design.design_watermark(poster).split("saved to ")[1].split(" ")[0].rstrip("—").strip()
    return poster, wm


def _make_order(poster, wm, client="Priya", item="Poster", price=149):
    r = payments.order_create(client, item, price)
    oid = r.split("Order ")[1].split(" ")[0]
    assert "Attached" in payments.order_attach(oid, wm, poster)
    return oid


# --------------------------------------------------- paid-work pipeline

def test_cannot_deliver_before_payment(poster_and_wm):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm)
    assert "REFUSED" in payments.order_delivered(oid)


def test_screenshot_only_claims(poster_and_wm):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm)
    import omniuse.llm as llmmod
    llmmod.describe_image = lambda p, q: "app=XYZ, amount=₹149.00, ref=123"
    payments.payment_verify_screenshot(poster, order_id=oid)
    assert payments._find(oid)["state"] == "payment_claimed"
    assert "REFUSED" in payments.order_delivered(oid)


def test_agent_cannot_self_mark_paid(poster_and_wm):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm)
    r = payments.order_mark_paid(oid, operator_token="wrong-token")
    assert "REFUSED" in r
    assert payments._find(oid)["state"] != "paid"


def test_operator_paid_then_deliver(poster_and_wm):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm)
    assert "PAID" in operator.handle(f"paid {oid}")
    assert payments._find(oid)["state"] == "paid"
    assert "delivered" in payments.order_delivered(oid)


def test_sms_verification_auto_paid(poster_and_wm, monkeypatch):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm, client="Amit", item="Thumb", price=99)
    monkeypatch.setattr(_mobile, "_shell", lambda cmd, timeout=30:
                        "Row: 0 address=TP-XYZBANK, body=Rs.99.00 credited to a/c by UPI, date=1758300000000")
    out = payments.payment_wait(oid, timeout_minutes=1, poll_seconds=1)
    assert "VERIFIED" in out and payments._find(oid)["state"] == "paid"


def test_payment_wait_timeout(poster_and_wm, monkeypatch):
    poster, wm = poster_and_wm
    oid = _make_order(poster, wm, client="Raj", item="Logo", price=500)
    monkeypatch.setattr(_mobile, "_shell", lambda cmd, timeout=30: "Row: 0 body=promo")
    out = payments.payment_wait(oid, timeout_minutes=1, poll_seconds=1)
    assert "TIMED OUT" in out and "Do NOT deliver" in out
    assert payments._find(oid)["state"] == "preview_sent"


def test_work_preview_preview_first(tmp_path):
    essay = " ".join(f"Sentence {i} of the deliverable." for i in range(1, 41))
    r = shop.work_preview(essay, fraction=0.4)
    assert r.startswith("Preview saved to ")
    path = r.split("saved to ")[1].split(" ")[0]
    content = open(path).read()
    assert "PREVIEW" in content and "Sentence 1" in content
    assert "Sentence 40" not in content


# --------------------------------------------------- one-message rule

def test_one_message_rule():
    shop.catalog_add("Shop poster design", 149)
    shop.prospect_add("Sharma Sweets", source="test", notes="mithai")
    first = shop.outreach_draft("Sharma Sweets", "Shop poster design")
    assert "OPERATOR SENDS THIS PERSONALLY" in first
    shop.prospect_status("Sharma Sweets", "contacted")
    assert "REFUSED" in shop.outreach_draft("Sharma Sweets", "Shop poster design")
    shop.prospect_status("Sharma Sweets", "not_interested")
    assert "REFUSED" in shop.outreach_draft("Sharma Sweets", "Shop poster design")


# --------------------------------------------------- guardrails

def test_killswitch_halts_agent(poster_and_wm):
    killswitch.engage("test")
    try:
        def chat(messages, tools=None):
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "catalog_list", "arguments": "{}"}}]}
        agent_mod.chat = chat
        r = Agent(toolsets=["shop"], max_steps=2, verbose=False).run("do something")
        assert "HALTED" in r
    finally:
        killswitch.disengage()


def test_escalation_pauses_agent():
    escalate.escalate_to_operator("KYC", "task")
    try:
        assert escalate.is_pending()
        def chat(messages, tools=None):
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "catalog_list", "arguments": "{}"}}]}
        agent_mod.chat = chat
        r = Agent(toolsets=["shop"], max_steps=2, verbose=False).run("do something")
        assert "PAUSED" in r
    finally:
        operator.handle("resolve")


def test_scripted_agent_runs_tools():
    def chat(messages, tools=None):
        if len(messages) <= 2:
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "notes_add",
                              "arguments": json.dumps({"text": "from test", "tags": "auto"})}}]}
        return {"role": "assistant", "content": "Done."}
    agent_mod.chat = chat
    r = Agent(toolsets=["notes"], max_steps=3, verbose=False).run("add a note")
    assert r == "Done."
    from omniuse.tools import notes
    assert "from test" in notes.notes_search("from test")


def test_prompt_rules():
    from omniuse.agent import SYSTEM_PROMPT
    assert "PAID WORK (any service" in SYSTEM_PROMPT
    assert "PREVIEW FIRST" in SYSTEM_PROMPT
    assert "INBOUND ONLY" in SYSTEM_PROMPT
    assert "ONE MESSAGE per prospect" in SYSTEM_PROMPT
