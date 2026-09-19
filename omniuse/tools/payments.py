"""Payments toolset — UPI QR, order tracking, payment verification.

The selling flow (watermark-first, verify-then-deliver):

    order_create(client, item, price)          → order id
    (generate the design, design_watermark it)
    order_attach(order_id, preview, final)     → record file paths
    send the client: watermarked preview + payment_qr(price)
    client pays → sends a screenshot → payment_verify_screenshot(...)
      → order becomes 'payment_claimed' (NOT paid — screenshots can be edited)
    payment_check_sms(...) on the operator's phone finds the credit SMS
      → order becomes 'paid' automatically
    then (and only then) send the clean, full-resolution file.

Honesty rules built in:
  - A screenshot alone NEVER marks an order paid — only a bank/UPI credit SMS
    or the operator (order_mark_paid with the operator token) can.
  - Every state change is written to the memory log.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from omniuse import config
from omniuse.tools import memory as _memory

STATES = ("created", "preview_sent", "payment_claimed", "paid", "delivered")


def _shop_dir() -> Path:
    d = Path(config.data_dir()) / "shop"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _orders_path() -> Path:
    return _shop_dir() / "orders.json"


def _orders() -> list[dict]:
    p = _orders_path()
    return json.loads(p.read_text()) if p.exists() else []


def _save_orders(orders: list[dict]) -> None:
    _orders_path().write_text(json.dumps(orders, indent=2, ensure_ascii=False))


def _find(order_id: str):
    for order in _orders():
        if order["id"] == order_id:
            return order
    return None


def _transition(order: dict, state: str, note: str = "") -> None:
    """Apply a state change to the order dict in hand, then persist it
    (merge by id, so concurrent edits to other orders survive)."""
    order["state"] = state
    order["history"] = order.get("history", []) + [{"state": state, "note": note, "ts": time.time()}]
    orders = _orders()
    for i, existing in enumerate(orders):
        if existing["id"] == order["id"]:
            orders[i] = order
            break
    else:
        orders.append(order)
    _save_orders(orders)
    _memory.log_event("order_state", id=order["id"], state=state, note=note)


# ---------------------------------------------------------------- orders


def order_create(client: str, item: str, price: float) -> str:
    if not client.strip() or not item.strip():
        return "ERROR: client and item are required."
    try:
        price = float(price)
    except (TypeError, ValueError):
        return "ERROR: price must be a number."
    if price <= 0:
        return "ERROR: price must be positive."
    import secrets
    order = {"id": f"ord-{int(time.time())}-{secrets.token_hex(3)}",
             "client": client.strip(),
             "item": item.strip(), "price": price, "state": "created",
             "preview": "", "final": "", "history": []}
    orders = _orders()
    orders.append(order)
    _save_orders(orders)
    _memory.log_event("order_created", id=order["id"], client=client, item=item, price=price)
    return (f"Order {order['id']} created for {client.strip()} — {item.strip()} @ ₹{price:.2f}. "
            "Next: design it, watermark it, order_attach the files, then send preview + QR.")


def order_attach(order_id: str, preview: str, final: str) -> str:
    order = _find(order_id)
    if not order:
        return f"ERROR: no order '{order_id}'."
    if not Path(preview).is_file() or not Path(final).is_file():
        return "ERROR: both file paths must exist (create the design first, then the watermarked copy)."
    order["preview"], order["final"] = preview, final
    _transition(order, "preview_sent", "files attached")
    return (f"Attached preview + final to {order_id}. Send ONLY the preview (watermarked) "
            f"with payment_qr({order['price']}). Keep the final file for after verification.")


def order_status(order_id: str = "") -> str:
    orders = _orders()
    if order_id:
        order = _find(order_id)
        if not order:
            return f"ERROR: no order '{order_id}'."
        return json.dumps(order, indent=2, ensure_ascii=False)
    if not orders:
        return "No orders yet."
    return "\n".join(f"- {o['id']} [{o['state']}] {o['client']} — {o['item']} ₹{o['price']}"
                     for o in orders)


def order_mark_paid(order_id: str, operator_token: str = "", reference: str = "") -> str:
    """Operator-only: mark an order paid (e.g. after checking the UPI app)."""
    order = _find(order_id)
    if not order:
        return f"ERROR: no order '{order_id}'."
    token = config.operator_token()
    if not token or operator_token != token:
        return ("REFUSED: only the operator can mark an order paid this way. "
                "Use payment_check_sms() for automatic verification, or ask the "
                "operator to confirm (they hold the operator token).")
    _transition(order, "paid", f"operator confirmed {reference}".strip())
    return f"Order {order_id} marked PAID (operator-confirmed). You may now deliver the final file."


def order_delivered(order_id: str) -> str:
    order = _find(order_id)
    if not order:
        return f"ERROR: no order '{order_id}'."
    if order["state"] != "paid":
        return (f"REFUSED: order {order_id} is '{order['state']}', not 'paid'. "
                "Never deliver the clean file before payment is verified.")
    _transition(order, "delivered")
    return f"Order {order_id} delivered. Final file: {order['final']}"


# ---------------------------------------------------------------- payment


def payment_qr(amount: float, note: str = "design order") -> str:
    """Generate a UPI QR (with amount pre-filled) for the operator's VPA."""
    vpa = config.upi_vpa()
    if not vpa:
        return "ERROR: OMNIUSE_UPI_VPA is not set (the operator's UPI ID)."
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "ERROR: amount must be a number."
    from urllib.parse import quote
    uri = (f"upi://pay?pa={quote(vpa)}&pn={quote(config.payee_name() or 'Payment')}"
           f"&am={amount:.2f}&cu=INR&tn={quote(note[:40])}")
    try:
        import qrcode
        img = qrcode.make(uri)
        path = _shop_dir() / f"upi-qr-{int(time.time())}.png"
        img.save(path)
        return f"UPI QR saved to {path} (₹{amount:.2f} to {vpa}). Send this image to the client."
    except ImportError:
        return (f"Send this UPI link to the client (any UPI app opens it): {uri} "
                "(install the 'qrcode' package to generate QR images)")


