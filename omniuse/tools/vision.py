"""Vision toolset — the agent's eyes.

Use after browser_screenshot / mobile_screenshot to actually SEE the screen.
Requires a vision-capable model (e.g. gpt-4o-mini, gpt-4o, or a VLM endpoint).
"""

from __future__ import annotations

from pathlib import Path

from omniuse.llm import describe_image


def look_at_image(image_path: str, question: str = "Describe this screen in detail.") -> str:
    path = Path(image_path)
    if not path.is_file():
        return f"ERROR: file not found: {image_path}"
    return describe_image(str(path), question)


TOOLS = {
    "look_at_image": (look_at_image, {
        "type": "function",
        "function": {
            "name": "look_at_image",
            "description": (
                "Look at a saved image (screenshot) with your vision and answer a "
                "question about it. Use after browser_screenshot or mobile_screenshot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path returned by the screenshot tool"},
                    "question": {"type": "string", "description": "What to look for (default: describe the screen)"},
                },
                "required": ["image_path"],
            },
        },
    }),
}
