"""Cloud rung — PhantomBuster, when an API key is configured.

WHY THIS EXISTS
---------------
Every other rung runs on the user's own machine, from the user's own IP, in the
user's own signed-in browser. That is fine for a few hundred page loads and it
is exactly what LinkedIn's anti-automation looks for at a few thousand. The
whole invitation queue still comes from the data export, which is one download
and zero page loads — nothing beats it for the 6,000-invitation case. What this
rung adds is the two things the export cannot do:

  * DM threads including archived / unread / InMail / spam folders, which the
    export flattens and partly omits;
  * accepting invitations at a paced rate from someone else's infrastructure
    rather than from the CEO's laptop.

OPTIONAL, ALWAYS
----------------
No API key configured means `available()` is False and the ladder never calls
here. Nothing about this file is required for the tool to work — it is a rung,
not a dependency, and the rest of the bundle has no import of it at module
scope.

THE SESSION COOKIE
------------------
Every LinkedIn automation guide opens with "paste your li_at cookie", and that
is the step people get wrong or refuse. We do not ask: `browser.session_cookie`
reads it out of the browser the user already signed in to, and it is cached
0600 in the profile directory. It is a credential — treat it like one.

Stdlib only. urllib, not requests.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

API = "https://api.phantombuster.com/api/v2"

# Phantom ids are per-account: the user duplicates an automation from the store
# and gets their own id. These are the STORE ids, which work as a default for a
# fresh account and are overridden by phantombuster.json when the user has their
# own. A wrong id fails loudly with a 404 rather than doing something surprising.
DEFAULT_AGENTS = {
    "inbox_scraper": "532696507966746",       # LinkedIn Inbox Scraper
    "invitation_accepter": "",                # set per account; no safe default
}

# PhantomBuster's own documented ceiling for the accepter. Not ours to raise.
ACCEPT_PER_LAUNCH = 50


class CloudUnavailable(RuntimeError):
    """No key, no agent, or the API said no. Callers fall to the next rung."""


def _cfg_path(profile: Path) -> Path:
    return profile / "phantombuster.json"


def config(profile: Path) -> Dict[str, Any]:
    """Key and agent ids, from the environment or the profile. Env wins."""
    cfg: Dict[str, Any] = {"api_key": "", "agents": dict(DEFAULT_AGENTS), "org": ""}
    path = _cfg_path(profile)
    if path.is_file():
        try:
            got = json.loads(path.read_text(encoding="utf-8"))
            cfg["api_key"] = str(got.get("api_key") or "")
            cfg["org"] = str(got.get("org") or "")
            cfg["agents"].update({k: str(v) for k, v in (got.get("agents") or {}).items()})
        except (OSError, ValueError):
            pass
    cfg["api_key"] = os.environ.get("PHANTOMBUSTER_API_KEY", "").strip() or cfg["api_key"]
    return cfg


def available(profile: Path) -> bool:
    return bool(config(profile).get("api_key"))


def _call(cfg: Dict[str, Any], method: str, path: str,
          body: Optional[Dict[str, Any]] = None,
          query: str = "", timeout: float = 60.0) -> Dict[str, Any]:
    url = f"{API}{path}" + (f"?{query}" if query else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Phantombuster-Key", cfg["api_key"])
    req.add_header("Content-Type", "application/json")
    if cfg.get("org"):
        req.add_header("X-Phantombuster-Org", cfg["org"])
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            raw = fh.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise CloudUnavailable(f"{method} {path} -> HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, OSError) as exc:
        raise CloudUnavailable(f"{method} {path} -> {exc}") from None
    try:
        got = json.loads(raw)
    except ValueError:
        raise CloudUnavailable(f"{method} {path} returned non-JSON: {raw[:200]}") from None
    # v2 wraps everything in {status, data}; some endpoints answer flat. Accept
    # both rather than break the moment one of them changes shape.
    return got.get("data") if isinstance(got.get("data"), dict) else got


def launch(cfg: Dict[str, Any], agent_id: str, arguments: Dict[str, Any]) -> str:
    if not agent_id:
        raise CloudUnavailable("no agent id configured for this task")
    got = _call(cfg, "POST", "/agents/launch",
                {"id": agent_id, "arguments": arguments, "manualLaunch": True})
    container = str(got.get("containerId") or got.get("id") or "")
    if not container:
        raise CloudUnavailable(f"launch returned no container id: {str(got)[:200]}")
    return container


def wait_for(cfg: Dict[str, Any], container: str, *, minutes: float = 12.0,
             every: float = 15.0) -> List[Dict[str, Any]]:
    """Poll until the container finishes, then return its result rows.

    A phantom that is still running is not an error and must not be treated as
    one — the caller would fall a rung and lose the work already paid for.
    """
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        got = _call(cfg, "GET", "/containers/fetch-output", query=f"id={container}")
        status = str(got.get("status") or "")
        if status in ("finished", "success", "error"):
            break
        time.sleep(every)
    else:
        raise CloudUnavailable(f"container {container} still running after {minutes:.0f}m")

    got = _call(cfg, "GET", "/containers/fetch-result-object", query=f"id={container}")
    result = got.get("resultObject")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            raise CloudUnavailable("result object was not JSON") from None
    if isinstance(result, dict):
        result = result.get("data") or result.get("results") or []
    return list(result or [])


# --------------------------------------------------------------------------- #
# The two tasks worth doing here
# --------------------------------------------------------------------------- #

def scrape_inbox(profile: Path, session_cookie: str, *,
                 folders: Optional[List[str]] = None,
                 limit: int = 500) -> List[Dict[str, Any]]:
    """Message threads, including the folders the data export does not carry."""
    cfg = config(profile)
    if not cfg["api_key"]:
        raise CloudUnavailable("no PhantomBuster API key configured")
    if not session_cookie:
        raise CloudUnavailable("no LinkedIn session cookie to hand over")
    args = {
        "sessionCookie": session_cookie,
        "numberOfThreadsToScrape": int(limit),
        # Archived and spam are where dropped requests hide, which is the whole
        # reason for asking a third party instead of reading the export.
        "inboxFilter": folders or ["inbox", "unread", "archived", "inmail", "spam"],
    }
    return wait_for(cfg, launch(cfg, cfg["agents"].get("inbox_scraper", ""), args))


def accept_invitations(profile: Path, session_cookie: str, *,
                       count: int, only_with_note: bool = False) -> List[Dict[str, Any]]:
    """Accept up to PhantomBuster's own per-launch ceiling. Never more.

    This MUTATES the account. It is only ever called from the act layer, after
    an explicit approval, and the caller is responsible for the daily cap on top
    of this per-launch one.
    """
    if count > ACCEPT_PER_LAUNCH:
        raise CloudUnavailable(
            f"refusing to accept {count} in one launch — the documented ceiling is "
            f"{ACCEPT_PER_LAUNCH}, and bulk invitation activity is what gets accounts "
            "restricted. Run it again tomorrow instead.")
    cfg = config(profile)
    if not cfg["api_key"]:
        raise CloudUnavailable("no PhantomBuster API key configured")
    args = {"sessionCookie": session_cookie,
            "numberOfInvitationsToAccept": int(count),
            "onlyAcceptInvitationsWithNote": bool(only_with_note)}
    return wait_for(cfg, launch(cfg, cfg["agents"].get("invitation_accepter", ""), args))


# --------------------------------------------------------------------------- #
# The session cookie, cached so it is asked for exactly never
# --------------------------------------------------------------------------- #

def cached_cookie(profile: Path) -> str:
    path = profile / ".li-session.json"
    if not path.is_file():
        return ""
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    # LinkedIn sessions last around a year, but a stale one fails in a way that
    # looks like a scraping error rather than an auth error. Expire it ourselves.
    if time.time() - float(got.get("at") or 0) > 60 * 60 * 24 * 25:
        return ""
    return str(got.get("li_at") or "")


def cache_cookie(profile: Path, value: str) -> None:
    if not value:
        return
    path = profile / ".li-session.json"
    path.write_text(json.dumps({"li_at": value, "at": time.time()}), encoding="utf-8")
    try:
        path.chmod(0o600)      # it is a credential, not a config file
    except OSError:
        pass
