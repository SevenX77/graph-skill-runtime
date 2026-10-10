"""Explicit user-scoped toolkit lifecycle using packaged private interpreters."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shlex
import shutil
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path

from discovery import discover, select_targets
from hosts import CLAUDE_MOD_FILES, assert_default_profiles, merge, projections
from locking import installer_lock
from ownership import InstallError, Transaction, digest, json_bytes, plain_path, read_bytes, read_json
from runtime_layout import current_target, executable_paths, runtime_node, runtime_python

SCHEMA = "graph-skill.toolkit-install.v1"
MIGRATED = "graph-skill.toolkit-migrated.v1"
ROOT = Path(__file__).resolve().parent.parent


def progress(message: str) -> None:
    print("  " + message, file=sys.stderr, flush=True)


def completion(result: dict, operation: str) -> None:
    if operation == "detect":
        return
    if result["status"] == "installed":
        hosts = ", ".join("Codex" if item == "codex" else "Claude Code" for item in result["targets"])
        print(f"\nGraph Skill {result['version']} is installed for {hosts}.", file=sys.stderr)
        print("Commands, Skills, canvas connection and follow-up hook are configured.", file=sys.stderr)
        launcher = state_root() / "bin" / ("graph-skill.cmd" if os.name == "nt" else "graph-skill")
        immediate = "& '" + str(launcher).replace("'", "''") + "' status" if os.name == "nt" else shlex.quote(str(launcher)) + " status"
        print(f"\nCheck now ({'PowerShell' if os.name == 'nt' else 'shell'}):\n  {immediate}", file=sys.stderr)
        print("Open a new terminal to use graph-skill and gskill by name.", file=sys.stderr)
        print(f"Restart {hosts} to load the Skills and canvas; review any host trust prompt.", file=sys.stderr)
        print('Then ask your agent: "Open a Graph Skill folder and show its graph."', file=sys.stderr)
        print("Desktop loading and rendering still need a check in the restarted host.\n", file=sys.stderr, flush=True)
    elif operation == "cleanup":
        preview = result["status"] == "planned"
        action = "Would remove" if preview else "Removed"
        progress(f"{action} {len(result['inactive_releases'])} inactive cached release(s).")
        for entry in result["preserved"]:
            progress(f"Kept {entry['path']}: {entry['reason']}")
        if preview:
            progress("No changes were applied; remove --dry-run to apply.")
    elif result["status"] == "planned":
        progress(f"{operation.capitalize()} preview: {len(result.get('changes', []))} planned file change(s).")
        progress("No changes were applied; remove --dry-run to apply.")
    elif operation == "status":
        progress(f"Installation check: {result['status']}.")
        if result.get("version"):
            progress(f"Version {result['version']}; hosts: {', '.join(result['targets'])}.")
        for problem in result.get("problems", []):
            progress(problem)
    elif result["status"] == "uninstalled":
        progress("Uninstalled. Restart the selected hosts; cached releases remain available for explicit cleanup.")
    elif result["status"] == "not-installed":
        progress("Graph Skill is not installed; no changes were needed.")


def state_root() -> Path:
    # Windows packaged hosts have a redirected AppData view. Shared executable
    # paths and their authoritative state must be outside that virtualized tree.
    return Path.home() / ".local/share/graph-skill"


def legacy_state_root() -> Path | None:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "GraphSkill"
    return None


def migration_record(state: Path, release: str) -> dict:
    return {"schema": MIGRATED, "home": str(Path.home()), "state_root": str(state), "release": release}


def legacy_installation(state: Path) -> tuple[Path | None, dict]:
    legacy = legacy_state_root()
    if legacy is None or legacy == state:
        return None, {}
    data = read_json(legacy / "install.json")
    if data.get("schema") == MIGRATED:
        release_root(legacy, data.get("release", ""))
        if data != migration_record(state, data["release"]):
            raise InstallError("Legacy migration record changed; preserved")
        return legacy, {}
    return legacy, load_manifest(legacy)


def installation_for_update(state: Path) -> tuple[Path, dict]:
    current = load_manifest(state)
    legacy, previous = legacy_installation(state)
    if current and previous:
        raise InstallError("Two active toolkit installations exist; preserved both for inspection")
    return (legacy, previous) if previous and legacy is not None else (state, current)


@contextmanager
def lifecycle_lock(state: Path):
    # Match the old installer's lock before acquiring the current lock. The
    # migration tombstone subsequently makes old installers fail closed.
    legacy = legacy_state_root()
    with ExitStack() as stack:
        if legacy is not None and legacy != state and legacy.exists():
            stack.enter_context(installer_lock(legacy, progress))
        stack.enter_context(installer_lock(state, progress))
        yield


def release_root(state: Path, identity: str) -> Path:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{16}", identity):
        raise InstallError("Invalid installed release identity")
    path = state / "versions" / identity
    plain_path(path)
    if path.parent.resolve() != (state / "versions").resolve():
        raise InstallError("Release path escaped its owner")
    return path


def verify_inventory(source: Path, info: dict) -> None:
    if not isinstance(info.get("files"), dict) or not info["files"]:
        raise InstallError("Bundle has no file inventory")
    for name, expected in info["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise InstallError(f"Unsafe bundle member: {name}")
        content = read_bytes(source / relative)
        if content is None or digest(content) != expected:
            raise InstallError(f"Bundle file missing or changed: {name}")


def package(source: Path) -> tuple[dict, bytes]:
    raw = read_bytes(source / "bundle.json")
    if raw is None:
        raise InstallError(
            "Use the release archive: bundle.json is missing. The source checkout must be packaged first."
        )
    info = json.loads(raw)
    if (
        not isinstance(info, dict)
        or info.get("schema") != "graph-skill.toolkit-bundle.v2"
        or not re.fullmatch(r"\d+\.\d+\.\d+", info.get("version", ""))
    ):
        raise InstallError("Invalid toolkit bundle metadata")
    if info.get("target") != current_target():
        raise InstallError(f"Bundle target {info.get('target')} does not match {current_target()}")
    if info.get("runtimes", {}).get("executables") != executable_paths(current_target()):
        raise InstallError("Invalid private runtime executable paths")
    verify_inventory(source, info)
    wheel = info.get("runtime_wheel", "")
    if wheel not in info["files"] or not wheel.startswith("runtime/") or not wheel.endswith(".whl"):
        raise InstallError("Bundle must bind its runtime wheel")
    for executable in executable_paths(current_target()).values():
        if executable not in info["files"]:
            raise InstallError(f"Bundle must bind its private executable: {executable}")
    return info, raw


def load_manifest(state: Path) -> dict:
    data = read_json(state / "install.json")
    if data:
        if data.get("schema") != SCHEMA or data.get("home") != str(Path.home()):
            raise InstallError("Installation manifest does not belong to this user or schema")
        release_root(state, data["release"])
        if not set(data["targets"]).issubset({"codex", "claude"}):
            raise InstallError("Unknown manifest target")
        for resource in data["resources"]:
            validate_resource(resource, state)
    return data


def validate_resource(resource: dict, state: Path) -> None:
    home = Path.home()
    path = Path(resource["path"])
    if not path.is_absolute() or ".." in path.parts:
        raise InstallError("Invalid managed resource path")
    exact = {
        home / ".codex/config.toml": "toml",
        home / ".codex/hooks.json": "hook",
        home / ".claude.json": "mcp",
        home / ".claude/settings.json": "hook",
        home / ".profile": "profile",
        home / ".bash_profile": "profile",
        home / ".bash_login": "profile",
        home / ".zprofile": "profile",
        state / "bin/gskill.cmd": "file",
        state / "bin/graph-skill.cmd": "file",
        state / "bin/gskill": "file",
        state / "bin/graph-skill": "file",
    }
    if path in exact and resource["kind"] == exact[path]:
        if "plugin_directory" in resource:
            directory = Path(resource["plugin_directory"])
            if (path != home / ".claude/settings.json" or directory.name != "claude-mod"
                    or directory != release_root(state, directory.parent.name) / "claude-mod"):
                raise InstallError("Manifest references an unowned Claude Mod directory")
        return
    for base in (home / ".agents/skills", home / ".claude/skills"):
        for name in ("graph-skill", "graph-skill-canvas"):
            if resource["kind"] == "file" and path.is_relative_to(base / name) and path.suffix == ".md":
                return
    raise InstallError(f"Manifest references an unowned resource: {path}")


def launchers(state: Path, release: Path, node: Path) -> list[dict]:
    python = runtime_python(release)
    commands = {
        "gskill": [str(python), "-I", "-B", "-X", "utf8", "-m", "graph_skill_runtime"],
        "graph-skill": [str(node), str(release / "bin/graph-skill.mjs")],
    }
    result = []
    for name, argv in commands.items():
        if os.name == "nt":
            # cmd expands percent signs even inside quotes. Reject other expansion controls.
            if any(any(c in part for c in '%!\r\n"') for part in argv):
                raise InstallError("Installed executable paths contain unsupported cmd expansion characters")
            body = (
                '@echo off\r\nsetlocal DisableDelayedExpansion\r\nset "NODE_OPTIONS="\r\nset "NODE_PATH="\r\n'
                + " ".join('"' + part + '"' for part in argv)
                + " %*\r\nexit /b %errorlevel%\r\n"
            )
            filename = name + ".cmd"
        else:
            body = "#!/bin/sh\nunset NODE_OPTIONS NODE_PATH\nexec " + shlex.join(argv) + ' "$@"\n'
            filename = name
        result.append(
            {"kind": "file", "path": str(state / "bin" / filename), "content": body.encode(), "target": "commands"}
        )
    if os.name != "nt":
        block = (
            "# >>> graph-skill-toolkit:path >>>\nexport PATH="
            + shlex.quote(str(state / "bin"))
            + ':"$PATH"\n# <<< graph-skill-toolkit:path <<<\n'
        )
        # Bash loads the first existing login file. Do not create a new file
        # that would mask the user's existing startup configuration.
        bash_profile = next(
            (name for name in (".bash_profile", ".bash_login", ".profile") if (Path.home() / name).exists()), ".profile"
        )
        for name in (bash_profile, ".zprofile"):
            result.append({"kind": "profile", "path": str(Path.home() / name), "value": block, "target": "commands"})
    return result


def windows_path() -> tuple[str, int]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return "", winreg.REG_EXPAND_SZ
    if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(value, str):
        raise InstallError("User PATH has an unsupported registry type")
    return value, kind


def set_windows_path(before: tuple[str, int], after: tuple[str, int]) -> None:
    import winreg

    if windows_path() != before:
        raise InstallError("User PATH changed concurrently; preserved")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Path", 0, after[1], after[0])
    # Ask running shells/app launchers to pick up the new environment.
    try:
        send = ctypes.windll.user32.SendMessageTimeoutW
        send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        send.restype = ctypes.c_ssize_t
        send(0xFFFF, 0x1A, 0, "Environment", 2, 1000, None)
    except (AttributeError, OSError):
        pass


def path_plan(state: Path, previous: dict, remove: bool, previous_state: Path | None = None
              ) -> tuple[tuple[str, int], tuple[str, int], bool] | None:
    if os.name != "nt":
        return None
    before = windows_path()
    value = str((previous_state or state) / "bin")
    parts = before[0].split(";") if before[0] else []

    def same(item: str) -> bool:
        return os.path.normcase(item.rstrip("\\/")) == os.path.normcase(value)

    matches = [i for i, item in enumerate(parts) if same(item)]
    owned = previous.get("path_added", False)
    if previous and owned and len(matches) != 1:
        raise InstallError("Managed PATH entry changed; restore it before update/uninstall")
    if previous_state is not None and previous_state != state:
        if owned:
            parts.pop(matches[0])
        value = str(state / "bin")
        matches = [i for i, item in enumerate(parts) if same(item)]
        owned = False
    if remove:
        if owned:
            parts.pop(matches[0])
    elif not matches:
        parts.insert(0, value)
        owned = True
    return before, (";".join(parts), before[1]), owned


def plan(resources: list[dict], old: dict, state: Path) -> tuple[Transaction, list[dict]]:
    transaction, owned = Transaction(), []
    previous = {entry["path"]: entry for entry in old.get("resources", [])}
    for resource in resources:
        validate_resource(resource, state)
        before, after, record = merge(resource, previous.pop(resource["path"], None))
        transaction.add(Path(resource["path"]), before, after)
        owned.append(record)
    for record in previous.values():
        before, after, _ = merge(record, record, remove=True)
        transaction.add(Path(record["path"]), before, after)
    return transaction, owned


def ready_bytes(raw: bytes) -> bytes:
    return json_bytes({"schema": "graph-skill.toolkit-ready.v1", "bundle_sha256": digest(raw)})


def verify_release(release: Path, raw: bytes) -> None:
    _, installed_raw = package(release)
    if (
        installed_raw != raw
        or not runtime_python(release).is_file()
        or read_bytes(release / "ready.json") != ready_bytes(raw)
    ):
        raise InstallError(f"Incomplete or different release already exists: {release}")


def provision(source: Path, release: Path, info: dict, raw: bytes) -> None:
    if release.exists():
        verify_release(release, raw)
        return
    release.mkdir(parents=True)
    try:
        for name in info["files"]:
            dest = release / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, dest)
            if os.name != "nt" and name.startswith(("runtimes/node/bin/", "runtimes/python/bin/")):
                dest.chmod(0o755)
        (release / "bundle.json").write_bytes(raw)
        package(release)
        (release / "ready.json").write_bytes(ready_bytes(raw))
    except BaseException:
        cleanup_release(release, release.parent.parent)
        raise


def cleanup_release(release: Path, state: Path) -> None:
    checked = release_root(state, release.name)
    if checked != release or not release.exists():
        return
    shutil.rmtree(checked)


def install(source: Path, target_option: str, dry_run: bool, discovery_report: dict | None = None) -> dict:
    state = state_root()
    progress("Checking package integrity...")
    info, raw = package(source)
    previous_state, old = installation_for_update(state)
    discovery_report = discover() if discovery_report is None else discovery_report
    targets = select_targets(target_option, discovery_report, old)
    progress(f"Checking configuration and file ownership for {', '.join(targets)}...")
    assert_default_profiles(targets)
    if old and tuple(map(int, info["version"].split("."))) < tuple(map(int, old["version"].split("."))):
        raise InstallError(f"Incoming toolkit {info['version']} is older than installed {old['version']}; "
                           "use a current bundle. Existing installation preserved.")
    identity = info["version"] + "-" + digest(raw)[:16]
    release = release_root(state, identity)
    node = runtime_node(release)
    if "claude" in targets and any(member not in info["files"] for member in CLAUDE_MOD_FILES):
        raise InstallError("Bundle must bind every Claude Mod asset")
    resources = projections(Path.home(), release, runtime_python(release), node, targets, source)
    resources += launchers(state, release, node)
    transaction, owned = plan(resources, old, state)
    path_change = path_plan(state, old, False, previous_state)
    manifest = {
        "schema": SCHEMA,
        "home": str(Path.home()),
        "version": info["version"],
        "release": identity,
        "targets": targets,
        "node": str(node),
        "python": str(runtime_python(release)),
        "target": info["target"],
        "path_added": path_change[2] if path_change else False,
        "resources": owned,
    }
    transaction.add(state / "install.json", read_bytes(state / "install.json"), json_bytes(manifest))
    if previous_state != state:
        # Keep a closed migration receipt instead of an old active owner. Old
        # installers reject its schema; verified cached bytes remain available.
        transaction.add(previous_state / "install.json", read_bytes(previous_state / "install.json"),
                        json_bytes(migration_record(state, old["release"])))
    report = {
        "status": "planned" if dry_run else "installed",
        "version": info["version"],
        "targets": targets,
        "changes": transaction.summary(),
        "target_selection": "detected" if target_option == "auto" else "explicit",
        "discovery": discovery_report,
        "runtime": str(runtime_python(release)),
        "state_root": str(state),
        "migrated_from": str(previous_state) if previous_state != state else None,
        "restart_desktop": True,
        "native_canvas": "requires user acceptance",
        "hook_trust": "review in host; installer does not grant trust",
    }
    if dry_run:
        return report
    progress("Installing private runtimes and validating the installed files...")
    provision(source, release, info, raw)
    try:
        progress("Configuring commands, Skills, canvas and follow-up hooks...")
        transaction.apply()
        if os.name != "nt":
            for path in (state / "bin/gskill", state / "bin/graph-skill"):
                path.chmod(0o755)
        if path_change and path_change[0] != path_change[1]:
            set_windows_path(path_change[0], path_change[1])
    except BaseException:
        transaction.rollback()
        # Retain the payload: concurrent edits may retain references to it even
        # when a transaction cannot fully roll back. Never delete that target.
        raise
    return report


def uninstall(dry_run: bool) -> dict:
    state = state_root()
    old = load_manifest(state)
    _, previous = legacy_installation(state)
    if previous:
        raise InstallError("Legacy installation requires install/update migration before uninstall")
    if not old:
        return {"status": "not-installed"}
    transaction, _ = plan([], old, state)
    transaction.add(state / "install.json", read_bytes(state / "install.json"), None)
    path_change = path_plan(state, old, True)
    report = {
        "status": "planned" if dry_run else "uninstalled",
        "changes": transaction.summary(),
        "retained_release_cache": str(state / "versions"),
        "restart_desktop": True,
    }
    if dry_run:
        return report
    transaction.apply()
    if path_change and path_change[0] != path_change[1]:
        try:
            set_windows_path(path_change[0], path_change[1])
        except BaseException:
            transaction.rollback()
            raise
    # Immutable release caches stay available for explicit reinstall/rollback.
    # Business assets and user run state are outside this installer's ownership.
    return report


def status() -> dict:
    state = state_root()
    old = load_manifest(state)
    if not old:
        legacy, previous = legacy_installation(state)
        if previous:
            return {"status": "migration-required", "legacy_state_root": str(legacy),
                    "state_root": str(state), "version": previous["version"], "targets": previous["targets"]}
        return {"status": "not-installed", "state_root": str(state)}
    problems = []
    progress("Checking installed configuration and package integrity...")
    for record in old["resources"]:
        try:
            merge(record, record, remove=True)
        except (OSError, ValueError, InstallError) as exc:
            problems.append(str(exc))
    try:
        release = release_root(state, old["release"])
        raw = read_bytes(release / "bundle.json")
        if raw is None:
            raise InstallError("Installed bundle.json is missing")
        verify_release(release, raw)
        path_plan(state, old, False)
    except (OSError, ValueError, InstallError) as exc:
        problems.append(str(exc))
    return {
        "status": "configuration-changed" if problems else "installed-files-present",
        "version": old["version"],
        "targets": old["targets"],
        "problems": problems,
        "native_host_loading": "unverified",
        "state_root": str(state),
    }


def cleanup(dry_run: bool) -> dict:
    state = state_root()
    old = load_manifest(state)
    legacy, previous = legacy_installation(state)
    if previous:
        raise InstallError("Legacy installation requires install/update migration before cleanup")
    roots = [state]
    if legacy is not None and read_json(legacy / "install.json").get("schema") == MIGRATED:
        roots.append(legacy)
    removed, preserved = [], []
    for root in roots:
        result = cleanup_at(root, old if root == state else {}, dry_run)
        removed.extend(result[0])
        preserved.extend(result[1])
    return {"status": "planned" if dry_run else "cleaned", "inactive_releases": removed, "preserved": preserved}


def cleanup_at(state: Path, old: dict, dry_run: bool) -> tuple[list, list]:
    versions = state / "versions"
    plain_path(versions)
    removed, preserved = [], []
    for path in sorted(versions.iterdir()) if versions.exists() else []:
        if path.name == old.get("release") or path == ROOT:
            preserved.append({"path": str(path), "reason": "active release or executing installer"})
            continue
        try:
            checked = release_root(state, path.name)
            info, raw = package(checked)
            if path.name != info["version"] + "-" + digest(raw)[:16]:
                raise InstallError("Release identity does not match its directory")
            verify_release(checked, raw)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, InstallError) as exc:
            preserved.append({"path": str(path), "reason": str(exc)})
            continue
        if not dry_run:
            cleanup_release(checked, state)
        removed.append(str(path))
    return removed, preserved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the Graph Skill toolkit for local Codex and Claude Code Desktop"
    )
    parser.add_argument("operation", choices=("install", "update", "uninstall", "status", "cleanup", "detect"))
    parser.add_argument("source", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--targets", default="auto", help="auto, codex, claude, or codex,claude")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the structured result even in an interactive terminal")
    args = parser.parse_args()
    discovery_report = None
    try:
        if args.operation in {"install", "update", "detect"}:
            discovery_report = discover()
        if args.operation in {"install", "update"}:
            # Reject discovery/profile uncertainty before the lock creates state.
            # Installation rechecks the previous target set while holding the lock.
            _, previous = installation_for_update(state_root())
            targets = select_targets(args.targets, discovery_report, previous)
            assert_default_profiles(targets)
        if args.operation == "detect":
            result = discovery_report
        elif args.operation == "status":
            result = status()
        elif args.dry_run:
            if args.operation == "cleanup":
                result = cleanup(True)
            else:
                result = (
                    uninstall(True) if args.operation == "uninstall"
                    else install(args.source.resolve(), args.targets, True, discovery_report)
                )
        else:
            with lifecycle_lock(state_root()):
                if args.operation == "cleanup":
                    result = cleanup(False)
                else:
                    result = (
                        uninstall(False) if args.operation == "uninstall"
                        else install(args.source.resolve(), args.targets, False, discovery_report)
                    )
        completion(result, args.operation)
        if args.operation == "detect" or args.json or not sys.stdout.isatty():
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, InstallError) as exc:
        result = {"status": "error", "message": str(exc)}
        if discovery_report is not None:
            result["discovery"] = discovery_report
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        print("Installation was not completed. Resolve the reported problem, then retry the same command.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
