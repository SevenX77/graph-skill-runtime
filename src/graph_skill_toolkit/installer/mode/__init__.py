"""Switch the owned desktop registration between a workspace and its installed release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import install
from hosts import CLAUDE_MOD_FILES, assert_default_profiles, merge, projections
from locking import installer_lock
from ownership import InstallError, digest, json_bytes, plain_path, read_bytes

SOURCE_SPEC = "01-PORTABLE-GSKILL-V1.md"


BUILD_MEMBERS = (
    "dist/server.mjs",
    "dist/after-tool.mjs",
    "dist/canvas.html",
    "dist/interface-lab.html",
    *("dist/" + member for member in CLAUDE_MOD_FILES),
)
SOURCE_MEMBERS = ("bin/graph-skill.mjs",)


def test_source(path: Path) -> tuple[Path, Path, dict[str, str], str]:
    """Check a built toolkit source without taking ownership of its mutable files."""
    if not path.is_absolute():
        raise InstallError("Test source must be an absolute toolkit directory")
    plain_path(path)
    root = path.resolve(strict=True)
    manifest = root / "package.json"
    plain_path(manifest)
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"Invalid toolkit source package: {manifest}") from exc
    if (
        metadata.get("name") != "graph-skill-toolkit"
        or not isinstance(metadata.get("version"), str)
        or not (root / "scripts/build/main.mjs").is_file()
    ):
        raise InstallError(f"Not a buildable Graph Skill toolkit source: {root}")
    spec = root.parents[1] / "docs/skill-spec" / SOURCE_SPEC
    required = [*(root / member for member in (*BUILD_MEMBERS, *SOURCE_MEMBERS)), spec]
    skill_members = []
    for skill in ("graph-skill", "graph-skill-canvas", "plugin-interface-lab"):
        skill_root = root / "skills" / skill
        required.append(skill_root / "SKILL.md")
        for path in sorted(skill_root.rglob("*.md")):
            required.append(path)
            skill_members.append(path.relative_to(root).as_posix())
    for item in required:
        plain_path(item)
        if not item.is_file():
            raise InstallError(f"Build the test source first; missing: {item}")
    hashes = {
        member: digest((root / member).read_bytes())
        for member in (*BUILD_MEMBERS, *SOURCE_MEMBERS, *skill_members)
    }
    return root, spec, hashes, metadata["version"]


def source_status() -> dict:
    state = install.state_root()
    old = install.load_manifest(state)
    if not old:
        return {"status": "not-installed", "state_root": str(state)}
    release = install.release_root(state, old["release"])
    mode = old.get("source_mode", "installed")
    problems = []
    for record in old["resources"]:
        try:
            merge(record, record, remove=True)
        except (OSError, ValueError, InstallError) as exc:
            problems.append(str(exc))
    root = old.get("test_root") if mode == "test" else None
    source_version = old["version"]
    if mode == "test":
        try:
            _, _, current_hashes, source_version = test_source(Path(root))
            saved = old.get("test_hashes", {})
            if current_hashes != saved:
                for member in sorted(current_hashes.keys() | saved.keys()):
                    if current_hashes.get(member) != saved.get(member):
                        problems.append(f"Test source changed since selection: {member}")
        except (OSError, ValueError, InstallError) as exc:
            problems.append(str(exc))
    return {
        "status": "configured" if not problems else "configuration-changed",
        "mode": mode,
        "test_root": root,
        "installed_root": str(release),
        "installed_version": old["version"],
        "source_version": source_version,
        "targets": old["targets"],
        "problems": problems,
        "loaded_host_processes": "unverified",
    }


def switch(mode: str, source: Path | None, dry_run: bool = False) -> dict:
    if mode not in {"test", "installed"}:
        raise InstallError("Mode must be test or installed")
    state = install.state_root()
    old = install.load_manifest(state)
    if not old:
        raise InstallError("Install the toolkit before switching its source")
    targets = old["targets"]
    assert_default_profiles(targets)
    release = install.release_root(state, old["release"])
    raw = read_bytes(release / "bundle.json")
    if raw is None:
        raise InstallError("Installed release is missing its bundle")
    install.verify_release(release, raw)
    node = install.runtime_node(release)
    python = install.runtime_python(release)
    if mode == "test":
        if source is None:
            raise InstallError("Test mode requires an explicit source directory")
        payload, spec, hashes, source_version = test_source(source)
        mod_root = payload / "dist/claude-mod"
        resources = projections(
            Path.home(), payload, python, node, targets, payload,
            mod_root=mod_root, mod_assets=payload / "dist", portable_spec=spec, interface_lab=True,
        )
    else:
        payload, hashes, mod_root, source_version = release, {}, None, old["version"]
        resources = projections(Path.home(), release, python, node, targets, release)
    if (
        old.get("source_mode", "installed") == mode
        and (mode == "installed" or old.get("test_root") == str(payload))
        and old.get("test_hashes", {}) == hashes
    ):
        for record in old["resources"]:
            merge(record, record, remove=True)
        return {
            "status": "planned" if dry_run else "unchanged",
            "mode": mode,
            "active_path": str(payload),
            "installed_path": str(release),
            "installed_version": old["version"],
            "source_version": source_version,
            "targets": targets,
            "changes": [],
            "reload_required": [],
            "loaded_host_processes": "unverified",
        }
    resources += install.launchers(state, release, node)
    transaction, owned = install.plan(resources, old, state, test_mod=mod_root)
    manifest = dict(old)
    manifest["resources"] = owned
    manifest["source_mode"] = mode
    if mode == "test":
        manifest["test_root"] = str(payload)
        manifest["test_hashes"] = hashes
    else:
        manifest.pop("test_root", None)
        manifest.pop("test_hashes", None)
    transaction.add(state / "install.json", read_bytes(state / "install.json"), json_bytes(manifest))
    result = {
        "status": "planned" if dry_run else "switched",
        "mode": mode,
        "active_path": str(payload),
        "installed_path": str(release),
        "installed_version": old["version"],
        "source_version": source_version,
        "targets": targets,
        "changes": transaction.summary(),
        "reload_required": targets,
        "loaded_host_processes": "unverified",
    }
    if not dry_run:
        transaction.apply()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Switch the owned Graph Skill desktop source")
    parser.add_argument("mode", choices=("test", "installed", "status"))
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "status":
            if args.source is not None:
                raise InstallError("Status does not take a source directory")
            result = source_status()
        elif args.dry_run:
            result = switch(args.mode, args.source, True)
        else:
            with installer_lock(install.state_root()):
                result = switch(args.mode, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, InstallError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
