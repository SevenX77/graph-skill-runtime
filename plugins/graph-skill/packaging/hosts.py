"""Pure projections and ownership-aware merging for two desktop host profiles."""

from __future__ import annotations

import base64
import copy
import json
import os
import shlex
import tomllib
from pathlib import Path

from ownership import InstallError, digest, json_bytes, read_bytes

SERVER = "graph-skill-canvas"
MARKER = "graph-skill-toolkit:canvas"
PLUGIN_DIRS = "CLAUDE_CODE_PLUGIN_DIRS"
CLAUDE_MOD_FILES = (
    "claude-mod/.claude-plugin/plugin.json",
    "claude-mod/hooks/hooks.json",
    "claude-mod/hooks/register.js",
)


def quoted_command(parts: list[str]) -> str:
    # Skill text names the shell convention explicitly; PowerShell needs '&'.
    if os.name == "nt":
        return " ".join('"' + p.replace("\\", "/") + '"' for p in parts)
    return shlex.join(parts)


def hook_group(node: Path, script: Path, target: str) -> dict:
    if target == "claude":
        handler = {"type": "command", "command": str(node), "args": [str(script)], "timeout": 10}
    elif os.name == "nt":
        expression = "& " + " ".join("'" + str(p).replace("'", "''") + "'" for p in (node, script))
        encoded = base64.b64encode(expression.encode("utf-16-le")).decode("ascii")
        handler = {
            "type": "command",
            "command": "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded,
            "timeout": 10,
        }
    else:
        handler = {"type": "command", "command": shlex.join([str(node), str(script)]), "timeout": 10}
    return {"matcher": ".*", "hooks": [handler]}


def projections(
    home: Path, payload: Path, python: Path, node: Path, targets: list[str], source_root: Path
) -> list[dict]:
    result = []
    for target in targets:
        if target == "codex":
            skills = home / ".agents" / "skills"
            config = home / ".codex" / "config.toml"
            block = (
                f'# >>> {MARKER} >>>\n[mcp_servers."{SERVER}"]\n'
                f"command = {json.dumps(str(node))}\n"
                f"args = [{json.dumps(str(payload / 'dist/server.mjs'))}]\n"
                'env = { NODE_OPTIONS = "", NODE_PATH = "" }\n'
                f"# <<< {MARKER} <<<\n"
            )
            result.append({"kind": "toml", "path": str(config), "value": block, "target": target})
            hook_file = home / ".codex" / "hooks.json"
        else:
            skills = home / ".claude" / "skills"
            result.append(
                {
                    "kind": "mcp",
                    "path": str(home / ".claude.json"),
                    "value": {
                        "command": str(node),
                        "args": [str(payload / "dist/server.mjs")],
                        "env": {"NODE_OPTIONS": "", "NODE_PATH": ""},
                    },
                    "target": target,
                }
            )
            hook_file = home / ".claude" / "settings.json"
            for member in CLAUDE_MOD_FILES:
                if not (source_root / member).is_file():
                    raise InstallError(f"Missing Claude Mod asset: {member}")
        result.append(
            {
                "kind": "hook",
                "path": str(hook_file),
                "value": hook_group(node, payload / "dist/after-tool.mjs", target),
                "target": target,
                **({"plugin_directory": str(payload / "claude-mod")} if target == "claude" else {}),
            }
        )
        replacements = {
            "{{GSKILL_COMMAND}}": quoted_command([str(python), "-I", "-B", "-X", "utf8", "-m", "graph_skill_runtime"]),
            "{{TOOLKIT_COMMAND}}": quoted_command([str(node), str(payload / "bin/graph-skill.mjs")]),
            "{{PORTABLE_SPEC}}": str(payload / "references/portable-gskill.md"),
        }
        for skill_id in ("graph-skill", "graph-skill-canvas"):
            skill_source = source_root / "skills" / skill_id
            if not (skill_source / "SKILL.md").is_file():
                raise InstallError(f"Missing packaged Skill: {skill_source}")
            for source in sorted(skill_source.rglob("*.md")):
                text = source.read_text(encoding="utf-8")
                for old, new in replacements.items():
                    text = text.replace(old, new)
                result.append(
                    {
                        "kind": "file",
                        "path": str(skills / skill_id / source.relative_to(skill_source)),
                        "content": text.encode("utf-8"),
                        "target": target,
                    }
                )
    return result


