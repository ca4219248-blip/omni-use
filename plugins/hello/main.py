"""Example OmniUse plugin — copy this folder to make your own toolset."""

from __future__ import annotations


def hello_say(message: str) -> str:
    return f"👋 Hello from the hello plugin! You said: {message}"


def hello_now() -> str:
    import time
    return f"It is now {time.strftime('%Y-%m-%d %H:%M:%S')} on this machine."


TOOLS = {
    "hello_say": (hello_say, {
        "type": "function",
        "function": {
            "name": "hello_say",
            "description": "Say hello (example plugin tool).",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    }),
    "hello_now": (hello_now, {
        "type": "function",
        "function": {
            "name": "hello_now",
            "description": "Current time on this machine (example plugin tool).",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
}
