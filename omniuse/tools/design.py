"""Design toolset — generate designs, watermark previews, prepare deliverables.

Two ways to create:
  - design_poster(): local template-based posters (PIL) — works offline:
    flyers, festival posts, quotes, banners, business cards.
  - design_ai_image(): AI image generation, if the configured LLM provider
    offers an images API.

Watermark-first selling: always send the watermarked preview; the clean
file is only handed over after payment is verified (see payments toolset).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from omniuse import config

SIZES = {"square": (1080, 1080), "post": (1080, 1350), "story": (1080, 1920),
         "banner": (1200, 400), "card": (1050, 600)}

STYLES = {
    "minimal":    ((250, 250, 250), (30, 30, 30), (110, 110, 110)),
    "dark":       ((18, 18, 24), (245, 245, 245), (150, 150, 170)),
    "festival":   ((255, 70, 40), (255, 255, 255), (255, 220, 120)),
    "ocean":      ((8, 60, 110), (240, 250, 255), (120, 190, 255)),
    "sunrise":    ((255, 120, 60), (60, 20, 40), (255, 230, 150)),
}

_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def _designs_dir() -> Path:
    d = Path(os.getenv("OMNIUSE_DESIGNS_DIR", "designs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _font(size: int):
    from PIL import ImageFont
    for path in _FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30] or "design"


def design_poster(title: str, subtitle: str = "", style: str = "minimal",
                  size: str = "square", footer: str = "") -> str:
    """Generate a poster locally with PIL (no external API needed)."""
    from PIL import Image, ImageDraw

    if not title.strip():
        return "ERROR: title is required."
    if style not in STYLES:
        return f"ERROR: style must be one of {sorted(STYLES)}"
    if size not in SIZES:
        return f"ERROR: size must be one of {sorted(SIZES)}"

    bg, fg, accent = STYLES[style]
    width, height = SIZES[size]
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # simple accent bar + centered text stack
    draw.rectangle([0, 0, width, max(8, height // 90)], fill=accent)
    draw.rectangle([0, height - max(8, height // 90), width, height], fill=accent)

    title_font = _font(max(28, width // (12 if len(title) > 40 else 8)))
    sub_font = _font(max(20, width // 26))
    foot_font = _font(max(16, width // 40))

    def center(text: str, font, y: int, color) -> int:
        for line in text.split("\n"):
            box = draw.textbbox((0, 0), line, font=font)
            draw.text(((width - (box[2] - box[0])) / 2, y), line, font=font, fill=color)
            y += (box[3] - box[1]) + font.size * 0.55
        return y

    y = height * 0.30 if subtitle else height * 0.38
    y = center(title, title_font, y, fg)
    if subtitle:
        y = center(subtitle, sub_font, y + height * 0.03, accent)
    if footer:
        center(footer, foot_font, height * 0.90, accent)

    path = _designs_dir() / f"{_slug(title)}-{int(time.time())}.png"
    img.save(path)
    return f"Poster saved to {path} ({size}, {style}). Send the WATERMARKED version until payment is verified."


def design_ai_image(prompt: str, size: str = "1024x1024") -> str:
    """Generate an image with the provider's images API (if available)."""
    if not prompt.strip():
        return "ERROR: prompt is required."
    from omniuse.llm import _get_client
    try:
        response = _get_client().images.generate(
            model=os.getenv("OMNIUSE_IMAGE_MODEL", "gpt-image-1"),
            prompt=prompt, size=size, n=1)
        import base64
        item = response.data[0]
        data = getattr(item, "b64_json", None)
        if data:
            path = _designs_dir() / f"{_slug(prompt)}-{int(time.time())}.png"
            path.write_bytes(base64.b64decode(data))
            return f"AI image saved to {path}"
        if getattr(item, "url", None):
            return (f"Image URL (download before delivering): {item.url}")
        return "ERROR: provider returned no image data."
    except Exception as e:  # noqa: BLE001
        return (f"ERROR: image generation failed ({type(e).__name__}: {e}). "
                "Falling back to design_poster() is a good move.")


def design_watermark(image_path: str) -> str:
    """Create a watermarked preview copy — for sending BEFORE payment."""
    from PIL import Image, ImageDraw

    src = Path(image_path)
    if not src.is_file():
        return f"ERROR: file not found: {image_path}"
    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    mark = f"  PREVIEW • {config.payee_name() or 'OmniUse'} • PAYMENT PENDING  "
    font = _font(max(20, img.width // 30))
    step = max(60, img.width // 8)
    for y in range(0, img.height + step * 4, step):
        for x in range(0 - img.width, img.width, step * 6):
            draw.text((x, y), mark, font=font, fill=(255, 255, 255, 95))
    overlay = overlay.rotate(25, center=(img.width / 2, img.height / 2))
    out = Image.alpha_composite(img, overlay).convert("RGB")
    path = src.with_name(f"{src.stem}-watermarked{src.suffix}")
    out.save(path)
    return f"Watermarked preview saved to {path} — send THIS file, never the original, until payment is verified."


TOOLS = {
    "design_poster": (design_poster, {
        "type": "function",
        "function": {
            "name": "design_poster",
            "description": (
                "Generate a poster/flyer design locally (PIL templates — no API "
                "needed). Great for festival posts, flyers, quotes, banners."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "style": {"type": "string", "enum": sorted(STYLES)},
                    "size": {"type": "string", "enum": sorted(SIZES)},
                    "footer": {"type": "string", "description": "Small footer line, e.g. 'DM to order'"},
                },
                "required": ["title"],
            },
        },
    }),
    "design_ai_image": (design_ai_image, {
        "type": "function",
        "function": {
            "name": "design_ai_image",
            "description": "Generate an image with the provider's images API (needs a provider that supports image generation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "size": {"type": "string", "description": "e.g. 1024x1024, 1536x1024"},
                },
                "required": ["prompt"],
            },
        },
    }),
    "design_watermark": (design_watermark, {
        "type": "function",
        "function": {
            "name": "design_watermark",
            "description": "Create a watermarked preview copy of a design — always send this until payment is verified.",
            "parameters": {
                "type": "object",
                "properties": {"image_path": {"type": "string"}},
                "required": ["image_path"],
            },
        },
    }),
}
