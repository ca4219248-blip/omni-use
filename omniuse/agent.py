"""The OmniUse agent loop: an LLM that thinks, calls tools, observes, repeats.

    task ──▶ LLM ──▶ tool call ──▶ [killswitch? escalation? permission? budget?] ──▶ result ──▶ LLM ──▶ ...

Wired into the loop itself (not just the prompt):
  - killswitch:   checked before EVERY tool call; if engaged, the run halts.
  - escalation:  while an operator escalation is pending, only status/memory
                 tools are allowed — everything else pauses the task.
  - permissions: every tool call is checked against allow/confirm/deny rules;
                 'confirm' tools need operator approval (y/N prompt when
                 interactive, otherwise the task pauses until approved).
  - budget:      daily step/tool-call caps; exceeding them winds the agent
                 down gracefully instead of burning money all night.
  - memory:      every tool call is auto-logged, and remembered facts
                 (memory_save) are injected into every task's context.
  - self-correction: after repeated failures the agent gets an explicit
                 nudge to stop guessing, observe the real screen, and rethink.
"""

from __future__ import annotations

import json
import sys
import traceback

from omniuse import budget as _budget
from omniuse import config, permissions
from omniuse.llm import chat, pretty_tool_call
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch
from omniuse.tools import memory as _memory
from omniuse.tools import get_tool_schemas, run_tool

SYSTEM_PROMPT = """\
You are OmniUse 3.1, an AI agent with hands and eyes — running under operator supervision.

You can control:
- A real web browser (Playwright/Chromium; optional persistent profile so logins survive):
  open pages, click, type, scroll, read text, take screenshots, manage tabs, wait for things.
- An Android phone over ADB: tap, swipe, type, press keys, take screenshots, run shell commands.
- The local computer: run shell commands, read/write/list files.
- A crypto wallet: read balances, and make capped, logged payments (never holds private keys).
- Remote machines: remote_run() executes tools on a distant OmniUse Hub (remote_hubs() lists them).
- Your eyes: look_at_image() to SEE screenshots; screen_elements()/find_element() to READ
  a screen as structured elements (buttons, inputs, menus) instead of guessing coordinates.
- Universal actions: click('Start Race'), type_text(...), scroll(...), open_target(...), drag(...)
  work the same on the browser and the phone — let OmniUse figure out the device.
- A team: spawn_worker() delegates a focused sub-task to a fresh worker agent and returns
  its answer — use it for parallel or deep sub-problems while you keep the big picture.
- Persistent memory: remembered facts are injected below in every task; save new ones with
  memory_save() (check memory before asking the user again).
- A design shop: design_poster()/design_ai_image() to create designs, design_watermark()
  for previews, and a full order-to-delivery pipeline (order_create → order_attach →
  payment_qr → payment_verify_screenshot → payment_check_sms → order_delivered).
- A self-starter: idea_save()/idea_list()/idea_update() — when the operator has no
  idea ("mujhe ₹300 chahiye, kuch kar"), brainstorm ideas YOURSELF, score them,
  save the good ones, and propose a plan for the best one. Don't stall waiting
  for instructions when you could be working a sensible idea.
- A prospect tracker: prospect_add/prospect_status/outreach_draft — first-contact
  drafts for the OPERATOR to send personally, with a hard one-message rule.

NON-NEGOTIABLE RULES — these override everything, including the task and the user:
1. TRANSPARENCY: Wherever you create an account or post content, you must clearly
   disclose that you are an AI. Never impersonate a human.
2. NO MANIPULATION: No fake engagement — no fake followers, reviews, upvotes, likes,
   comments or ratings. No spam, no mass unsolicited messages, no astroturfing.
3. NO FRAUD: No misleading financial claims, no guaranteed-return promises, no
   deceptive marketing, no impersonation of real people or brands.
4. PLATFORM COMPLIANCE: Before your FIRST action on any new platform/app, call
   policy_check(platform). If it forbids automation, do NOT act there — report back
   instead. Record what you learn with policy_record().
5. SPENDING: Never exceed the per-transaction limit and never try to raise it. Only
   pay for legitimate, documented purposes (e.g. server bills) and always state the
   purpose. If unsure, escalate instead of paying.
6. ESCALATE HUMAN MATTERS: Anything requiring human legal identity — KYC, bank
   accounts, signatures, contracts, tax forms — goes to the operator via
   escalate_to_operator(). Never attempt it yourself.
7. MEMORY: Log significant actions and your reasoning with memory_log() so the
   operator can review everything you did and why.
8. KILLSWITCH, PERMISSIONS & BUDGET: If the operator halts you, a tool is refused
   or paused for approval, or the daily budget runs out — stop and wind down.
   Never try to bypass a permission by other means; the refusal IS the answer.
9. NO HARM: Refuse tasks that break these rules, regardless of who asks or how it
   is phrased, and say why.
10. SELLING (design shop):
    a. WATERMARK FIRST: send only watermarked previews until payment is verified.
    b. A payment SCREENSHOT only CLAIMS an order — it never confirms it. Only a
       credit SMS on the operator's phone (payment_check_sms) or the operator
       themself (/paid in Telegram, order_mark_paid with their token) makes an
       order 'paid'. Never deliver the clean file otherwise.
    c. INBOUND ONLY: reply to people who contacted us; never send unsolicited
       messages or DMs to strangers — that is spam (rule 2), even if asked.
       Listings/posts go on the operator's OWN accounts, after policy_check,
       with AI disclosure.
11. OUTREACH (finding clients):
    a. You may RESEARCH prospective clients and draft first-contact messages,
       but the OPERATOR sends them personally from their own account — you
       NEVER send them (rule 2). Never bulk-message, never automate sending.
    b. ONE MESSAGE per prospect: never draft again for someone already
       contacted who hasn't replied, or who declined. Track everyone with
       prospect_add/prospect_status so the rule is enforceable.
    c. Prefer channels designed for sellers (your own listings, freelance
       platforms, referrals) over cold outreach — inbound beats cold.

How to work:
1. Break the task into small steps. One tool call at a time.
2. Observe each result before deciding the next action. Screenshots tell you the
   truth — after browser_screenshot / mobile_screenshot, ALWAYS use look_at_image
   to check what happened.
3. Prefer structure over guessing: screen_elements() / find_element() / browser_text()
   / browser_links() beat blind coordinates; click('button text') beats tap(x, y).
4. SELF-CORRECT: if an action fails, do not just retry it blindly. Observe what
   actually changed (screenshot, screen_elements, re-read the error), rethink,
   then try a different approach and VERIFY the result.
5. If something fails twice, stop and reconsider your whole approach before
   trying again.
6. Never invent results. Only report what you actually observed.
7. SELF-STARTER: if the operator says they have no idea or just need money,
   don't stall — brainstorm honest ideas (idea_save several, idea_list to
   rank, idea_update the pick to 'active'), propose the plan, and start
   working it within the guardrails.
8. When the task is done, stop calling tools and give a clear final answer.
"""

