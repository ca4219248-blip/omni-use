"""QR toolset — generate QR codes for anything (text, URL, WiFi, contact).

The UPI payment QR lives in the payments toolset (payment_qr) because it
follows the shop's money rules. This toolset is the generic everyday one:
share a link, a WiFi password, a vCard, or any text as a scannable PNG.
"""

from __future__ import annotations

import time
from pathlib import Path

from omniuse import config


def _qrcode():
    try:
        import qrcode
        return qrcode, None
    except ImportError:
        return None, "ERROR: the 'qrcode' package is not installed (pip install qrcode)."


def _save_qr(data: str, name_hint: str = "") -> str:
    qrcode, err = _qrcode()
    if err:
        return err
    d = Path(config.data_dir()) / "qr"
    d.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in (name_hint or "qr"))[:30].strip("-") or "qr"
    out = d / f"{slug}-{int(time.time())}.png"
    img = qrcode.make(data)
    img.save(out)
    return f"QR saved to {out} ({len(data)} chars encoded). Send/share the image."


def qr_text(text: str, name: str = "") -> str:
    """Encode any text into a QR code."""
    if not (text or "").strip():
        return "ERROR: text is required."
    if len(text) > 2000:
        return "ERROR: too much text for one QR (2000 chars max) — use a file link instead."
    return _save_qr(text, name)


def qr_url(url: str, name: str = "") -> str:
    """Encode a URL (adds https:// if no scheme is present)."""
    url = (url or "").strip()
    if not url:
        return "ERROR: url is required."
    if "://" not in url:
        url = "https://" + url
    return _save_qr(url, name or url.split("//")[-1][:20])


def qr_wifi(ssid: str, password: str = "", security: str = "WPA",
            hidden: bool = False, name: str = "") -> str:
    """Encode WiFi credentials (scanning it joins the network)."""
    if not (ssid or "").strip():
        return "ERROR: ssid is required."
    security = (security or "WPA").strip().upper()
    if security not in ("WPA", "WEP", "nopass"):
        return "ERROR: security must be WPA, WEP or nopass."
    if security != "nopass" and not password:
        return "ERROR: password is required unless security is 'nopass'."
    data = f"WIFI:T:{security};S:{ssid};P:{password};;" if security != "nopass" \
        else f"WIFI:T:nopass;S:{ssid};;"
    if hidden:
        data = data.replace(";;", ";H:true;;", 1)
    return _save_qr(data, name or ssid)


def qr_vcard(name: str, phone: str = "", email: str = "", org: str = "",
             url: str = "", note: str = "") -> str:
    """Encode a contact card (scanning it adds the contact)."""
    if not (name or "").strip():
        return "ERROR: name is required."
    fields = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name.strip()}"]
    if phone.strip():
        fields.append(f"TEL:{phone.strip()}")
    if email.strip():
        fields.append(f"EMAIL:{email.strip()}")
    if org.strip():
        fields.append(f"ORG:{org.strip()}")
    if url.strip():
        fields.append(f"URL:{url.strip()}")
    if note.strip():
        fields.append(f"NOTE:{note.strip()[:100]}")
    fields.append("END:VCARD")
    return _save_qr("\n".join(fields), name)


TOOLS = {
    "qr_text": (qr_text, {
        "type": "function",
        "function": {
            "name": "qr_text",
            "description": "Encode any text (up to 2000 chars) into a QR code image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "name": {"type": "string", "description": "Filename hint"},
                },
                "required": ["text"],
            },
        },
    }),
    "qr_url": (qr_url, {
        "type": "function",
        "function": {
            "name": "qr_url",
            "description": "Encode a URL into a QR code (https:// added if missing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["url"],
            },
        },
    }),
    "qr_wifi": (qr_wifi, {
        "type": "function",
        "function": {
            "name": "qr_wifi",
            "description": "Encode WiFi credentials — guests scan it and join (WPA/WEP/nopass).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ssid": {"type": "string"},
                    "password": {"type": "string"},
                    "security": {"type": "string", "enum": ["WPA", "WEP", "nopass"]},
                    "hidden": {"type": "boolean"},
                    "name": {"type": "string"},
                },
                "required": ["ssid"],
            },
        },
    }),
    "qr_vcard": (qr_vcard, {
        "type": "function",
        "function": {
            "name": "qr_vcard",
            "description": "Encode a contact card (name, phone, email...) — scanning it adds the contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "org": {"type": "string"},
                    "url": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    }),
}
