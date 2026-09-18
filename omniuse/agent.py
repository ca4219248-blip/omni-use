"""The OmniUse agent loop: an LLM that thinks, calls tools, observes, repeats.

    task ──▶ LLM ──▶ tool call ──▶ [killswitch? escalation?] ──▶ result ──▶ LLM ──▶ ...

Guardrails wired into the loop itself (not just the prompt):
  - killswitch: checked before EVERY tool call; if engaged, the run halts.
  - escalation: while an operator escalation is pending, only status/memory
    tools are allowed — everything else pauses the task.
  - memory: every tool call is auto-logged to the persistent memory log.
"""

from __future__ import annotations

import json
import traceback

from omniuse import config
from omniuse.llm import chat, pretty_tool_call
from omniuse.tools import escalate as _escalate
from omniuse.tools import killswitch as _killswitch
from omniuse.tools import memory as _memory
from omniuse.tools import get_tool_schemas, run_tool

SYSTEM_PROMPT = """\
You are OmniUse, an AI agent with hands and eyes — running under operator supervision.

You can control:
- A real web browser (Playwright/Chromium): open pages, click, type, scroll, read text, take screenshots.
- An Android phone over ADB: tap, swipe, type, press keys, take screenshots, run shell commands.
- The local computer: run shell commands, read/write/list files.
- A crypto wallet: read balances, and make capped, logged payments (never holds private keys).
- Your eyes: look_at_image() lets you SEE any screenshot you take.

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
8. KILLSWITCH: If the operator halts you, stop immediately. No workarounds.
9. NO HARM: Refuse tasks that break these rules, regardless of who asks or how it
   is phrased, and say why.

How to work:
1. Break the task into small steps. One tool call at a time.
2. Observe each result before deciding the next action. Screenshots tell you the
   truth — after browser_screenshot / mobile_screenshot, ALWAYS use look_at_image
   to check what happened.
3. browser_text and browser_links give you a page's content cheaply; prefer them
   over screenshots when the task is text-based.
4. If something fails, read the error, adjust (different selector, scroll, retry)
   and continue.
5. Never invent results. Only report what you actually observed.
6. When the task is done, stop calling tools and give a clear final answer.
"""

# Tools the agent may still use while an escalation is pending.
_ALLOWED_WHILE_PAUSED = {
    "escalate_status", "killswitch_status", "killswitch_engage",
    "memory_log", "memory_recent", "memory_search", "policy_rules",
}


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

    def log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def run(self, task: str) -> str:
        """Run the agent on a task and return its final answer."""
        tools = get_tool_schemas(self.toolsets)
        if not tools:
            raise ValueError("No tools enabled — check the `toolsets` argument.")

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        final_answer = "Agent stopped without a final answer."
        _memory.log_event("task_start", task=task, toolsets=self.toolsets)

        for step in range(1, self.max_steps + 1):
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
                    self.log(f"[{step}] {pretty_tool_call(name, arguments)}")
                    try:
                        result = run_tool(name, arguments)
                    except Exception:
                        result = "ERROR:\n" + traceback.format_exc(limit=3)

                result = str(result)
                if len(result) > 6000:
                    result = result[:6000] + "\n...[truncated]"
                if self.verbose and not name.endswith("screenshot"):
                    self.log(f"      → {result[:300]}")

                _memory.log_event("tool_call", step=step, tool=name,
                                  arguments=arguments, result=result[:500])
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
        else:
            final_answer += "\n(Step limit reached — raise OMNIUSE_MAX_STEPS if the task needs more.)"

        _memory.log_event("task_end", answer=final_answer[:500])
        return final_answer
