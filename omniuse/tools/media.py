"""Media toolset — image operations with Pillow (no API, fully local).

Resize, crop, convert formats, compress, strip EXIF, contact sheets
(thumbnail grids) and image info. Pairs naturally with the design toolset:
e.g. make a poster, then resize it for every platform in one call.
"""

from __future__ import annotations

from pathlib import Path

from omniuse.tools import memory as _memory


def _load(path: str):
    if not Path(path).is_file():
        return None, f"ERROR: file not found: {path}"
    try:
        from PIL import Image
        return Image.open(path), None
    except ImportError:
        return None, "ERROR: Pillow is not installed (pip install pillow)."
    except Exception as e:  # noqa: BLE001
        return None, f"ERROR: could not open the image ({e})."


def _save(img, path: str) -> str:
    try:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        _memory.log_event("media_saved", path=str(out), size=img.size)
        return f"Saved {out} ({img.width}x{img.height}, {out.stat().st_size:,} bytes)."
    except Exception as e:  # noqa: BLE001
        return f"ERROR: could not save ({e})."


def media_info(path: str) -> str:
    """Dimensions, format, mode and file size of an image."""
    img, err = _load(path)
    if err:
        return err
    return (f"Path: {path}\nFormat: {img.format or 'n/a'}\nSize: {img.width}x{img.height} px\n"
            f"Mode: {img.mode}\nFile size: {Path(path).stat().st_size:,} bytes")


def media_resize(path: str, width: int = 0, height: int = 0,
                 percent: int = 0, keep_ratio: bool = True, out_path: str = "") -> str:
    """Resize an image — exact w/h, or a percentage of the original."""
    img, err = _load(path)
    if err:
        return err
    if percent and not width and not height:
        scale = max(1, int(percent)) / 100
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    elif width and height:
        if not keep_ratio:
            new_size = (max(1, int(width)), max(1, int(height)))
        elif img.width > img.height:
            new_size = (max(1, int(width)), max(1, round(width * img.height / img.width)))
        else:
            new_size = (max(1, round(height * img.width / img.height)), max(1, int(height)))
    elif width:
        new_size = (max(1, int(width)), max(1, round(int(width) * img.height / img.width)))
    elif height:
        new_size = (max(1, round(int(height) * img.width / img.height)), max(1, int(height)))
    else:
        return "ERROR: give width, height, or percent."
    try:
        resized = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB").resize(new_size)
    except Exception as e:  # noqa: BLE001
        return f"ERROR: resize failed ({e})."
    src = Path(path)
    out = out_path or str(src.with_name(f"{src.stem}-resized{src.suffix}"))
    return _save(resized, out)


def media_crop(path: str, left: int = 0, top: int = 0, right: int = 0,
               bottom: int = 0, out_path: str = "") -> str:
    """Crop a rectangle (pixel coordinates: left, top, right, bottom)."""
    img, err = _load(path)
    if err:
        return err
    if right <= left or bottom <= top:
        return "ERROR: right must be > left and bottom must be > top."
    if right > img.width or bottom > img.height:
        return f"ERROR: crop box exceeds image bounds ({img.width}x{img.height})."
    try:
        cropped = img.crop((int(left), int(top), int(right), int(bottom)))
    except Exception as e:  # noqa: BLE001
        return f"ERROR: crop failed ({e})."
    src = Path(path)
    out = out_path or str(src.with_name(f"{src.stem}-cropped{src.suffix}"))
    return _save(cropped, out)


def media_convert(path: str, fmt: str = "png") -> str:
    """Convert an image to another format (png / jpg / webp / bmp / gif)."""
    img, err = _load(path)
    if err:
        return err
    fmt = (fmt or "").strip().lower().lstrip(".")
    supported = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}
    if fmt not in supported:
        return f"ERROR: format must be one of {sorted(supported)}."
    if fmt in ("jpg", "jpeg") and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    src = Path(path)
    out = str(src.with_suffix(f".{fmt}"))
    return _save(img, out)