def object_at(data: dict, key: str, path: Path) -> dict:
    value = data.setdefault(key, {})
    if not isinstance(value, dict):
        raise InstallError(f"{path}: {key} must be an object")
    return value


def block_location(text: str, marker: str) -> tuple[int, int] | None:
    start, end = f"# >>> {marker} >>>", f"# <<< {marker} <<<"
    if start not in text and end not in text:
        return None
    if text.count(start) != 1 or text.count(end) != 1:
        raise InstallError(f"Invalid ownership block: {marker}")
    a, end_start = text.index(start), text.index(end)
    b = end_start + len(end)
    if (
        a >= end_start
        or (a and text[a - 1] != "\n")
        or (end_start and text[end_start - 1] != "\n")
        or (b < len(text) and text[b] not in "\r\n")
    ):
        raise InstallError(f"Invalid ownership block: {marker}")
    if text[b : b + 2] == "\r\n":
        b += 2
    elif text[b : b + 1] == "\n":
        b += 1
    return a, b


def merge(resource: dict, previous: dict | None, remove: bool = False) -> tuple[bytes | None, bytes | None, dict]:
    path = Path(resource["path"])
    raw = read_bytes(path)
    kind = resource["kind"]
    owned = {key: value for key, value in resource.items() if key != "content"}
    if kind == "file":
        check_file(path, raw, previous)
        content = resource.get("content", b"")
        owned["sha256"] = digest(content)
        return raw, (None if remove else content), owned
    text = (raw or b"").decode("utf-8-sig")
    if kind in {"toml", "profile"}:
        return raw, merge_block(text, resource, previous, remove), owned
    try:
        data = json.loads(text) if text else {}
    except ValueError as exc:
        raise InstallError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InstallError(f"Expected JSON object: {path}")
    if kind == "mcp":
        merge_mcp(data, resource, previous, remove)
    elif kind == "hook":
        merge_hook(data, resource, previous, remove)
        merge_plugin_directory(data, resource, previous, remove)
    else:
        raise InstallError(f"Unknown resource kind: {kind}")
    return raw, json_bytes(data), owned


def check_file(path: Path, raw: bytes | None, previous: dict | None) -> None:
    if previous:
        if raw is None or digest(raw) != previous["sha256"]:
            raise InstallError(f"Managed file changed; preserved: {path}")
    elif raw is not None:
        raise InstallError(f"Unmanaged file already exists; preserved: {path}")


def check_codex_config(text: str, path: Path, previous: dict | None, remove: bool) -> None:
    parsed = tomllib.loads(text)
    if not previous and SERVER in parsed.get("mcp_servers", {}):
        raise InstallError(f"Unmanaged MCP server already exists: {path}")
    legacy = parsed.get("plugins", {}).get("graph-skill-canvas@graph-skill-local", {})
    if not remove and legacy.get("enabled") is True:
        raise InstallError(
            "Disable the old graph-skill-canvas@graph-skill-local plugin in Codex before installing the toolkit."
        )


