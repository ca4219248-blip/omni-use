"""OmniUse Hub — give a remote AI a body on this machine.

Run this on the device you want to control:

    OMNIUSE_HUB_TOKEN=<secret> python -m omniuse.hub --port 8787

Then from anywhere (another machine, a cloud agent):

    POST http://<device>:8787/run   {"tool": "browser_open", "arguments": {"url": "example.com"}}
    GET  http://<device>:8787/status

Calls are authenticated with the token and go through the same permission
system as local agent runs (deny/confirm still apply).
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from omniuse import __version__, config, permissions
from omniuse.tools import TOOLSETS, run_tool


def make_handler(token: str):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            expected = f"Bearer {token}"
            if not token:
                self._reply(500, {"ok": False, "error": "hub token not configured"})
                return False
            if self.headers.get("Authorization") != expected:
                self._reply(401, {"ok": False, "error": "unauthorized"})
                return False
            return True

        def do_GET(self):  # noqa: N802 — stdlib naming
            if self.path.rstrip("/") == "/status":
                self._reply(200, {"ok": True, "version": __version__,
                                  "toolsets": sorted(TOOLSETS)})
            else:
                self._reply(404, {"ok": False, "error": "not found"})

        def do_POST(self):  # noqa: N802 — stdlib naming
            if not self._authorized():
                return
            if self.path.rstrip("/") != "/run":
                self._reply(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                tool, arguments = payload.get("tool", ""), payload.get("arguments", {})
            except (ValueError, json.JSONDecodeError):
                self._reply(400, {"ok": False, "error": "invalid JSON body"})
                return

            level = permissions.check(tool, arguments)
            if level == "deny":
                self._reply(403, {"ok": False, "error": f"tool '{tool}' is denied by permissions"})
                return
            if level == "confirm" and not permissions.is_approved(tool):
                self._reply(403, {"ok": False,
                                  "error": f"tool '{tool}' needs operator approval "
                                           f"(approve on the hub machine first)"})
                return
            try:
                self._reply(200, {"ok": True, "result": run_tool(tool, arguments or {})})
            except Exception as e:  # noqa: BLE001 — remote callers get the error as data
                self._reply(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})

        def log_message(self, fmt, *args):  # quiet default logging
            print(f"[hub] {self.address_string()} {fmt % args}", flush=True)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(prog="omniuse-hub",
                                     description="Expose this machine's OmniUse tools over HTTP.")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default 127.0.0.1; use 0.0.0.0 for LAN — know what you're doing).")
    args = parser.parse_args()

    token = config.hub_token()
    if not token:
        print("Set OMNIUSE_HUB_TOKEN first — an unauthenticated hub is an open door.")
        return 1
    server = ThreadingHTTPServer((args.host, args.port), make_handler(token))
    print(f"OmniUse Hub v{__version__} listening on http://{args.host}:{args.port} "
          f"({len(TOOLSETS)} toolsets) — Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHub stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
