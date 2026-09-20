"""Shop toolset — sell ANY work, without spamming anyone.

What this toolset does:
  - catalog_list/add/remove: what you sell and at what price — ANY service
    (designs, writing, research, data work, tutorials, anything)
  - shop_proposal: a ready-to-send offer (price + preview + UPI QR + next
    steps) for a client who CONTACTED US
  - work_preview: make a partial/teaser version of any TEXT deliverable —
    the "watermark" equivalent for non-design work
  - shop_listing_draft: marketing copy + a poster for the operator's OWN
    account/page (post it yourself, or let the agent post it after
    policy_check — with AI disclosure)
  - prospect_add/prospect_list/prospect_status: track potential clients
    the OPERATOR plans to contact personally (google maps, referrals, …)
  - outreach_draft: a personalised first-contact message the OPERATOR sends
    personally — with a hard ONE-MESSAGE rule: no draft for anyone already
    contacted without a reply, or who declined.

What it deliberately does NOT do:
  - send unsolicited messages to strangers, scrape leads, or cold-DM people.
    That's spam — it breaks platform rules, it breaks OmniUse's
    non-negotiable rule #2, and it burns whatever reputation the shop has.
    The operator sends first-contact messages from their own account; the
    agent only researches prospects and drafts the text.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config
from omniuse.tools import memory as _memory


def _shop_dir() -> Path:
    d = Path(config.data_dir()) / "shop"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _catalog_path() -> Path:
    return _shop_dir() / "catalog.json"


def _catalog() -> list[dict]:
    p = _catalog_path()
    return json.loads(p.read_text()) if p.exists() else []


def _save_catalog(items: list[dict]) -> None:
    _catalog_path().write_text(json.dumps(items, indent=2, ensure_ascii=False))


def catalog_list() -> str:
    items = _catalog()
    if not items:
        return ("Catalog is empty — add items with catalog_add. "
                "Example: 'Instagram post design', ₹149.")
    return "\n".join(f"- {i['item']} — ₹{i['price']:.2f} ({i.get('note', '')})"
                     for i in items)


def catalog_add(item: str, price: float, note: str = "") -> str:
    if not item.strip():
        return "ERROR: item is required."
    try:
        price = float(price)
    except (TypeError, ValueError):
        return "ERROR: price must be a number."
    items = _catalog()
    items.append({"item": item.strip(), "price": price, "note": note.strip(),
                  "added": time.time()})
    _save_catalog(items)
    _memory.log_event("catalog_add", item=item, price=price)
    return f"Added to catalog: {item.strip()} @ ₹{price:.2f} ({len(items)} items total)."


def catalog_remove(item: str) -> str:
    items = _catalog()
    kept = [i for i in items if i["item"].lower() != item.strip().lower()]
    if len(kept) == len(items):
        return f"No catalog item named '{item}'."
    _save_catalog(kept)
    return f"Removed '{item}' from the catalog."


def shop_proposal(client: str, item: str, order_id: str = "") -> str:
    """Compose an offer message for a client who contacted us first."""
    entry = next((i for i in _catalog() if i["item"].lower() == item.strip().lower()), None)
    price = entry["price"] if entry else None
    price_line = f"₹{price:.2f}" if price else "(price from the operator — confirm before quoting)"
    payee = config.payee_name() or config.upi_vpa() or "(operator's UPI)"
    return (
        f"PROPOSAL for {client.strip()} (send via the channel they contacted us on):\n\n"
        f"Hi {client.strip()}! Thanks for reaching out 🙏\n"
        f"Here's a PREVIEW of your {item.strip()} order: <attach the preview file — "
        f"watermarked image for designs, work_preview() output for text work>\n"
        f"Price: {price_line}\n"
        f"To get the complete, full version:\n"
        f"1. Pay via UPI (QR below / UPI ID: {payee})\n"
        f"2. I'll verify and deliver the full work right away ✨\n\n"
        f"Attach: the preview + payment_qr({price if price else 'amount'}) image."
        + (f"\nOrder: {order_id}" if order_id else "")
    )


def work_preview(content: str, fraction: float = 0.4) -> str:
    """Make a partial preview of any TEXT deliverable (the watermark
    equivalent for non-design work: writing, research, data summaries,
    translations, code help...). Give it a file path or the text itself.

    The client sees the first `fraction` of the work + a clear notice that
    the rest arrives after payment. The full version only ever goes out via
    the order pipeline once the order is verified 'paid'."""
    from pathlib import Path as P
    text = content.strip()
    looks_like_path = len(text) < 300 and ("/" in text or text.startswith("."))
    try:
        is_file = looks_like_path and P(text).is_file()
    except OSError:
        is_file = False
    if looks_like_path and not is_file:
        return f"ERROR: file not found: {text}"
    if is_file:
        try:
            text = P(text).read_text(encoding="utf-8", errors="replace").strip()
        except OSError as e:
            return f"ERROR: could not read the file ({e})."
    if not text:
        return "ERROR: give me the text (or a path to a text file) to preview."
    try:
        fraction = min(0.9, max(0.1, float(fraction)))
    except (TypeError, ValueError):
        fraction = 0.4
    cut = max(1, int(len(text) * fraction))
    # cut at a word/line boundary so the preview doesn't end mid-word
    while cut < len(text) and not text[cut].isspace():
        cut += 1
    preview = text[:cut].rstrip()
    notice = (f"\n\n— — — PREVIEW — about {int(fraction * 100)}% of the work — "
              f"the complete version is delivered right after payment ✨ — — —")
    out = _shop_dir() / f"preview-{int(time.time())}.txt"
    out.write_text(preview + notice, encoding="utf-8")
    return (f"Preview saved to {out} ({len(preview)} of {len(text)} chars). Send THIS to "
            f"the client; keep the full version for after payment is verified.")


def shop_listing_draft(item: str, platform: str = "instagram") -> str:
    """Draft a listing/post for the operator's OWN page (they post it, or the
    agent posts it after policy_check — with AI disclosure)."""
    entry = next((i for i in _catalog() if i["item"].lower() == item.strip().lower()), None)
    if not entry:
        return f"ERROR: add '{item}' to the catalog first (catalog_add)."
    from omniuse.tools import design as _design
    poster = _design.design_poster(
        title=entry["item"], subtitle=f"starting ₹{entry['price']:.0f}",
        style="minimal", size="post",
        footer="DM to order")
    copy = (
        f"DRAFT LISTING ({platform}) — for the operator's own account:\n\n"
        f"✨ Custom {entry['item']} ✨\n"
        f"From ₹{entry['price']:.0f} — made just for you.\n"
        f" preview first, full work after payment.\n"
        f"DM to order!\n\n"
        f"(Remember: if the agent posts this itself, disclose it's an AI and "
        f"run policy_check('{platform}') first.)\n{poster}"
    )
    _memory.log_event("listing_draft", item=item, platform=platform)
    return copy


# ------------------------------------------------------------ prospects

PROSPECT_STATUSES = ("listed", "contacted", "replied", "not_interested", "converted")


def _prospects_path() -> Path:
    return _shop_dir() / "prospects.json"


def _prospects() -> list[dict]:
    p = _prospects_path()
    return json.loads(p.read_text()) if p.exists() else []


def _save_prospects(items: list[dict]) -> None:
    _prospects_path().write_text(json.dumps(items, indent=2, ensure_ascii=False))


def _prospect(name: str):
    target = name.strip().lower()
    return next((p for p in _prospects() if p["name"].lower() == target), None)


def prospect_add(name: str, source: str = "", contact: str = "", notes: str = "") -> str:
    """Track a potential client the OPERATOR plans to contact personally."""
    if not name.strip():
        return "ERROR: name is required."
    if _prospect(name):
        return f"Note: '{name.strip()}' is already tracked (status: {_prospect(name)['status']})."
    items = _prospects()
    items.append({"name": name.strip(), "source": source.strip(),
                  "contact": contact.strip(), "notes": notes.strip(),
                  "status": "listed", "history": []})
    _save_prospects(items)
    _memory.log_event("prospect_added", name=name.strip(), source=source.strip())
    return (f"Tracking prospect '{name.strip()}' [listed]. Remember: the OPERATOR sends "
            "the first message personally — the agent only drafts it (outreach_draft).")


def prospect_list() -> str:
    items = _prospects()
    if not items:
        return "No prospects tracked yet."
    return "\n".join(f"- {p['name']} [{p['status']}]"
                     + (f" ({p['source']})" if p["source"] else "")
                     + (f" — {p['notes']}" if p["notes"] else "")
                     for p in items)


def prospect_status(name: str, status: str) -> str:
    """Update a prospect's status as the operator works the lead."""
    if status.strip().lower() not in PROSPECT_STATUSES:
        return f"ERROR: status must be one of {PROSPECT_STATUSES}"
    items = _prospects()
    for item in items:
        if item["name"].lower() == name.strip().lower():
            item["status"] = status.strip().lower()
            item["history"] = item.get("history", []) + [{"status": item["status"], "ts": time.time()}]
            _save_prospects(items)
            _memory.log_event("prospect_status", name=item["name"], status=item["status"])
            return f"'{item['name']}' → {item['status']}"
    return f"ERROR: no prospect named '{name}'."


