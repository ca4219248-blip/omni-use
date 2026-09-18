"""The OmniUse agent loop: an LLM that thinks, calls tools, observes, repeats.

    task ──▶ LLM ──▶ tool call ──▶ result ──▶ LLM ──▶ ... ──▶ final answer
"""

from __future__ import annotations

import json
import traceback

from omniuse import config
from omniuse.llm import chat, pretty_tool_call
from omniuse.tools import get_tool_schemas, run_tool

SYSTEM_PROMPT = """\
You are OmniUse, an AI agent with hands and eyes.

You can control:
- A real web browser (Playwright/Chromium): open pages, click, type, scroll, read text, take screenshots.
- An Android phone over ADB: tap, swipe, type, press keys, take screenshots, run shell commands.
- The local computer: run shell commands, read/write/list files.
- Your eyes: look_at_image() lets you SEE any screenshot you take.

How to work:
1. Break the task into small steps. One tool call at a time.
2. Observe each result before deciding the next action. Screenshots tell you the truth —
   after browser_screenshot / mobile_screenshot, ALWAYS use look_at_image to check what happened.
3. browser_text and browser_links give you a page's content cheaply; prefer them over screenshots
   when the task is text-based.
4. If something fails, read the error, adjust (try a different selector, scroll, retry) and continue.
5. Never invent results. Only report what you actually observed.
6. When the task is done, stop calling tools and give a clear final answer.
"""


class Agent:
    """A tool-using agent.

    Args:
        toolsets: Which toolsets to enable. None = all of
            {"browser", "mobile", "system", "vision"}.
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
                name = call["function"]["name"]
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
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })
        else:
            final_answer += "\n(Step limit reached — raise OMNIUSE_MAX_STEPS if the task needs more.)"

        return final_answer