def payment_verify_screenshot(image_path: str, order_id: str = "") -> str:
    """Read a client's payment screenshot with vision — claims, never confirms."""
    from pathlib import Path as P
    if not P(image_path).is_file():
        return f"ERROR: file not found: {image_path}"
    from omniuse.llm import describe_image
    question = (
        "This is supposed to be a UPI payment screenshot. Extract exactly: "
        "1) app name, 2) amount paid (₹), 3) date and time, 4) UPI reference / "
        "transaction ID, 5) payer name, 6) any signs of editing or inconsistency. "
        "Reply in plain lines: app=, amount=, datetime=, ref=, payer=, notes=."
    )
    try:
        extraction = describe_image(image_path, question)
    except Exception as e:  # noqa: BLE001
        return f"ERROR reading the screenshot: {e}"
    order = _find(order_id) if order_id else None
    claimed = ""
    if order:
        _transition(order, "payment_claimed", f"client screenshot: {extraction[:200]}")
        claimed = (f" Order {order_id} is now 'payment_claimed' — NOT paid. Verify with "
                   "payment_check_sms() or the operator before delivering anything.")
    return (f"SCREENSHOT READ (unverified — screenshots can be edited):\n{extraction}\n"
            f"Next step: confirm the credit actually arrived — payment_check_sms() on the "
            f"operator's phone, or operator confirmation.{claimed}")


