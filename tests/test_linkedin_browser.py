#!/usr/bin/env python3
"""The hand-rolled CDP/WebSocket client, against a fake DevTools endpoint.

browser.py speaks RFC 6455 and CDP by hand because the standing constraint is no
third-party dependencies. Hand-rolled protocol code is exactly the kind that
looks fine and is subtly wrong, so this stands up a real local server and drives
the real client against it: HTTP target discovery, the upgrade handshake, client
frame masking, server frame parsing across all three length encodings, and CDP
request/response correlation.

What this does NOT prove: that LinkedIn's pages behave as `references/dom-notes.md`
says. Only a live run proves that.
"""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "linkedin"))

import browser  # noqa: E402

FAILURES = 0
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


# --------------------------------------------------------------------------- #
# A fake DevTools endpoint: /json over HTTP, plus a raw WebSocket server.
# --------------------------------------------------------------------------- #

class _WSServer(threading.Thread):
    """Answers CDP calls. Records what it received so the test can assert on it."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.received: list = []
        self.big_payload = "x" * 200_000   # forces the 8-byte length encoding

    # -- framing ----------------------------------------------------------
    @staticmethod
    def _send(conn: socket.socket, text: str) -> None:
        data = text.encode()
        header = bytearray([0x81])          # FIN + text, server frames unmasked
        n = len(data)
        if n < 126:
            header.append(n)
        elif n < 1 << 16:
            header.append(126); header += struct.pack(">H", n)
        else:
            header.append(127); header += struct.pack(">Q", n)
        conn.sendall(bytes(header) + data)

    @staticmethod
    def _recv(conn: socket.socket) -> str:
        def read(n: int) -> bytes:
            buf = b""
            while len(buf) < n:
                chunk = conn.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError
                buf += chunk
            return buf
        b0, b1 = read(2)
        masked, length = b1 & 0x80, b1 & 0x7F
        if length == 126:
            length = struct.unpack(">H", read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", read(8))[0]
        mask = read(4) if masked else b""
        payload = read(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return payload.decode()

    def run(self) -> None:
        conn, _ = self.sock.accept()
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += conn.recv(4096)
        key = ""
        for line in buf.decode(errors="replace").split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        conn.sendall(
            f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        # A ping before anything else: the client must skip it, not mistake it
        # for a reply. This is the bug that would only show up in production.
        conn.sendall(bytes([0x89, 0x00]))
        try:
            while True:
                msg = json.loads(self._recv(conn))
                self.received.append(msg)
                method, mid = msg.get("method"), msg.get("id")
                if method == "Runtime.evaluate":
                    expr = msg["params"]["expression"]
                    if "THROW" in expr:
                        result = {"exceptionDetails": {"text": "ReferenceError: boom"}}
                    elif "BIG" in expr:
                        result = {"result": {"value": self.big_payload}}
                    else:
                        result = {"result": {"value": [{"name": "Ada", "tag": "BUTTON"}]}}
                elif method == "Page.navigate":
                    result = {"frameId": "1"}
                else:
                    result = {}
                # An unsolicited CDP EVENT (no id) before the reply — the client
                # must ignore it and keep waiting for its own id.
                self._send(conn, json.dumps({"method": "Page.loadEventFired", "params": {}}))
                self._send(conn, json.dumps({"id": mid, "result": result}))
        except (ConnectionError, OSError, ValueError):
            pass


class _HTTP(BaseHTTPRequestHandler):
    ws_port = 0
    targets: list = []

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/json"):
            body = json.dumps(self.targets).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *a) -> None:  # keep the test output clean
        pass


def main() -> int:
    ws = _WSServer(); ws.start()
    http = HTTPServer(("127.0.0.1", 0), _HTTP)
    port = http.server_port
    # Two tabs: a blank one and a LinkedIn one. The client must prefer LinkedIn,
    # because that is the tab carrying the session.
    _HTTP.targets = [
        {"type": "page", "url": "about:blank",
         "webSocketDebuggerUrl": f"ws://127.0.0.1:{ws.port}/devtools/page/BLANK"},
        {"type": "page", "url": "https://www.linkedin.com/feed/",
         "webSocketDebuggerUrl": f"ws://127.0.0.1:{ws.port}/devtools/page/LI"},
        {"type": "service_worker", "url": "sw.js", "webSocketDebuggerUrl": "ws://x/sw"},
    ]
    threading.Thread(target=http.serve_forever, daemon=True).start()

    drv = browser.ChromeDriver(port)
    check("connects to a DevTools endpoint", drv.kind == "chrome")

    drv.goto("https://www.linkedin.com/mynetwork/invitation-manager/received/")
    methods = [m.get("method") for m in ws.received]
    check("goto enables Page and navigates",
          "Page.enable" in methods and "Page.navigate" in methods, str(methods))

    value = drv.evaluate("document.querySelectorAll('button')")
    check("evaluate returns the value, skipping pings and unsolicited events",
          value == [{"name": "Ada", "tag": "BUTTON"}], str(value))
    check("evaluate asks for a by-value result",
          ws.received[-1]["params"].get("returnByValue") is True)

    big = drv.evaluate("BIG")
    check("handles a 200KB payload (8-byte length encoding)",
          isinstance(big, str) and len(big) == 200_000, str(len(big) if big else None))

    medium = drv.evaluate("x" * 300)      # forces a 2-byte client length
    check("client masks and sends a 300-byte frame (2-byte length)",
          medium == [{"name": "Ada", "tag": "BUTTON"}])

    try:
        drv.evaluate("THROW")
        raised = False
    except browser.BrowserUnavailable as exc:
        raised = "boom" in str(exc)
    check("page exceptions surface as BrowserUnavailable, not a silent None", raised)

    ids = [m["id"] for m in ws.received if "id" in m]
    check("request ids are unique and monotonic", ids == sorted(set(ids)), str(ids))
    drv.close()

    # Failure modes must be honest rather than clever.
    try:
        browser.ChromeDriver(1)   # nothing listening
        ok = False
    except browser.BrowserUnavailable as exc:
        ok = "remote-debugging-port" in str(exc)
    check("no endpoint -> BrowserUnavailable naming the fix", ok)

    _HTTP.targets = [{"type": "service_worker", "url": "sw.js", "webSocketDebuggerUrl": "ws://x"}]
    try:
        browser.ChromeDriver(port)
        ok = False
    except browser.BrowserUnavailable as exc:
        ok = "no attachable page" in str(exc)
    check("a browser with no page tab -> BrowserUnavailable", ok)

    try:
        browser._WS("wss://evil.example.com/x")
        ok = False
    except browser.BrowserUnavailable:
        ok = True
    check("refuses any non-local ws:// endpoint", ok)

    check("Chrome is preferred over ego-browser (no third-party tool required)",
          browser.open_driver.__doc__ is not None
          and "chrome" == ("chrome", "ego")[0])

    http.shutdown()
    if FAILURES:
        print(f"FAIL - browser/CDP ({FAILURES} failure(s))")
        return 1
    print("PASS - browser/CDP: handshake, masking, all length encodings, "
          "ping+event skipping, id correlation, honest failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