def outreach_draft(name: str, item: str, channel: str = "whatsapp") -> str:
    """Draft a personalised FIRST-CONTACT message for the operator to send
    THEMSELVES. The agent never sends it. One message per prospect — refuses
    if they were already contacted without a reply, or if they declined."""
    entry = next((i for i in _catalog() if i["item"].lower() == item.strip().lower()), None)
    if not entry:
        return f"ERROR: add '{item}' to the catalog first (catalog_add)."
    p = _prospect(name)
    if p is None:
        return (f"ERROR: track '{name}' first with prospect_add — every prospect must "
                "be on record so the one-message rule is enforced.")
    if p["status"] == "contacted":
        return (f"REFUSED: '{p['name']}' was already contacted and hasn't replied. "
                "One message per prospect — no follow-ups on silence. If they reply, "
                "update with prospect_status(name, 'replied') and continue the conversation.")
    if p["status"] == "not_interested":
        return (f"REFUSED: '{p['name']}' declined. Do not contact them again — "
                "that's the fastest way to get reported and banned.")
    price = entry["price"]
    draft = (
        f"FIRST-CONTACT DRAFT for {channel} — THE OPERATOR SENDS THIS PERSONALLY (never the agent):\n\n"
        f"Hi {p['name']}! I'm {config.payee_name() or 'the operator'} — I do custom "
        f"{entry['item'].lower()} work for small businesses" +
        (f" like {p['notes'][:60]}" if p.get("notes") else "") +
        f". I've done a sample of the kind of work I can do for you — want me to send it over? "
        f"If you like it, it's ₹{price:.0f} for the full job, no payment until you've seen a preview. "
        f"If it's not for you, no worries at all. 🙏\n\n"
        f"RULES (enforced): send this ONCE from your own account; if no reply, leave it — "
        f"prospect_status('{p['name']}', 'contacted') after sending, "
        f"'not_interested' if they decline, 'replied' if they answer."
    )
    return draft