def payment_check_sms(minutes: int = 120, mark_paid: bool = True) -> str:
    """Check the operator's phone SMS inbox for a UPI/bank credit confirmation.

    Requires the phone to be connected over ADB with SMS read permission.
    A matching credit SMS is the only automatic way an order becomes 'paid'.
    """
    from omniuse.tools import mobile as _mobile
    since = int((time.time() - max(1, minutes) * 60) * 1000)
    try:
        raw = _mobile._shell(
            f"content query --uri content://sms/inbox "
            f"--projection address:body:date --where \"date>{since}\"")
    except Exception as e:  # noqa: BLE001
        return (f"Could not read SMS ({e}). Is the phone connected with SMS permission? "
                "The operator can also confirm manually with order_mark_paid.")
    import re
    hits = []
    for line in raw.splitlines():
        body = re.search(r"body=([^,]*)", line)
        if not body:
            continue
        text = body.group(1)
        if re.search(r"credited|received|UPI/|bank", text, re.IGNORECASE):
            hits.append(text.strip()[:200])
    if not hits:
        return "No credit SMS found in the given window. Do NOT deliver until payment is confirmed."
    paid = []
    for text in hits:
        amounts = [float(a.replace(",", "")) for a in
                   re.findall(r"(?:Rs\\.?|₹|INR)\\s*([0-9]+(?:\\.[0-9]+)?)", text)]
        for order in _orders():
            if order["state"] in ("payment_claimed", "preview_sent", "created") \\
                    and abs(order["price"] - (amounts[0] if amounts else -1)) < 0.01:
                if mark_paid:
                    _transition(order, "paid", f"credit SMS: {text[:150]}")
                paid.append(f"{order['id']} ₹{order['price']:.2f}")
    if paid:
        return (f"PAYMENT VERIFIED via SMS for: {', '.join(paid)} — "
                f"you may now deliver the final files. (matched: {hits[0][:120]})")
    return (f"Credit SMS found but no matching order amount: {hits[0][:150]}. "
            "Check payment_check_sms window or the order price.")


TOOLS = {
    "order_create": (order_create, {
        "type": "function",
        "function": {
            "name": "order_create",
            "description": "Create a new design order for a client (tracks state from created → paid → delivered).",
            "parameters": {
                "type": "object",
                "properties": {
                    "client": {"type": "string", "description": "Client name/handle"},
                    "item": {"type": "string", "description": "What they ordered"},
                    "price": {"type": "number", "description": "Price in ₹"},
                },
                "required": ["client", "item", "price"],
            },
        },
    }),
    "order_attach": (order_attach, {
        "type": "function",
        "function": {
            "name": "order_attach",
            "description": "Attach the watermarked preview and the final (clean) file to an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "preview": {"type": "string", "description": "Path to the WATERMARKED file to send"},
                    "final": {"type": "string", "description": "Path to the clean full file (deliver only after verified payment)"},
                },
                "required": ["order_id", "preview", "final"],
            },
        },
    }),
    "order_status": (order_status, {
        "type": "function",
        "function": {
            "name": "order_status",
            "description": "Show one order (or all orders) and their states.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Empty = list all"}},
            },
        },
    }),
    "order_mark_paid": (order_mark_paid, {
        "type": "function",
        "function": {
            "name": "order_mark_paid",
            "description": (
                "Operator-only: mark an order paid after checking the UPI app/bank. "
                "Needs the operator's secret token; the agent cannot self-approve."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "operator_token": {"type": "string", "description": "The operator's secret token"},
                    "reference": {"type": "string", "description": "UPI ref / note"},
                },
                "required": ["order_id"],
            },
        },
    }),
    "order_delivered": (order_delivered, {
        "type": "function",
        "function": {
            "name": "order_delivered",
            "description": "Mark an order delivered. Refuses unless the order is verified 'paid'.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    }),
    "payment_qr": (payment_qr, {
        "type": "function",
        "function": {
            "name": "payment_qr",
            "description": "Generate a UPI QR for the operator's UPI ID with the amount pre-filled — send this image to the client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount in ₹"},
                    "note": {"type": "string", "description": "Payment note shown in the UPI app"},
                },
                "required": ["amount"],
            },
        },
    }),
    "payment_verify_screenshot": (payment_verify_screenshot, {
        "type": "function",
        "function": {
            "name": "payment_verify_screenshot",
            "description": (
                "Read a client's payment screenshot (amount, ref, app). Only CLAIMS the "
                "order — screenshots can be edited. Verify via payment_check_sms() or the "
                "operator before delivering anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["image_path"],
            },
        },
    }),
    "payment_check_sms": (payment_check_sms, {
        "type": "function",
        "function": {
            "name": "payment_check_sms",
            "description": (
                "Check the operator's phone SMS inbox for a UPI/bank credit confirmation "
                "matching a pending order — the only automatic way an order becomes 'paid'. "
                "Requires the phone connected over ADB with SMS read permission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "description": "How far back to look (default 120)"},
                    "mark_paid": {"type": "boolean", "description": "Auto-mark matching orders paid (default true)"},
                },
            },
        },
    }),
}