def media_compress(path: str, quality: int = 70, out_path: str = "") -> str:
    """Re-save a JPEG/WebP at lower quality to shrink file size."""
    img, err = _load(path)
    if err:
        return err
    quality = max(10, min(95, int(quality)))
    src = Path(path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-compressed.jpg")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=quality, optimize=True)
    except Exception as e:  # noqa: BLE001
        return f"ERROR: compression failed ({e})."
    old, new = src.stat().st_size, out.stat().st_size
    saved = 100 * (1 - new / old) if old else 0
    return f"Compressed: {out} — {old:,} → {new:,} bytes ({saved:.0f}% smaller, quality {quality})."


def media_contact_sheet(folder: str, columns: int = 4, thumb: int = 256,
                        out_path: str = "") -> str:
    """Grid of thumbnails for every image in a folder (shop catalog view)."""
    root = Path(folder)
    if not root.is_dir():
        return f"ERROR: folder not found: {folder}"
    try:
        from PIL import Image
    except ImportError:
        return "ERROR: Pillow is not installed (pip install pillow)."
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
    images = sorted(p for p in root.iterdir() if p.suffix.lower() in exts and p.is_file())
    if not images:
        return f"No images in {folder}."
    columns = max(1, min(10, int(columns)))
    thumb = max(32, min(1024, int(thumb)))
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows * thumb), (24, 24, 24))
    for i, p in enumerate(images):
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((thumb, thumb))
            x, y = (i % columns) * thumb, (i // columns) * thumb
            sheet.paste(im, (x + (thumb - im.width) // 2, y + (thumb - im.height) // 2))
        except Exception:  # noqa: BLE001
            continue
    out = Path(out_path) if out_path else root / "contact-sheet.jpg"
    return _save(sheet, str(out)) + f" ({len(images)} thumbnails, {columns}/row)"


TOOLS = {
    "media_info": (media_info, {
        "type": "function",
        "function": {
            "name": "media_info",
            "description": "Dimensions, format and file size of an image.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }),
    "media_resize": (media_resize, {
        "type": "function",
        "function": {
            "name": "media_resize",
            "description": ("Resize an image — give width and/or height (aspect kept by default), "
                            "or percent of original size."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "percent": {"type": "integer", "description": "e.g. 50 = half size"},
                    "keep_ratio": {"type": "boolean"},
                    "out_path": {"type": "string", "description": "Output path (default: <name>-resized.<ext>)"},
                },
                "required": ["path"],
            },
        },
    }),
    "media_crop": (media_crop, {
        "type": "function",
        "function": {
            "name": "media_crop",
            "description": "Crop an image to a pixel rectangle (left, top, right, bottom).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "left": {"type": "integer"},
                    "top": {"type": "integer"},
                    "right": {"type": "integer"},
                    "bottom": {"type": "integer"},
                    "out_path": {"type": "string"},
                },
                "required": ["path", "left", "top", "right", "bottom"],
            },
        },
    }),
    "media_convert": (media_convert, {
        "type": "function",
        "function": {
            "name": "media_convert",
            "description": "Convert an image to png / jpg / webp / bmp / gif / tiff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "fmt": {"type": "string", "enum": ["png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"]},
                },
                "required": ["path", "fmt"],
            },
        },
    }),
    "media_compress": (media_compress, {
        "type": "function",
        "function": {
            "name": "media_compress",
            "description": "Shrink an image by re-saving at lower JPEG quality (default 70).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "quality": {"type": "integer", "description": "JPEG quality 10-95 (default 70)"},
                    "out_path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    }),
    "media_contact_sheet": (media_contact_sheet, {
        "type": "function",
        "function": {
            "name": "media_contact_sheet",
            "description": "Build a thumbnail grid (contact sheet) of every image in a folder — a one-glance catalog view.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string"},
                    "columns": {"type": "integer", "description": "Thumbnails per row (default 4)"},
                    "thumb": {"type": "integer", "description": "Thumbnail size in px (default 256)"},
                    "out_path": {"type": "string"},
                },
                "required": ["folder"],
            },
        },
    }),
}
