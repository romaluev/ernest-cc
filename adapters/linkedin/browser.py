"""Browser access for the LinkedIn ingest rungs — ego-browser or plain Chrome.

Two drivers behind one interface so the ladder in `ingest.py` never has to care
which one is present:

  EgoDriver     shells out to `ego-browser nodejs`. Reuses the user's login
                state in an isolated agent task space.
  ChromeDriver  attaches to any Chrome/Chromium already listening on a DevTools
                port and drives it over CDP. This is the path that matters when
                the CEO just uses normal Chrome.

RUNS OUTSIDE THE ERNEST GATE, deliberately. `ernest/gate.py:_SHELL_NET_RE`
blocks any shell command containing an https URL, so a browser heredoc cannot
run from inside a gated session — and it should not. This module is invoked by
cron/launchd or by hand; the engine only ever reads the files it writes.

Stdlib only, matching the rest of the engine — no pip, no npm, no vendor SDK.
The WebSocket client below is hand-rolled for exactly that reason: localhost,
no TLS, no extensions, no continuation frames beyond what CDP actually sends.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CDP_PORT = 9222
_TIMEOUT = 30.0

# Anything Chromium-based speaks CDP, so all of these work. Safari and Firefox
# do NOT — Firefox has its own protocol and Safari has no equivalent at all.
# Rather than fail with "no browser", we say which ones would work.
_CHROMIUM_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Arc.app/Contents/MacOS/Arc",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "microsoft-edge", "brave-browser",
)
UNSUPPORTED_BROWSERS = ("Safari", "Firefox")


class BrowserUnavailable(RuntimeError):
    """No driver could be reached. Callers must fall to the next rung, not guess."""


# --------------------------------------------------------------------------- #
# Minimal CDP-over-WebSocket client
# --------------------------------------------------------------------------- #

class _WS:
    """Just enough RFC 6455 to talk to a local DevTools endpoint."""

    def __init__(self, url: str, timeout: float = _TIMEOUT) -> None:
        if not url.startswith("ws://"):
            raise BrowserUnavailable(f"Only local ws:// endpoints are supported, got {url!r}")
        rest = url[len("ws://"):]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise BrowserUnavailable("DevTools closed the connection during handshake")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise BrowserUnavailable(f"DevTools refused the upgrade: {buf.split(chr(13).encode())[0]!r}")
        self._tail = buf.split(b"\r\n\r\n", 1)[1]

    def _recv(self, n: int) -> bytes:
        while len(self._tail) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BrowserUnavailable("DevTools connection closed mid-frame")
            self._tail += chunk
        out, self._tail = self._tail[:n], self._tail[n:]
        return out

    def send(self, payload: str) -> None:
        data = payload.encode()
        header = bytearray([0x81])          # FIN + text
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 1 << 16:
            header.append(0x80 | 126); header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127); header += struct.pack(">Q", n)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self) -> str:
        while True:
            b0, b1 = self._recv(2)
            opcode, length = b0 & 0x0F, b1 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv(8))[0]
            payload = self._recv(length)
            if b1 & 0x80:  # server frames are never masked, but be tolerant
                payload = bytes(p ^ payload[i % 4] for i, p in enumerate(payload))
            if opcode == 0x8:
                raise BrowserUnavailable("DevTools sent a close frame")
            if opcode in (0x1, 0x2):
                return payload.decode("utf-8", "replace")
            # ping/pong/continuation: keep reading

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@dataclass
class Driver:
    kind: str  # "ego" | "chrome"

    def goto(self, url: str) -> None: raise NotImplementedError
    def evaluate(self, expression: str) -> Any: raise NotImplementedError
    def close(self) -> None: pass


class ChromeDriver(Driver):
    """Attach to a Chrome already running with --remote-debugging-port."""

    def __init__(self, port: int = DEFAULT_CDP_PORT) -> None:
        super().__init__(kind="chrome")
        self.port, self._id = port, 0
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
                targets = json.loads(r.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise BrowserUnavailable(
                f"No Chrome DevTools endpoint on 127.0.0.1:{port}. Start Chrome with "
                f"--remote-debugging-port={port} using the CEO's real profile, or install "
                "ego-browser."
            ) from exc
        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise BrowserUnavailable("Chrome is listening but has no attachable page tab open.")
        # Prefer a tab already on LinkedIn — it is the one carrying the session.
        pages.sort(key=lambda t: ("linkedin.com" not in (t.get("url") or ""), t.get("url") or ""))
        self.ws = _WS(pages[0]["webSocketDebuggerUrl"])

    def _call(self, method: str, **params: Any) -> Dict[str, Any]:
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise BrowserUnavailable(f"CDP {method} failed: {msg['error']}")
                return msg.get("result", {})

    def goto(self, url: str) -> None:
        self._call("Page.enable")
        self._call("Page.navigate", url=url)

    def evaluate(self, expression: str) -> Any:
        res = self._call("Runtime.evaluate", expression=expression,
                         returnByValue=True, awaitPromise=True)
        if res.get("exceptionDetails"):
            raise BrowserUnavailable(f"Page JS threw: {res['exceptionDetails'].get('text')}")
        return (res.get("result") or {}).get("value")

    def close(self) -> None:
        self.ws.close()


class EgoDriver(Driver):
    """Drive ego-browser via its nodejs heredoc runtime."""

    def __init__(self, task: str = "linkedin inbound triage") -> None:
        super().__init__(kind="ego")
        if not shutil.which("ego-browser"):
            raise BrowserUnavailable("ego-browser is not on PATH.")
        self.task = task

    def _run(self, body: str) -> str:
        script = (f"const task = await useOrCreateTaskSpace({json.dumps(self.task)});\n{body}\n")
        proc = subprocess.run(["ego-browser", "nodejs"], input=script, text=True,
                              capture_output=True, timeout=180)
        if proc.returncode != 0:
            raise BrowserUnavailable(f"ego-browser failed: {proc.stderr.strip()[:400]}")
        return proc.stdout

    def goto(self, url: str) -> None:
        self._run(f"await openOrReuseTab({json.dumps(url)}, {{ wait: true, timeout: 30 }});")

    def evaluate(self, expression: str) -> Any:
        out = self._run(f"cliLog(JSON.stringify(await js({json.dumps(expression)})));")
        for line in reversed(out.strip().splitlines()):
            try:
                return json.loads(line.strip())
            except ValueError:
                continue
        return None


def find_chromium() -> Optional[str]:
    """A Chromium-family browser we could start ourselves."""
    for candidate in _CHROMIUM_CANDIDATES:
        if candidate.startswith("/"):
            if Path(candidate).exists():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def launch_chromium(port: int = DEFAULT_CDP_PORT, *, wait: float = 12.0) -> bool:
    """Start a Chromium-family browser with debugging on, and wait for it.

    Uses a DEDICATED profile directory, never the user's default. Chrome refuses
    to enable remote debugging on an already-running default profile, and
    silently attaching to someone's main browser is not a thing to do quietly.
    The trade-off is stated plainly: a fresh profile is not signed in to
    LinkedIn, so the user signs in once and it persists.
    """
    exe = find_chromium()
    if not exe:
        return False
    profile = Path.home() / ".ernest-cc" / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(
            [exe, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
             "--no-first-run", "--no-default-browser-check",
             "https://www.linkedin.com/feed/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def available_drivers(port: int = DEFAULT_CDP_PORT) -> List[str]:
    """Which rungs are reachable right now. Used by `ernest doctor`."""
    found: List[str] = []
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
            found.append("chrome")
    except (urllib.error.URLError, OSError):
        pass
    if shutil.which("ego-browser"):
        found.append("ego")
    return found


def open_driver(prefer: str = "auto", port: int = DEFAULT_CDP_PORT) -> Driver:
    """Best available driver. Raises BrowserUnavailable so callers fall a rung."""
    # Chrome FIRST. It is already on the machine and needs no third-party tool,
    # which is the standing constraint here — we adopt other tools' patterns, we
    # do not depend on them. ego-browser is an optional accelerator, used only
    # when it happens to be installed and Chrome is not listening.
    order = {"auto": ("chrome", "ego"), "ego": ("ego",), "chrome": ("chrome",)}[prefer]
    errors = []
    for kind in order:
        try:
            return EgoDriver() if kind == "ego" else ChromeDriver(port)
        except BrowserUnavailable as exc:
            errors.append(f"{kind}: {exc}")
    raise BrowserUnavailable(" | ".join(errors))
