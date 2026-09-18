"""Wallet toolset — read balances and make capped, fully-logged payments.

Design rules (for everyone's safety):
  - The agent NEVER holds private keys. Actual signing is delegated to a
    command the OPERATOR configures (OMNIUSE_SEND_CMD), e.g. a hardware
    wallet CLI. If unset, payments are only queued for the operator.
  - Hard per-transaction cap (OMNIUSE_WALLET_MAX_TX, default 0.01 ETH).
    Raising it requires the operator's token via wallet_raise_limit().
  - Payments only go out when the wallet balance is at/above the operator's
    autopay threshold (OMNIUSE_AUTOPAY_MIN), and every payment — executed,
    queued, or failed — is written to the memory log.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

from omniuse import config


def _data_path(name: str) -> Path:
    d = Path(config.data_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _rpc(payload: dict) -> dict:
    req = Request(config.rpc_url(), data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _balance(address: str) -> float:
    resp = _rpc({"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
                 "params": [address, "latest"]})
    return int(resp["result"], 16) / 1e18


def _max_tx() -> float:
    p = _data_path("limits.json")
    if p.exists():
        try:
            return float(json.loads(p.read_text()).get("max_tx", config.wallet_max_tx_default()))
        except (ValueError, json.JSONDecodeError):
            pass
    return config.wallet_max_tx_default()


def wallet_status() -> str:
    address = config.wallet_address()
    balance = (f"{_balance(address):.6f} {config.wallet_currency()}" if address
               else "(no OMNIUSE_WALLET_ADDRESS set)")
    return (f"balance: {balance}\n"
            f"per-tx limit: {_max_tx()} {config.wallet_currency()}\n"
            f"autopay threshold: {config.autopay_min() or 'not set'}")


def wallet_balance() -> str:
    address = config.wallet_address()
    if not address:
        return "ERROR: OMNIUSE_WALLET_ADDRESS is not set."
    return f"{_balance(address):.6f} {config.wallet_currency()}"


def wallet_send(to: str, amount, purpose: str) -> str:
    if not (isinstance(to, str) and to.startswith("0x") and len(to) == 42):
        return "ERROR: 'to' must be a 42-character 0x… address."
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "ERROR: amount must be a number."
    if amount <= 0:
        return "ERROR: amount must be positive."
    if not purpose or not purpose.strip():
        return "ERROR: a payment purpose is required (what is this for?)."

    cap = _max_tx()
    if amount > cap:
        return (f"REFUSED: {amount} exceeds the per-transaction limit of {cap} "
                f"{config.wallet_currency()}. Only the operator can raise it "
                f"(wallet_raise_limit with the operator token).")

    address = config.wallet_address()
    minimum = config.autopay_min()
    if address and minimum:
        balance = _balance(address)
        if balance < minimum:
            return (f"REFUSED: balance {balance:.6f} is below the autopay "
                    f"threshold {minimum} — payment deferred, not sent.")

    entry = {"to": to, "amount": amount, "currency": config.wallet_currency(),
             "purpose": purpose, "ts": time.time()}
    cmd = config.send_cmd()
    if cmd:
        result = subprocess.run([cmd, to, str(amount), purpose],
                                 capture_output=True, text=True, timeout=180)
        entry["status"] = "executed" if result.returncode == 0 else "failed"
        entry["output"] = (result.stdout + result.stderr)[:1000]
    else:
        entry["status"] = "queued"

    queue = _data_path("payment_queue.json")
    history = json.loads(queue.read_text()) if queue.exists() else []
    history.append(entry)
    queue.write_text(json.dumps(history, indent=2))

    from omniuse.tools import memory
    memory.log_event("payment", **entry)

    if entry["status"] == "executed":
        return f"Payment sent: {amount} {config.wallet_currency()} → {to} ({purpose})"
    if entry["status"] == "queued":
        return (f"Payment QUEUED for the operator (no OMNIUSE_SEND_CMD configured): "
                f"{amount} → {to} ({purpose})")
    return f"Payment command FAILED: {entry['output']}"


def wallet_raise_limit(new_limit, operator_token: str) -> str:
    token = config.operator_token()
    if not token or operator_token != token:
        return "REFUSED: invalid or missing operator token. Only the operator can raise the limit."
    try:
        new_limit = float(new_limit)
    except (TypeError, ValueError):
        return "ERROR: new_limit must be a number."
    if new_limit <= 0:
        return "ERROR: new_limit must be positive."
    old = _max_tx()
    _data_path("limits.json").write_text(json.dumps({"max_tx": new_limit}, indent=2))
    from omniuse.tools import memory
    memory.log_event("limit_change", old=old, new=new_limit, by="operator")
    return f"Per-transaction limit raised to {new_limit} {config.wallet_currency()} (operator-approved)."


TOOLS = {
    "wallet_status": (wallet_status, {
        "type": "function",
        "function": {
            "name": "wallet_status",
            "description": "Show wallet balance, the per-transaction spending limit, and the autopay threshold.",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "wallet_balance": (wallet_balance, {
        "type": "function",
        "function": {
            "name": "wallet_balance",
            "description": "Check the configured wallet's on-chain balance (read-only).",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "wallet_send": (wallet_send, {
        "type": "function",
        "function": {
            "name": "wallet_send",
            "description": (
                "Send a payment (e.g. pay a VPS bill). Refuses anything above the "
                "per-transaction limit, requires a stated purpose, and logs everything. "
                "Only pay for legitimate, documented purposes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient 0x… address"},
                    "amount": {"type": "number", "description": "Amount in the wallet currency"},
                    "purpose": {"type": "string", "description": "Human-readable reason for this payment"},
                },
                "required": ["to", "amount", "purpose"],
            },
        },
    }),
    "wallet_raise_limit": (wallet_raise_limit, {
        "type": "function",
        "function": {
            "name": "wallet_raise_limit",
            "description": (
                "Raise the per-transaction spending limit. Requires the operator's "
                "secret token — the agent must never hold or guess it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "new_limit": {"type": "number"},
                    "operator_token": {"type": "string", "description": "The operator's secret token"},
                },
                "required": ["new_limit", "operator_token"],
            },
        },
    }),
}