def merge_block(text: str, resource: dict, previous: dict | None, remove: bool) -> bytes:
    path = Path(resource["path"])
    kind = resource["kind"]
    marker = MARKER if kind == "toml" else "graph-skill-toolkit:path"
    loc = block_location(text, marker)
    if previous:
        if loc is None or text[loc[0] : loc[1]] != previous["value"]:
            raise InstallError(f"Managed block changed; preserved: {path}")
    elif loc is not None:
        raise InstallError(f"Unmanaged block already exists; preserved: {path}")
    if kind == "toml":
        check_codex_config(text, path, previous, remove)
    replacement = "" if remove else resource["value"]
    if loc:
        text = text[: loc[0]] + replacement + text[loc[1] :]
    else:
        text += ("\n" if text and not text.endswith("\n") else "") + replacement
    if kind == "toml":
        tomllib.loads(text)
    return text.encode("utf-8")


def merge_mcp(data: dict, resource: dict, previous: dict | None, remove: bool) -> None:
    path = Path(resource["path"])
    entries = object_at(data, "mcpServers", path)
    if previous:
        if entries.get(SERVER) != previous["value"]:
            raise InstallError(f"Managed MCP entry changed; preserved: {path}")
    elif SERVER in entries:
        raise InstallError(f"Unmanaged MCP entry already exists; preserved: {path}")
    if remove:
        entries.pop(SERVER)
    else:
        entries[SERVER] = resource["value"]


def merge_hook(data: dict, resource: dict, previous: dict | None, remove: bool) -> None:
    path = Path(resource["path"])
    hooks = object_at(data, "hooks", path)
    groups = hooks.setdefault("PostToolUse", [])
    if not isinstance(groups, list):
        raise InstallError(f"PostToolUse must be an array: {path}")
    if previous:
        matches = [i for i, item in enumerate(groups) if item == previous["value"]]
        if len(matches) != 1:
            raise InstallError(f"Managed hook changed; preserved: {path}")
        index = matches[0]
        if remove:
            groups.pop(index)
        else:
            groups[index] = resource["value"]
    elif resource["value"] in groups:
        raise InstallError(f"Unmanaged matching hook already exists: {path}")
    else:
        groups.append(copy.deepcopy(resource["value"]))


def merge_plugin_directory(data: dict, resource: dict, previous: dict | None, remove: bool) -> None:
    """Own one path-list entry alongside the hook in the same settings transaction."""
    incoming = resource.get("plugin_directory")
    prior = (previous or {}).get("plugin_directory")
    if incoming is None and prior is None:
        return
    path = Path(resource["path"])
    environment = object_at(data, "env", path)
    value = environment.get(PLUGIN_DIRS, "")
    if not isinstance(value, str):
        raise InstallError(f"{path}: {PLUGIN_DIRS} must be a string")
    parts = value.split(os.pathsep) if value else []

    def equivalent(left: str, right: str) -> bool:
        return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))

    if prior is not None:
        matches = [i for i, item in enumerate(parts) if equivalent(item, prior)]
        if len(matches) != 1 or parts[matches[0]] != prior:
            raise InstallError(f"Managed Claude Mod entry changed; preserved: {path}")
        index = matches[0]
        parts.pop(index)
    else:
        index = len(parts)
    if not remove and incoming is not None:
        if os.pathsep in incoming:
            raise InstallError("Claude Mod installation path contains the plugin-list separator")
        if any(equivalent(item, incoming) for item in parts):
            raise InstallError(f"Unmanaged Claude Mod entry already exists; preserved: {path}")
        parts.insert(index, incoming)
    if parts:
        environment[PLUGIN_DIRS] = os.pathsep.join(parts)
    else:
        environment.pop(PLUGIN_DIRS, None)
    if not environment:
        data.pop("env", None)


def assert_default_profiles(targets: list[str]) -> None:
    profiles = {"codex": ("CODEX_HOME", ".codex"), "claude": ("CLAUDE_CONFIG_DIR", ".claude")}
    for target in targets:
        name, directory = profiles[target]
        value = os.environ.get(name)
        if value and Path(value).expanduser().resolve() != (Path.home() / directory).resolve():
            raise InstallError(
                f"Custom {name} is set. This installer targets default desktop user profiles; "
                "use a session without this override."
            )