TOOLS = {
    "catalog_list": (catalog_list, {
        "type": "function",
        "function": {
            "name": "catalog_list",
            "description": "Show what the shop sells and at what prices.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "catalog_add": (catalog_add, {
        "type": "function",
        "function": {
            "name": "catalog_add",
            "description": "Add an item (ANY service) to the shop catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "e.g. 'Instagram post design', 'Assignment writeup'"},
                    "price": {"type": "number"},
                    "note": {"type": "string", "description": "Short description"},
                },
                "required": ["item", "price"],
            },
        },
    }),
    "catalog_remove": (catalog_remove, {
        "type": "function",
        "function": {
            "name": "catalog_remove",
            "description": "Remove an item from the shop catalog.",
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string"}},
                "required": ["item"],
            },
        },
    }),
    "work_preview": (work_preview, {
        "type": "function",
        "function": {
            "name": "work_preview",
            "description": (
                "Make a partial preview of any TEXT deliverable (writing, research, data "
                "work, translations...) — the watermark equivalent for non-design work. "
                "Give a file path or the text itself; returns a saved preview file with "
                "a payment notice. Use for ANY service that isn't an image: preview-first "
                "selling applies to all work, not just designs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full work text, or a path to it"},
                    "fraction": {"type": "number", "description": "How much to show, 0.1-0.9 (default 0.4)"},
                },
                "required": ["content"],
            },
        },
    }),
    "shop_proposal": (shop_proposal, {
        "type": "function",
        "function": {
            "name": "shop_proposal",
            "description": (
                "Compose an offer for a client who CONTACTED US first: price, "
                "preview, UPI QR instructions, delivery promise. "
                "For inbound inquiries only — never send to strangers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {"type": "string", "description": "Client's name/handle"},
                    "item": {"type": "string", "description": "Catalog item"},
                    "order_id": {"type": "string"},
                },
                "required": ["client", "item"],
            },
        },
    }),
    "shop_listing_draft": (shop_listing_draft, {
        "type": "function",
        "function": {
            "name": "shop_listing_draft",
            "description": (
                "Draft a listing post (copy + poster) for the operator's OWN page. "
                "The operator posts it, or the agent posts it after policy_check "
                "with AI disclosure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "platform": {"type": "string", "description": "e.g. instagram, whatsapp status"},
                },
                "required": ["item"],
            },
        },
    }),
    "prospect_add": (prospect_add, {
        "type": "function",
        "function": {
            "name": "prospect_add",
            "description": (
                "Track a potential client the operator plans to contact PERSONALLY. "
                "Every prospect must be on record so the one-message rule is enforced."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source": {"type": "string", "description": "e.g. google maps, instagram"},
                    "contact": {"type": "string", "description": "phone/handle"},
                    "notes": {"type": "string", "description": "What kind of business they run"},
                },
                "required": ["name"],
            },
        },
    }),
    "prospect_list": (prospect_list, {
        "type": "function",
        "function": {
            "name": "prospect_list",
            "description": "Show all tracked prospects and their statuses.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "prospect_status": (prospect_status, {
        "type": "function",
        "function": {
            "name": "prospect_status",
            "description": "Update a prospect's status as the operator works the lead (listed/contacted/replied/not_interested/converted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": list(PROSPECT_STATUSES)},
                },
                "required": ["name", "status"],
            },
        },
    }),
    "outreach_draft": (outreach_draft, {
        "type": "function",
        "function": {
            "name": "outreach_draft",
            "description": (
                "Draft a personalised FIRST-CONTACT message for a prospect — the "
                "OPERATOR sends it themselves from their own account; the agent never "
                "sends it. One message per prospect: refuses to draft for anyone "
                "already contacted without a reply, or who declined."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "item": {"type": "string", "description": "Catalog item to pitch"},
                    "channel": {"type": "string", "description": "e.g. whatsapp, sms, email"},
                },
                "required": ["name", "item"],
            },
        },
    }),
}
