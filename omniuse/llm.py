"""Thin wrapper around any OpenAI-compatible chat API.

Works with OpenAI, Groq, OpenRouter, Together, Sarvam, or a local
server (vLLM / Ollama / llama.cpp) — anything that speaks the
/chat/completions protocol with tool calling.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI

from omniuse import config

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.api_key(), base_url=config.base_url())
    return _client


def chat(messages, tools=None) -> dict:
    """One chat completion. Returns the assistant message as a plain dict."""
    response = _get_client().chat.completions.create(
        model=config.model(),
        messages=messages,
        tools=tools or None,
    )
    return response.choices[0].message.model_dump(exclude_none=True)


def describe_image(image_path: str, question: str = "Describe this screen in detail.") -> str:
    """Send an image to a vision-capable model and return its answer."""
    data = base64.b64encode(Path(image_path).read_bytes()).decode()
    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    response = _get_client().chat.completions.create(
        model=config.model(),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""


def pretty_tool_call(name: str, arguments: dict) -> str:
    args = json.dumps(arguments, ensure_ascii=False)
    if len(args) > 200:
        args = args[:200] + "…"
    return f"{name}({args})"
