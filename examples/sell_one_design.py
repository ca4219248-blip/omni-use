#!/usr/bin/env python3
"""Send-and-watch: make a design, watermark it, wait for the payment SMS.

    python examples/sell_one_design.py

Uses the full 4.0 paid-work pipeline:
design → watermark → order → QR → payment_wait (SMS on the operator phone)
→ delivery. Requires a connected LLM (and an ADB phone for the SMS part).
"""

from omniuse import Agent

TASK = """
Sell one poster design through the paid-work pipeline:
1. design_poster() a festival sale poster (item: 'Festival sale poster', ₹149).
2. design_watermark() it.
3. order_create + order_attach the watermarked preview and the full file.
4. payment_qr(149) and tell me where the QR image is saved so I can send it.
5. If a client says they paid, payment_wait on the order — do NOT deliver
   until it turns 'paid'.
Follow every rule in your system prompt (preview-first, inbound only).
"""

if __name__ == "__main__":
    print(Agent(toolsets=["design", "payments", "shop", "memory"]).run(TASK))
