"""Ernest enforcement gate for Claude Code/Cowork.

The gate is deterministic. It blocks live external mutations, risky filesystem
writes, and obvious shell escapes before Claude can execute them.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

READ_TOOLS = {"Read", "Glob", "Grep"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "Shell"}
GUARDED_FS_TOOLS = READ_TOOLS | WRITE_TOOLS

PATH_ARG_KEYS = ("file_path", "path", "notebook_path", "filename", "file")

_MUTATION_VERB_RE = re.compile(
    r"(?i)(?:^|_)(SEND|REPLY|FORWARD|PUBLISH|POST|CREATE|UPDATE|DELETE|REMOVE|"
    r"ARCHIVE|TRASH|MOVE|MERGE|ADD|SET|PATCH|PUT|INVITE|SCHEDULE|CANCEL|ACCEPT|"
    r"DECLINE|ASSIGN|CLOSE|COMPLETE|MARK|UPSERT|IMPORT|UPLOAD|REPLACE|CLEAR|PAY|"
    r"TRANSFER|SHARE|LABEL|UNLABEL|COMMENT|DUPLICATE)(?:_|$)"
)

_CONNECTOR_HINTS = (
    "gmail", "outlook", "mail", "email", "slack", "teams", "discord",
    "hubspot", "salesforce", "crm", "calendar", "notion", "linear", "asana",
    "jira", "monday", "clickup", "intercom", "sheet", "drive", "box",
    "telegram", "twilio", "stripe",
)

_DRAFT_BLOCK_PATTERNS = [
    re.compile(r"(?i)(outlook|gmail|email|mail|message).*(send|publish|reply|forward)"),
    re.compile(r"(?i)^send_(email|message|mail)$"),
    re.compile(r"(?i)hubspot_(create|update|delete|merge|write)"),
    re.compile(r"(?i)slack_(post|send|publish)"),
]

_DRAFT_SAFE = ("DRAFT",)
_READ_VERB_RE = re.compile(
    r"(?i)(?:^|_)(GET|LIST|SEARCH|FETCH|READ|FIND|QUERY|RETRIEVE|SCROLL|VIEW|"
    r"WATCH|DOWNLOAD|EXPORT|RESOLVE|CHECK|ANALYZE|DISPLAY|HEALTH)(?:_|$)"
)

_SHELL_EXTERNAL_MUTATION_RE = re.compile(
    r"(?i)(slack\.com/api/chat\.postMessage|gmail|hubspot|calendar|stripe|"
    r"sendmail|mailx|curl .*-(X|request) +(POST|PUT|PATCH|DELETE)|"
    r"curl .*--request +(POST|PUT|PATCH|DELETE))"
)

_HYGIENE_JOB_ID = "ernest-hubspot-hygiene"
_HYGIENE_ALLOWED_ACTIONS = {"UPDATE_CONTACT", "UPDATE_CONTACTS", "UPDATE_CONTACT_PROPERTY"}
_HYGIENE_FORBIDDEN_ACTION_RE = re.compile(r"(?i)(CREATE|DELETE|MERGE|ASSOCIATE|IMPORT|BATCH|DEAL)")
_HYGIENE_PROP_KEYS = {
    "properties", "property", "fields", "field", "data", "payload", "contact_properties",
}
_hygiene_policy_cache: Optional[Dict[str, Any]] = None


def parse_mcp_tool(tool_name: str) -> Optional[Dict[str, str]]:
    if not tool_name or not tool_name.startswith("mcp__"):
        return None
    rest = tool_name[len("mcp__"):]
    parts = rest.split("__", 1)
    if len(parts) != 2:
        return {"server": parts[0], "action": ""}
    return {"server": parts[0], "action": parts[1]}


def _is_connector(server: str) -> bool:
    s = (server or "").lower()
    return any(h in s for h in _CONNECTOR_HINTS)


def _action_is_mutation(action: str) -> bool:
    a = (action or "").upper()
    if any(safe in a for safe in _DRAFT_SAFE):
        return False
    if _READ_VERB_RE.search(a) and not _MUTATION_VERB_RE.search(a):
        return False
    return bool(_MUTATION_VERB_RE.search(a))


def glob_to_regex(pattern: str) -> str:
    out: List[str] = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        if pattern[i:i + 3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    return "".join(out)


def glob_match(rel_path: str, pattern: str) -> bool:
    return re.match(glob_to_regex(pattern), rel_path) is not None


def matches_any(rel_path: str, patterns: List[str]) -> bool:
    return any(glob_match(rel_path, pattern) for pattern in patterns)


def _deny_patterns_for_path(rel_path: str, patterns: List[str]) -> List[str]:
    if not rel_path.startswith("/"):
        return patterns
    # Absolute paths are only allowed when explicitly whitelisted (for example
    # the local vault). Keep secret/token/.env guards, but do not treat macOS'
    # /private/var prefix as a project "private/" folder.
    return [pattern for pattern in patterns if "private" not in pattern.lower()]


def _expand(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path))
    if os.path.isabs(expanded):
        return os.path.realpath(expanded).replace(os.sep, "/")
    return expanded


def load_scope(ernest_root: str) -> Optional[Dict[str, List[str]]]:
    path = os.path.join(ernest_root, "ernest.yaml")
    if not os.path.isfile(path):
        return None
    text = open(path, "r", encoding="utf-8").read()
    scope = _scope_from_text(text)
    return {key: [_expand(item) for item in values] for key, values in scope.items()}


_LIST_ITEM_RE = re.compile(r'^\s*-\s*["\']?([^"\'#]+?)["\']?\s*(?:#.*)?$')


def _scope_from_text(text: str) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {"read": [], "write": [], "deny": []}
    in_scope = False
    scope_indent = 0
    section: Optional[str] = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if not in_scope:
            if stripped.startswith("scope:"):
                in_scope = True
                scope_indent = indent
            continue
        if indent <= scope_indent and stripped.endswith(":"):
            break
        key = stripped.rstrip(":")
        if key in ("read", "write", "deny") and stripped.endswith(":"):
            section = key
            continue
        match = _LIST_ITEM_RE.match(raw)
        if match and section:
            result[section].append(match.group(1).strip())
    return result


def to_relative(arg: str, ernest_root: str) -> tuple[Optional[str], bool]:
    if not isinstance(arg, str) or not arg:
        return None, False
    root = os.path.realpath(ernest_root)
    cleaned = _expand(arg.strip())
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    abs_path = os.path.realpath(cleaned if os.path.isabs(cleaned) else os.path.join(root, cleaned))
    inside = abs_path == root or abs_path.startswith(root + os.sep)
    if inside:
        return os.path.relpath(abs_path, root).replace(os.sep, "/"), False
    if ".." in arg:
        return None, True
    return abs_path.replace(os.sep, "/"), False


def _candidate_paths(args: Dict[str, Any]) -> List[str]:
    if not isinstance(args, dict):
        return []
    return [args[key] for key in PATH_ARG_KEYS if isinstance(args.get(key), str) and args.get(key)]


def scope_block(scope: Dict[str, List[str]], tool_name: str, args: Dict[str, Any],
                ernest_root: str) -> Optional[Dict[str, str]]:
    if tool_name not in GUARDED_FS_TOOLS:
        return None
    op = "write" if tool_name in WRITE_TOOLS else "read"
    for arg in _candidate_paths(args):
        rel, escaped = to_relative(arg, ernest_root)
        if escaped:
            return {"error": "scope_path_escape", "path": arg, "scope": op,
                    "reason": "path escapes project root"}
        if rel is None:
            continue
        if matches_any(rel, _deny_patterns_for_path(rel, scope.get("deny", []))):
            return {"error": "ernest_scope_denied", "path": rel, "scope": op,
                    "reason": "matches scope.deny"}
        if not matches_any(rel, scope.get(op, [])):
            return {"error": "ernest_scope_denied", "path": rel, "scope": op,
                    "reason": f"not in scope.{op}"}
    return None


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "yes", "1")


def _block(text: str, key: str) -> str:
    lines = text.splitlines()
    out: List[str] = []
    grab = False
    base = 0
    for raw in lines:
        if not grab:
            if re.match(rf"^\s*{re.escape(key)}\s*:", raw):
                grab = True
                base = len(raw) - len(raw.lstrip())
            continue
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= base and ":" in raw.strip():
            break
        out.append(raw)
    return "\n".join(out)


def _load_hygiene_policy(ernest_root: str) -> Dict[str, Any]:
    global _hygiene_policy_cache
    if _hygiene_policy_cache is not None:
        return _hygiene_policy_cache
    policy: Dict[str, Any] = {
        "job_id": _HYGIENE_JOB_ID,
        "dry_run": True,
        "approved": False,
        "mechanical_fields": {"company", "firstname", "lastname", "jobtitle"},
        "active_run_marker": "logs/hygiene-active-run.json",
    }
    path = os.path.join(ernest_root, "ernest.yaml")
    if os.path.isfile(path):
        text = open(path, "r", encoding="utf-8").read()
        dry = re.search(r"^\s*dry_run\s*:\s*(\S+)", text, re.M)
        approved = re.search(r"^\s*approved\s*:\s*(\S+)", text, re.M)
        marker = re.search(r'^\s*active_run_marker\s*:\s*["\']?([^"\'\n]+?)["\']?\s*$', text, re.M)
        fields = re.findall(r"^\s*-\s*(\w+)\s*$", _block(text, "mechanical_fields"), re.M)
        if dry:
            policy["dry_run"] = _parse_bool(dry.group(1))
        if approved:
            policy["approved"] = _parse_bool(approved.group(1))
        if marker:
            policy["active_run_marker"] = marker.group(1).strip()
        if fields:
            policy["mechanical_fields"] = {field.lower() for field in fields}
    _hygiene_policy_cache = policy
    return policy


def _hygiene_active_run_valid(policy: Dict[str, Any], ernest_root: str) -> bool:
    marker = os.path.join(ernest_root, policy.get("active_run_marker", "logs/hygiene-active-run.json"))
    if not os.path.isfile(marker):
        return False
    try:
        data = json.load(open(marker, "r", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("job_id") != policy.get("job_id") or not data.get("mechanical_only"):
        return False
    try:
        ts = datetime.fromisoformat(data.get("started_at", "").replace("Z", "+00:00"))
        return (time.time() - ts.timestamp()) <= 3600
    except (TypeError, ValueError):
        return False


def _collect_property_names(obj: Any, depth: int = 0) -> Set[str]:
    names: Set[str] = set()
    if depth > 8:
        return names
    if isinstance(obj, dict):
        for key, value in obj.items():
            lower_key = str(key).lower()
            if lower_key in _HYGIENE_PROP_KEYS and isinstance(value, dict):
                names |= {str(prop).lower() for prop in value}
            elif lower_key in ("property", "field", "name") and isinstance(value, str):
                names.add(value.lower())
            else:
                names |= _collect_property_names(value, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            names |= _collect_property_names(item, depth + 1)
    return names


def hygiene_may_auto_apply(tool_name: str, args: Optional[Dict[str, Any]],
                           ernest_root: str) -> bool:
    info = parse_mcp_tool(tool_name)
    if not info or "hubspot" not in info["server"].lower():
        return False
    action = info["action"].upper()
    if _HYGIENE_FORBIDDEN_ACTION_RE.search(action) or action not in _HYGIENE_ALLOWED_ACTIONS:
        return False
    policy = _load_hygiene_policy(ernest_root)
    if policy.get("dry_run", True) or not policy.get("approved", False):
        return False
    if os.environ.get("ERNEST_CRON_JOB", "") != policy.get("job_id"):
        return False
    if not _hygiene_active_run_valid(policy, ernest_root):
        return False
    allowed = policy.get("mechanical_fields") or set()
    if not isinstance(allowed, set):
        allowed = {str(item).lower() for item in allowed}
    props = _collect_property_names(args or {})
    return not props or props.issubset(allowed)


def draft_only_block(tool_name: str, args: Optional[Dict[str, Any]],
                     ernest_root: str) -> Optional[Dict[str, str]]:
    name = tool_name or ""
    info = parse_mcp_tool(name)
    if info:
        if not _is_connector(info["server"]):
            return None
        if hygiene_may_auto_apply(name, args, ernest_root):
            return None
        if _action_is_mutation(info["action"]):
            return {
                "error": "draft_only",
                "tool": name,
                "action": info["action"],
                "reason": f"Live mutation '{info['action']}' on '{info['server']}' blocked until CEO approval.",
            }
        return None
    for pattern in _DRAFT_BLOCK_PATTERNS:
        if pattern.search(name):
            return {"error": "draft_only", "tool": name,
                    "reason": "External publish/send/write blocked until CEO approval."}
    return None


def shell_block(tool_name: str, args: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if tool_name not in SHELL_TOOLS:
        return None
    command = str((args or {}).get("command", ""))
    if _SHELL_EXTERNAL_MUTATION_RE.search(command):
        return {
            "error": "shell_external_mutation",
            "tool": tool_name,
            "reason": "Shell command appears to mutate an external system; use a draft-safe MCP tool instead.",
        }
    return None


def evaluate(tool_name: str, args: Optional[Dict[str, Any]], ernest_root: str,
             scope: Optional[Dict[str, List[str]]] = None) -> Optional[Dict[str, str]]:
    block = draft_only_block(tool_name, args, ernest_root)
    if block is not None:
        return block
    block = shell_block(tool_name, args)
    if block is not None:
        return block
    if scope is None:
        scope = load_scope(ernest_root)
    if scope is None:
        return None
    return scope_block(scope, tool_name, args or {}, ernest_root)