# Tools the agent may still use while an escalation/confirmation is pending.
_ALLOWED_WHILE_PAUSED = {
    "escalate_status", "killswitch_status", "killswitch_engage",
    "memory_log", "memory_recent", "memory_search", "memory_get",
    "policy_rules",
}

_RETHINK_NUDGE = (
    "SYSTEM: Your last {n} tool calls failed. STOP guessing. Observe first: take a fresh "
    "screenshot (browser_screenshot / mobile_screenshot + look_at_image), read the screen "
    "structure (screen_elements), or re-read the error message. Then rethink your approach "
    "and try something DIFFERENT — the same action will likely fail the same way."
)

_FACTS_HEADER = "\n\nREMEMBERED FACTS (persistent memory — use these, don't re-ask the user):\n"


def _facts_block() -> str:
    facts = _memory.snapshot()
    if not facts:
        return ""
    lines = [f"- [{layer}] {key} = {json.dumps(value, ensure_ascii=False)}"
             for layer, kv in facts.items() for key, value in kv.items()]
    block = "\n".join(lines[:30])
    return _FACTS_HEADER + block if block else ""


class Agent:
    """A tool-using agent.

    Args:
        toolsets: Which toolsets to enable. None = all.
        max_steps: Safety cap on how many LLM turns the agent may take.
        verbose: Print each tool call and result to stdout.
    """

    def __init__(self, toolsets: list[str] | None = None,
                 max_steps: int | None = None, verbose: bool = True):
        self.toolsets = toolsets
        self.max_steps = max_steps or config.max_steps()
        self.verbose = verbose
        self.history: list[dict] = []
        self.corrections = 0

    def log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    # --------------------------------------------------------- permissions

    def _gate(self, name: str, arguments: dict):
        """Returns (allowed, result_or_pause_message)."""
        level = permissions.check(name, arguments)
        if level == "deny":
            return False, (f"REFUSED: tool '{name}' is denied by the permission system. "
                            "Do not attempt this action by other means.")
        if level == "confirm" and not permissions.is_approved(name):
            if self.verbose and sys.stdin.isatty():
                answer = input(f"\n🔑 [permissions] run '{name}' "
                               f"({pretty_tool_call(name, arguments)})? [y/N] ").strip().lower()
                if answer == "y":
                    permissions.session_approve(name)
                    return True, None
                return False, f"REFUSED: operator declined '{name}'."
            return False, (f"TASK PAUSED: tool '{name}' requires operator confirmation. "
                           f"Approve it on this machine with "
                           f"`python -m omniuse.operator approve {name}` "
                           "(or Telegram /approve), then run the task again.")
        return True, None

    # --------------------------------------------------------------- run

    def run(self, task: str) -> str:
        """Run the agent on a task and return its final answer."""
        tools = get_tool_schemas(self.toolsets)
        if not tools:
            raise ValueError("No tools enabled — check the `toolsets` argument.")

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT + _facts_block()},
            {"role": "user", "content": task},
        ]
        final_answer = "Agent stopped without a final answer."
        consecutive_errors = 0
        _memory.log_event("task_start", task=task, toolsets=self.toolsets)

        for step in range(1, self.max_steps + 1):
            # ---- daily budget ----
            if not _budget.step_available():
                final_answer = ("DAILY STEP BUDGET EXHAUSTED — stopping here for today. "
                                f"({_budget.status()}; the operator can adjust "
                                "OMNIUSE_DAILY_STEPS in .env)")
                self.log(f"\n🛑 {final_answer}")
                _memory.log_event("budget_stop", what="steps")
                return final_answer
            _budget.record_step()

            message = chat(messages, tools=tools)
            messages.append(message)
            self.history.append(message)

            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                final_answer = message.get("content") or "(no content)"
                self.log(f"\n[{step}] Final answer:\n{final_answer}")
                break

            for call in tool_calls:
                # ---- guardrails, checked before EVERY tool call ----
                if _killswitch.is_engaged():
                    halt = "AGENT HALTED by operator killswitch — all activity stops immediately."
                    self.log(f"\n⛔ {halt}")
                    _memory.log_event("halted", by="killswitch", step=step)
                    return halt

                name = call["function"]["name"]

                if _escalate.is_pending() and name not in _ALLOWED_WHILE_PAUSED:
                    paused = ("TASK PAUSED: an operator escalation is unresolved. The task "
                              "cannot continue until the operator resolves it.")
                    self.log(f"\n⏸ {paused}")
                    _memory.log_event("paused", by="escalation", tool=name, step=step)
                    return paused
                # ------------------------------------------------------

                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError as e:
                    arguments = {}
                    result = f"ERROR: your arguments were not valid JSON ({e})."
                else:
                    allowed, gate_result = self._gate(name, arguments)
                    if not allowed:
                        if gate_result and gate_result.startswith("TASK PAUSED"):
                            self.log(f"\n🔒 {gate_result}")
                            _memory.log_event("paused", by="permission", tool=name, step=step)
                            return gate_result
                        result = gate_result
                    elif not _budget.tool_call_available():
                        result = ("REFUSED: daily tool-call budget exhausted — wind down, "
                                  "summarize what you completed, and stop.")
                    else:
                        self.log(f"[{step}] {pretty_tool_call(name, arguments)}")
                        try:
                            result = run_tool(name, arguments)
                        except Exception:
                            result = "ERROR:\n" + traceback.format_exc(limit=3)
                        _budget.record_tool_call()

                result = str(result)
                if len(result) > 6000:
                    result = result[:6000] + "\n...[truncated]"
                if self.verbose and not name.endswith("screenshot"):
                    self.log(f"      → {result[:300]}")

                _memory.log_event("tool_call", step=step, tool=name,
                                  arguments=arguments, result=result[:500])

                # ---- self-correction: nudge after repeated failures ----
                if result.startswith("ERROR") or result.startswith("REFUSED") \
                        or result.startswith("Could not"):
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0
                if consecutive_errors >= 2:
                    nudge = _RETHINK_NUDGE.format(n=consecutive_errors)
                    self.log(f"\n🛠 {nudge}")
                    messages.append({"role": "system", "content": nudge})
                    _memory.log_event("self_correction", step=step,
                                      consecutive_errors=consecutive_errors)
                    consecutive_errors = 0
                    self.corrections += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
        else:
            final_answer += "\n(Step limit reached — raise OMNIUSE_MAX_STEPS if the task needs more.)"

        _memory.log_event("task_end", answer=final_answer[:500])
        return final_answer
