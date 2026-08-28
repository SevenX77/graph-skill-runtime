#!/usr/bin/env python
"""Validate and exercise one immutable Graph Skill Runtime release candidate."""

from __future__ import annotations

import argparse
import asyncio
import configparser
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast

_DISTRIBUTION: Final = "graph-skill-runtime"
_IMPORT_PACKAGE: Final = "graph_skill_runtime"
_CONSOLE_ENTRY: Final = "graph_skill_runtime.adapters.cli:main"
_ARTIFACT_SCHEMA: Final = "gskill.release-artifacts.v1"
_ACCEPTANCE_SCHEMA: Final = "gskill.package-acceptance.v1"
_MOIRAI_PREFIX: Final = "graph_skill_runtime/integrations/assets/moirai/"
_MOIRAI_MANIFEST: Final = _MOIRAI_PREFIX + "integration.json"
_EXPECTED_MCP_TOOLS: Final = {
    "compile",
    "evaluate_golden",
    "inspect",
    "predict",
    "resolve_run",
    "resume",
    "run",
    "submit_agent_result",
}
_EXPECTED_MCP_ANNOTATIONS: Final = {
    "compile": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "resolve_run": {"readOnlyHint": True, "openWorldHint": False},
    "predict": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
    "run": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    "resume": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    "submit_agent_result": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "inspect": {"readOnlyHint": True, "openWorldHint": False},
    "evaluate_golden": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
}
_WHEEL_BASE_MEMBERS: Final = {
    "graph_skill_runtime/__init__.py",
    "graph_skill_runtime/migration/atomic_publish.py",
    "graph_skill_runtime/migration/studio_v030.py",
    "graph_skill_runtime/py.typed",
    "graph_skill_runtime/skills/builtin/md-patch/SKILL.md",
}
_WHEEL_FORBIDDEN_MEMBERS: Final = {
    "graph_skill_runtime/CHANGELOG.md",
    "graph_skill_runtime/requirements.txt",
}
_WHEEL_FORBIDDEN_PREFIXES: Final = (
    "graph_agent/",
    "graph_skill_runtime/examples/",
)
_COMMAND_TIMEOUT_SECONDS: Final = 900.0
_COMMIT_PATTERN: Final = re.compile(r"^[0-9a-fA-F]{40}$")
_WHEEL_PATTERN: Final = re.compile(
    r"^graph_skill_runtime-(?P<version>.+)-py3-none-any\.whl$"
)
_SDIST_PATTERN: Final = re.compile(r"^graph_skill_runtime-(?P<version>.+)\.tar\.gz$")

JsonObject = dict[str, Any]


def _unique_json_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    document: JsonObject = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _load_json_bytes(content: bytes, *, source: str) -> JsonObject:
    try:
        value = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{source} is not unique-key UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{source} must contain a JSON object")
    return cast(JsonObject, value)


def _load_json_file(path: Path) -> JsonObject:
    try:
        return _load_json_bytes(path.read_bytes(), source=str(path))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _validate_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute():
        raise ValueError(f"archive contains a non-portable path: {name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"archive contains an unsafe path: {name!r}")


def _manifest_string_items(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"MoirAI manifest field {field!r} must be a non-empty string list")
    items = cast(tuple[str, ...], tuple(value))
    if len(items) != len(set(items)):
        raise ValueError(f"MoirAI manifest field {field!r} contains duplicates")
    return items


def _manifest_entry_ids(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"MoirAI manifest field {field!r} must be a non-empty list")
    identifiers: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"MoirAI manifest field {field!r} must contain objects")
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"MoirAI manifest field {field!r} contains an invalid id")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"MoirAI manifest field {field!r} contains duplicate ids")
    return tuple(identifiers)


def _moirai_members(manifest: JsonObject, *, prefix: str) -> set[str]:
    roles = _manifest_entry_ids(manifest.get("roles"), field="roles")
    skills = _manifest_entry_ids(manifest.get("skills"), field="skills")
    knowledge = _manifest_string_items(manifest.get("knowledge"), field="knowledge")
    return {
        prefix + "integration.json",
        *(prefix + f"roles/{role_id}.md" for role_id in roles),
        *(prefix + f"skills/{skill_id}/SKILL.md" for skill_id in skills),
        *(prefix + f"knowledge/{filename}" for filename in knowledge),
    }


def _metadata(content: bytes, *, source: str) -> Mapping[str, str]:
    try:
        return Parser().parsestr(content.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{source} metadata is not UTF-8: {exc}") from exc


def _require_metadata(
    content: bytes,
    *,
    source: str,
    version: str,
) -> None:
    metadata = _metadata(content, source=source)
    expected = {
        "Name": _DISTRIBUTION,
        "Version": version,
        "Requires-Python": ">=3.11",
    }
    actual = {field: metadata.get(field) for field in expected}
    if actual != expected:
        raise ValueError(f"{source} metadata mismatch: expected {expected}, got {actual}")


def _wheel_version(path: Path) -> str:
    match = _WHEEL_PATTERN.fullmatch(path.name)
    if match is None:
        raise ValueError(f"wheel filename does not match the pure-Python release contract: {path.name}")
    return match.group("version")


def _sdist_version(path: Path) -> str:
    match = _SDIST_PATTERN.fullmatch(path.name)
    if match is None:
        raise ValueError(f"sdist filename does not match the release contract: {path.name}")
    return match.group("version")


def _validate_wheel(path: Path) -> str:
    version = _wheel_version(path)
    if not path.is_file():
        raise ValueError(f"wheel does not exist: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("wheel contains duplicate member names")
            for info in infos:
                _validate_archive_name(info.filename)
                member_type = (info.external_attr >> 16) & 0o170000
                if member_type == stat.S_IFLNK:
                    raise ValueError(f"wheel contains a symbolic link: {info.filename}")
            member_set = set(names)
            manifest = _load_json_bytes(
                archive.read(_MOIRAI_MANIFEST),
                source=f"{path}:{_MOIRAI_MANIFEST}",
            )
            expected_moirai = _moirai_members(manifest, prefix=_MOIRAI_PREFIX)
            dist_info_roots = {
                name.split("/", 1)[0]
                for name in names
                if name.split("/", 1)[0].endswith(".dist-info")
            }
            if len(dist_info_roots) != 1:
                raise ValueError("wheel must contain exactly one .dist-info directory")
            dist_info = next(iter(dist_info_roots))
            required_dist_info = {
                f"{dist_info}/METADATA",
                f"{dist_info}/WHEEL",
                f"{dist_info}/entry_points.txt",
                f"{dist_info}/licenses/LICENSE",
                f"{dist_info}/RECORD",
            }
            missing = sorted(
                (_WHEEL_BASE_MEMBERS | expected_moirai | required_dist_info) - member_set
            )
            forbidden = sorted(_WHEEL_FORBIDDEN_MEMBERS & member_set)
            forbidden.extend(
                sorted(
                    name
                    for name in member_set
                    if name.startswith(_WHEEL_FORBIDDEN_PREFIXES)
                )
            )
            forbidden.extend(
                sorted(
                    name
                    for name in member_set
                    if name.startswith(_MOIRAI_PREFIX) and name not in expected_moirai
                )
            )
            if missing or forbidden:
                details: list[str] = []
                if missing:
                    details.append("missing: " + ", ".join(missing[:10]))
                if forbidden:
                    details.append("forbidden: " + ", ".join(forbidden[:10]))
                raise ValueError("invalid wheel contents; " + "; ".join(details))
            _require_metadata(
                archive.read(f"{dist_info}/METADATA"),
                source=f"{path}:METADATA",
                version=version,
            )
            wheel_metadata = archive.read(f"{dist_info}/WHEEL").decode("utf-8")
            if "Root-Is-Purelib: true" not in wheel_metadata or "Tag: py3-none-any" not in wheel_metadata:
                raise ValueError("wheel metadata does not declare one pure py3-none-any artifact")
            entry_points = configparser.ConfigParser(interpolation=None)
            entry_points.optionxform = str
            entry_points.read_string(
                archive.read(f"{dist_info}/entry_points.txt").decode("utf-8")
            )
            actual_scripts = dict(entry_points.items("console_scripts"))
            if actual_scripts != {"gskill": _CONSOLE_ENTRY}:
                raise ValueError(f"wheel console entry points differ: {actual_scripts}")
    except (KeyError, UnicodeDecodeError, configparser.Error, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid wheel {path}: {exc}") from exc
    return version


def _tar_file_bytes(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise ValueError(f"sdist is missing {name}") from exc
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"sdist member is not a regular file: {name}")
    return stream.read()


def _validate_sdist(path: Path) -> str:
    version = _sdist_version(path)
    if not path.is_file():
        raise ValueError(f"sdist does not exist: {path}")
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise ValueError("sdist contains duplicate member names")
            for member in members:
                _validate_archive_name(member.name)
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"sdist contains a non-regular member: {member.name}")
            roots = {PurePosixPath(name).parts[0] for name in names}
            expected_root = f"graph_skill_runtime-{version}"
            if roots != {expected_root}:
                raise ValueError(f"sdist root mismatch: expected {expected_root!r}, got {sorted(roots)}")
            file_names = {member.name for member in members if member.isfile()}
            package_prefix = f"{expected_root}/src/"
            manifest_name = package_prefix + _MOIRAI_MANIFEST
            manifest = _load_json_bytes(
                _tar_file_bytes(archive, manifest_name),
                source=f"{path}:{manifest_name}",
            )
            expected_moirai = _moirai_members(
                manifest,
                prefix=package_prefix + _MOIRAI_PREFIX,
            )
            required = {
                f"{expected_root}/LICENSE",
                f"{expected_root}/PKG-INFO",
                f"{expected_root}/README.md",
                f"{expected_root}/pyproject.toml",
                f"{expected_root}/src/graph_skill_runtime/__init__.py",
                f"{expected_root}/src/graph_skill_runtime/py.typed",
                *expected_moirai,
            }
            missing = sorted(required - file_names)
            forbidden = sorted(
                name
                for name in file_names
                if name.startswith(f"{expected_root}/src/graph_agent/")
                or name.startswith(
                    f"{expected_root}/src/graph_skill_runtime/examples/"
                )
                or (
                    name.startswith(package_prefix + _MOIRAI_PREFIX)
                    and name not in expected_moirai
                )
            )
            if missing or forbidden:
                details: list[str] = []
                if missing:
                    details.append("missing: " + ", ".join(missing[:10]))
                if forbidden:
                    details.append("forbidden: " + ", ".join(forbidden[:10]))
                raise ValueError("invalid sdist contents; " + "; ".join(details))
            _require_metadata(
                _tar_file_bytes(archive, f"{expected_root}/PKG-INFO"),
                source=f"{path}:PKG-INFO",
                version=version,
            )
            project = tomllib.loads(
                _tar_file_bytes(archive, f"{expected_root}/pyproject.toml").decode(
                    "utf-8"
                )
            )["project"]
            if project.get("name") != _DISTRIBUTION or project.get("version") != version:
                raise ValueError("sdist pyproject name/version differs from its filename")
            if project.get("scripts") != {"gskill": _CONSOLE_ENTRY}:
                raise ValueError("sdist pyproject console entry point differs")
    except (KeyError, UnicodeDecodeError, tarfile.TarError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid sdist {path}: {exc}") from exc
    return version


def _discover_distributions(dist_dir: Path) -> tuple[Path, Path]:
    resolved = dist_dir.expanduser().resolve(strict=False)
    if not resolved.is_dir():
        raise ValueError(f"distribution directory does not exist: {resolved}")
    files = sorted(path for path in resolved.iterdir() if path.is_file())
    uv_ignore = resolved / ".gitignore"
    if uv_ignore in files:
        if uv_ignore.read_bytes().strip() != b"*":
            raise ValueError("uv-created dist/.gitignore contains unexpected content")
        files.remove(uv_ignore)
    wheels = [path for path in files if path.suffix == ".whl"]
    sdists = [path for path in files if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1 or len(files) != 2:
        raise ValueError(
            "distribution directory must contain exactly one wheel and one .tar.gz sdist; "
            f"found {[path.name for path in files]}"
        )
    return wheels[0], sdists[0]


def _artifact_record(path: Path, *, kind: str) -> JsonObject:
    return {
        "kind": kind,
        "filename": path.name,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _validate_distributions(
    *,
    dist_dir: Path,
    source_commit: str,
) -> JsonObject:
    if _COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise ValueError("source_commit must be the exact 40-hex checkout commit")
    wheel, sdist = _discover_distributions(dist_dir)
    wheel_version = _validate_wheel(wheel)
    sdist_version = _validate_sdist(sdist)
    if wheel_version != sdist_version:
        raise ValueError(
            f"wheel/sdist version mismatch: {wheel_version!r} != {sdist_version!r}"
        )
    return {
        "schema_version": _ARTIFACT_SCHEMA,
        "distribution": _DISTRIBUTION,
        "version": wheel_version,
        "source_commit": source_commit.lower(),
        "artifacts": [
            _artifact_record(sdist, kind="sdist"),
            _artifact_record(wheel, kind="wheel"),
        ],
    }


def _artifact_entries(manifest: JsonObject) -> dict[str, JsonObject]:
    if set(manifest) != {
        "schema_version",
        "distribution",
        "version",
        "source_commit",
        "artifacts",
    }:
        raise ValueError("release artifact manifest has unknown or missing top-level fields")
    if manifest.get("schema_version") != _ARTIFACT_SCHEMA:
        raise ValueError("release artifact manifest schema is unsupported")
    if manifest.get("distribution") != _DISTRIBUTION:
        raise ValueError("release artifact manifest names another distribution")
    version = manifest.get("version")
    commit = manifest.get("source_commit")
    if not isinstance(version, str) or not version:
        raise ValueError("release artifact manifest version must be non-empty")
    if not isinstance(commit, str) or _COMMIT_PATTERN.fullmatch(commit) is None:
        raise ValueError("release artifact manifest source_commit must be 40 hex characters")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError("release artifact manifest must contain exactly two artifacts")
    by_kind: dict[str, JsonObject] = {}
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ValueError("release artifact entries must be objects")
        entry = cast(JsonObject, raw)
        kind = entry.get("kind")
        if kind not in {"wheel", "sdist"} or kind in by_kind:
            raise ValueError("release artifact kinds must be exactly wheel and sdist")
        if set(entry) != {"kind", "filename", "size", "sha256"}:
            raise ValueError(f"release artifact {kind!r} has unknown or missing fields")
        filename = entry.get("filename")
        size = entry.get("size")
        digest = entry.get("sha256")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"release artifact {kind!r} filename is not a basename")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError(f"release artifact {kind!r} size must be positive")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"release artifact {kind!r} SHA-256 is invalid")
        by_kind[cast(str, kind)] = entry
    return by_kind


def _verify_artifact_manifest(
    *,
    dist_dir: Path,
    manifest_path: Path,
) -> tuple[JsonObject, Path, Path]:
    manifest = _load_json_file(manifest_path)
    by_kind = _artifact_entries(manifest)
    resolved_dist = dist_dir.expanduser().resolve(strict=False)
    paths: dict[str, Path] = {}
    for kind, entry in by_kind.items():
        path = (resolved_dist / cast(str, entry["filename"])).resolve(strict=False)
        if path.parent != resolved_dist or not path.is_file():
            raise ValueError(f"manifest-owned {kind} is missing from {resolved_dist}")
        if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
            raise ValueError(f"manifest-owned {kind} bytes do not match size/SHA-256")
        paths[kind] = path
    wheel_version = _validate_wheel(paths["wheel"])
    sdist_version = _validate_sdist(paths["sdist"])
    if wheel_version != manifest["version"] or sdist_version != manifest["version"]:
        raise ValueError("artifact version differs from the release artifact manifest")
    return manifest, paths["wheel"], paths["sdist"]


def _run_checked(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float = _COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(env),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"command could not complete: {argv[0]}: {exc}") from exc
    if result.returncode != 0:
        raise ValueError(
            f"command failed ({result.returncode}): {list(argv)!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _run_checked_bytes(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float = _COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(env),
            text=False,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"command could not complete: {argv[0]}: {exc}") from exc
    if result.returncode != 0:
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise ValueError(
            f"command failed ({result.returncode}): {list(argv)!r}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return result


def _controlled_environment(*, home: Path, config: Path, cache: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "APPDATA": str(config),
            "HOME": str(home),
            "LOCALAPPDATA": str(config),
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "USERPROFILE": str(home),
            "UV_CACHE_DIR": str(cache),
            "XDG_CACHE_HOME": str(cache),
            "XDG_CONFIG_HOME": str(config),
        }
    )
    return environment


def _environment_python(root: Path) -> Path:
    windows = root / "Scripts" / "python.exe"
    return windows if windows.is_file() else root / "bin" / "python"


def _environment_gskill(root: Path) -> Path:
    windows = root / "Scripts" / "gskill.exe"
    return windows if windows.is_file() else root / "bin" / "gskill"


def _create_uv_environment(
    *,
    uv: Path,
    root: Path,
    seed: bool,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    argv = [str(uv), "venv", "--python", sys.executable]
    if seed:
        argv.append("--seed")
    argv.append(str(root))
    _run_checked(argv, cwd=cwd, env=env)
    if not _environment_python(root).is_file():
        raise ValueError(f"environment Python was not created: {root}")


def _install_with_pip(
    *,
    environment_root: Path,
    artifact: Path,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    _run_checked(
        [
            str(_environment_python(environment_root)),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--no-input",
            str(artifact),
        ],
        cwd=cwd,
        env=env,
    )


def _install_with_uv(
    *,
    uv: Path,
    environment_root: Path,
    artifact: Path,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    _run_checked(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(_environment_python(environment_root)),
            str(artifact),
        ],
        cwd=cwd,
        env=env,
    )


def _tree_snapshot(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            path.relative_to(root).as_posix() + ("/" if path.is_dir() else "")
            for path in root.rglob("*")
        )
    )


def _cli_json(
    gskill: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> JsonObject:
    result = _run_checked([str(gskill), *arguments], cwd=cwd, env=env)
    return _load_json_bytes(result.stdout.encode("utf-8"), source=f"gskill {' '.join(arguments)}")


def _assert_cli_utf8_transport(
    gskill: Path,
    *,
    skill_root: Path,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    legacy_environment = dict(env)
    legacy_environment["PYTHONUTF8"] = "0"
    legacy_environment["PYTHONIOENCODING"] = "cp936"
    expected = "全局安装"
    result = _run_checked_bytes(
        [
            str(gskill),
            "config",
            "resolve",
            str(skill_root),
            "--run-id",
            "utf8-transport",
            "--inputs-json",
            json.dumps({"name": expected}, ensure_ascii=False),
        ],
        cwd=cwd,
        env=legacy_environment,
    )
    payload = _load_json_bytes(result.stdout, source="gskill UTF-8 transport probe")
    request = cast(JsonObject, payload.get("request"))
    inputs = cast(JsonObject, request.get("inputs"))
    if inputs.get("name") != expected:
        raise ValueError("installed console did not preserve UTF-8 JSON text")


def _assert_completed(payload: JsonObject, *, mode: str) -> None:
    if payload.get("status") != "completed" or payload.get("mode") != mode:
        raise ValueError(f"expected completed {mode} result, got {payload}")


def _sqlite_integrity(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"expected durable SQLite database: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if row != ("ok",):
        raise ValueError(f"SQLite integrity check failed for {path}: {row}")
    moved = path.with_name(path.name + ".reopen")
    os.replace(path, moved)
    os.replace(moved, path)


async def _mcp_smoke(
    *,
    gskill: Path,
    skill_root: Path,
    work_root: Path,
    env: Mapping[str, str],
) -> tuple[str, ...]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    error_log_path = work_root / "mcp-stderr.log"
    parameters = StdioServerParameters(
        command=str(gskill),
        args=["mcp"],
        env=dict(env),
        cwd=work_root,
        encoding="utf-8",
        encoding_error_handler="replace",
    )
    with error_log_path.open("w", encoding="utf-8", newline="\n") as error_log:
        async with stdio_client(parameters, errlog=error_log) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=30,
            ) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = tuple(sorted(tool.name for tool in tools.tools))
                if set(names) != _EXPECTED_MCP_TOOLS:
                    raise ValueError(f"installed MCP tool inventory differs: {names}")
                annotations = {
                    tool.name: tool.annotations.model_dump(by_alias=True, exclude_none=True)
                    if tool.annotations is not None
                    else None
                    for tool in tools.tools
                }
                if annotations != _EXPECTED_MCP_ANNOTATIONS:
                    raise ValueError(f"installed MCP tool annotations differ: {annotations}")
                result = await session.call_tool(
                    "compile",
                    {
                        "request": {
                            "schema_version": "gskill.compile-request.v1",
                            "kind": "compile_request",
                            "skill_root": str(skill_root),
                            "cache": False,
                        }
                    },
                )
                if getattr(result, "isError", False):
                    raise ValueError(f"installed MCP compile returned an error: {result}")
                structured = getattr(result, "structuredContent", None)
                if structured is None:
                    structured = getattr(result, "structured_content", None)
                if not isinstance(structured, dict) or structured.get("status") != "passed":
                    raise ValueError(f"installed MCP compile payload differs: {structured}")
                inspected = await session.call_tool(
                    "inspect",
                    {
                        "request": {
                            "schema_version": "gskill.inspect-request.v1",
                            "kind": "inspect_request",
                            "skill_root": str(skill_root),
                            "include_call_graph": True,
                        }
                    },
                )
                if getattr(inspected, "isError", False):
                    raise ValueError(f"installed MCP inspect returned an error: {inspected}")
                inspected_content = getattr(inspected, "structuredContent", None)
                if inspected_content is None:
                    inspected_content = getattr(inspected, "structured_content", None)
                if not isinstance(inspected_content, dict) or inspected_content.get(
                    "skill_id"
                ) != "hello-world":
                    raise ValueError(
                        f"installed MCP inspect payload differs: {inspected_content}"
                    )
    return names


def _installed_distribution_smoke(args: argparse.Namespace) -> JsonObject:
    environment_root = Path(args.environment_root).resolve(strict=True)
    work_root = Path(args.work_root).resolve(strict=True)
    logic_skill = Path(args.logic_skill).resolve(strict=True)
    agent_skill = Path(args.agent_skill).resolve(strict=True)
    expected_version = cast(str, args.expected_version)
    gskill = _environment_gskill(environment_root)
    if not gskill.is_file():
        raise ValueError(f"installed gskill command is missing: {gskill}")

    controlled_root = work_root / "受控 host state"
    home = controlled_root / "home"
    config = controlled_root / "config"
    cache = controlled_root / "cache"
    for directory in (home, config, cache):
        directory.mkdir(parents=True, exist_ok=True)
    before_state = _tree_snapshot(controlled_root)
    environment = _controlled_environment(home=home, config=config, cache=cache)

    spec = importlib.util.find_spec(_IMPORT_PACKAGE)
    if spec is None or spec.origin is None:
        raise ValueError("installed graph_skill_runtime import cannot be resolved")
    module_path = Path(spec.origin).resolve(strict=True)
    if not module_path.is_relative_to(environment_root):
        raise ValueError(f"graph_skill_runtime resolved outside the clean environment: {module_path}")
    runtime = importlib.import_module(_IMPORT_PACKAGE)
    if Path(runtime.__file__).resolve(strict=True) != module_path:
        raise ValueError("resolved and imported graph_skill_runtime paths differ")
    if importlib.metadata.version(_DISTRIBUTION) != expected_version:
        raise ValueError("installed distribution version differs from the candidate")
    for optional in ("dotenv", "langchain_openai", "openai"):
        if importlib.util.find_spec(optional) is not None:
            raise ValueError(f"base distribution unexpectedly installed optional provider module {optional}")

    from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets

    assets = PackagedMoiraiAssets()
    if (len(assets.role_ids()), len(assets.skill_ids())) != (4, 8):
        raise ValueError("installed MoirAI role/skill inventory differs")
    distribution = importlib.metadata.distribution(_DISTRIBUTION)
    installed_files = tuple(str(item).replace("\\", "/") for item in distribution.files or ())
    if any("graph_skill_runtime/examples/" in name for name in installed_files):
        raise ValueError("installed distribution leaked a user business skill example")
    if any(name.endswith("/graph.yaml") for name in installed_files):
        raise ValueError("installed distribution leaked a business graph.yaml")

    version_result = _run_checked([str(gskill), "--version"], cwd=work_root, env=environment)
    if version_result.stdout.strip() != f"gskill {expected_version}":
        raise ValueError(f"installed console version differs: {version_result.stdout!r}")
    _assert_cli_utf8_transport(
        gskill,
        skill_root=logic_skill,
        cwd=work_root,
        env=environment,
    )
    detections = _cli_json(gskill, ["integrations", "detect"], cwd=work_root, env=environment)
    detection_targets = {
        item.get("target")
        for item in cast(list[JsonObject], detections.get("detections", []))
        if isinstance(item, dict)
    }
    if detection_targets != {"claude", "codex", "copilot", "cursor", "gemini", "opencode"}:
        raise ValueError(f"installed host detection inventory differs: {detection_targets}")
    mcp_tools = asyncio.run(
        _mcp_smoke(
            gskill=gskill,
            skill_root=logic_skill,
            work_root=work_root,
            env=environment,
        )
    )
    read_only_state = _tree_snapshot(controlled_root)
    if read_only_state != before_state:
        raise ValueError(
            "install/import/version/detection wrote implicit host state: "
            f"before={before_state}, after={read_only_state}"
        )

    compile_result = _cli_json(
        gskill,
        ["compile", str(logic_skill), "--no-cache"],
        cwd=work_root,
        env=environment,
    )
    if compile_result.get("status") != "passed" or compile_result.get("diagnostics") != []:
        raise ValueError(f"installed CLI compile failed: {compile_result}")
    inspect_result = _cli_json(
        gskill,
        ["inspect", str(logic_skill), "--call-graph"],
        cwd=work_root,
        env=environment,
    )
    if inspect_result.get("skill_id") != "hello-world":
        raise ValueError(f"installed CLI inspect differs: {inspect_result}")

    non_ascii_name = "发布验收"
    predict_state = work_root / "状态 空间" / "predict"
    predict_result = _cli_json(
        gskill,
        [
            "predict",
            str(logic_skill),
            "--run-id",
            "package-predict",
            "--state-dir",
            str(predict_state),
            "--inputs-json",
            json.dumps({"name": non_ascii_name}, ensure_ascii=False),
        ],
        cwd=work_root,
        env=environment,
    )
    _assert_completed(predict_result, mode="predict")
    if non_ascii_name not in cast(str, cast(JsonObject, predict_result["outputs"])["greeting"]):
        raise ValueError("installed predict lost non-ASCII argv or output text")

    run_state = work_root / "状态 空间" / "run"
    run_result = _cli_json(
        gskill,
        [
            "run",
            str(logic_skill),
            "--run-id",
            "package-run",
            "--state-dir",
            str(run_state),
            "--executor",
            "host-native",
            "--inputs-json",
            json.dumps({"name": non_ascii_name}, ensure_ascii=False),
        ],
        cwd=work_root,
        env=environment,
    )
    _assert_completed(run_result, mode="run")
    if non_ascii_name not in cast(str, cast(JsonObject, run_result["outputs"])["greeting"]):
        raise ValueError("installed run lost non-ASCII argv or output text")

    integration_project = work_root / "integration project"
    integration_project.mkdir()
    integration_arguments = [
        "integrations",
        "install",
        "moirai",
        "--targets",
        "claude,codex",
        "--scope",
        "project",
        "--project-root",
        str(integration_project),
    ]
    planned = _cli_json(
        gskill,
        [*integration_arguments, "--dry-run"],
        cwd=work_root,
        env=environment,
    )
    installed = _cli_json(gskill, integration_arguments, cwd=work_root, env=environment)
    unchanged = _cli_json(gskill, integration_arguments, cwd=work_root, env=environment)
    uninstalled = _cli_json(
        gskill,
        [
            "integrations",
            "uninstall",
            "moirai",
            "--targets",
            "claude,codex",
            "--scope",
            "project",
            "--project-root",
            str(integration_project),
        ],
        cwd=work_root,
        env=environment,
    )
    statuses = tuple(item.get("status") for item in (planned, installed, unchanged, uninstalled))
    if statuses != ("planned", "installed", "unchanged", "uninstalled"):
        raise ValueError(f"installed MoirAI projection lifecycle differs: {statuses}")
    if any(path.is_file() for path in integration_project.rglob("*")):
        raise ValueError("installed MoirAI uninstall left manifest-owned files behind")

    handoff_state = work_root / "状态 空间" / "handoff"
    required = _cli_json(
        gskill,
        [
            "run",
            str(agent_skill),
            "--run-id",
            "package-handoff",
            "--state-dir",
            str(handoff_state),
            "--executor",
            "host-native",
            "--inputs-json",
            json.dumps({"note": "durable package handoff"}),
        ],
        cwd=work_root,
        env=environment,
    )
    if required.get("status") != "agent_required":
        raise ValueError(f"installed host-native run did not pause durably: {required}")
    agent_required = cast(JsonObject, required["agent_required"])
    task = cast(JsonObject, agent_required["task"])
    checkpoint_ref = cast(str, agent_required["checkpoint_ref"])
    reopened_wait = _cli_json(
        gskill,
        [
            "resume",
            str(agent_skill),
            "package-handoff",
            "--state-root",
            str(handoff_state),
            "--checkpoint-ref",
            checkpoint_ref,
        ],
        cwd=work_root,
        env=environment,
    )
    if reopened_wait.get("status") != "agent_required":
        raise ValueError(f"installed resume did not reopen the durable wait: {reopened_wait}")
    result_payload = {
        "schema_version": "gskill.agent-result.v1",
        "kind": "agent_result",
        "task_id": task["task_id"],
        "status": "completed",
        "output": {"echoed_note": "三平台回交"},
        "error": None,
        "executor_id": "release/host-native",
        "provenance": {"acceptance": args.channel},
    }
    submit_arguments = [
        "submit",
        "package-handoff",
        "--state-root",
        str(handoff_state),
        "--checkpoint-ref",
        checkpoint_ref,
        "--result-json",
        json.dumps(result_payload, ensure_ascii=False, separators=(",", ":")),
    ]
    completed = _cli_json(gskill, submit_arguments, cwd=work_root, env=environment)
    duplicate = _cli_json(gskill, submit_arguments, cwd=work_root, env=environment)
    reopened_terminal = _cli_json(
        gskill,
        [
            "resume",
            str(agent_skill),
            "package-handoff",
            "--state-root",
            str(handoff_state),
            "--checkpoint-ref",
            checkpoint_ref,
        ],
        cwd=work_root,
        env=environment,
    )
    _assert_completed(completed, mode="resume")
    if duplicate != completed or reopened_terminal != completed:
        raise ValueError("installed handoff retry/reopen did not return the same causal result")
    if cast(JsonObject, completed["outputs"]).get("echoed_note") != "三平台回交":
        raise ValueError(f"installed handoff output differs: {completed['outputs']}")

    for database in (
        handoff_state / "checkpoints.sqlite3",
        handoff_state / "agent-handoffs.sqlite3",
    ):
        _sqlite_integrity(database)
    request_snapshot = handoff_state / "runs" / "package-handoff" / "request.json"
    trace = handoff_state / "runs" / "package-handoff" / "trace.jsonl"
    if not request_snapshot.is_file() or not trace.is_file():
        raise ValueError("installed handoff omitted its immutable request snapshot or trace")

    after_state = _tree_snapshot(controlled_root)
    allowed_runtime_cache = {
        "home/.cache/",
        "home/.cache/graph-skill-runtime-portable-v1/",
    }
    unexpected_host_changes = sorted(
        item
        for item in set(after_state) - set(before_state)
        if item not in allowed_runtime_cache
        and not item.startswith("home/.cache/graph-skill-runtime-portable-v1/")
    )
    if unexpected_host_changes:
        raise ValueError(
            "runtime operations wrote state outside the owned compile cache: "
            + ", ".join(unexpected_host_changes)
        )
    return {
        "schema_version": "gskill.installed-smoke.v1",
        "channel": args.channel,
        "distribution_version": expected_version,
        "python": platform.python_version(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "module_path": str(module_path),
        "mcp_tools": list(mcp_tools),
        "compile_status": compile_result["status"],
        "predict_status": predict_result["status"],
        "run_status": run_result["status"],
        "handoff_statuses": [
            required["status"],
            reopened_wait["status"],
            completed["status"],
            duplicate["status"],
            reopened_terminal["status"],
        ],
        "integration_statuses": list(statuses),
        "unexpected_host_state_changes": unexpected_host_changes,
    }


def _copy_verified_artifact(source: Path, destination: Path, expected_hash: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if _sha256(destination) != expected_hash:
        raise ValueError(f"artifact copy changed bytes: {source}")
    return destination


def _accept_distributions(args: argparse.Namespace) -> JsonObject:
    manifest_path = Path(args.manifest).resolve(strict=True)
    manifest, wheel, sdist = _verify_artifact_manifest(
        dist_dir=Path(args.dist_dir),
        manifest_path=manifest_path,
    )
    expected_commit = cast(str, args.expected_source_commit).lower()
    if _COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected source commit must be exactly 40 hexadecimal characters")
    if manifest["source_commit"] != expected_commit:
        raise ValueError(
            "release artifact manifest belongs to a different checkout: "
            f"expected {expected_commit}, got {manifest['source_commit']}"
        )
    logic_source = Path(args.logic_skill).resolve(strict=True)
    agent_source = Path(args.agent_skill).resolve(strict=True)
    for source, files in (
        (logic_source, ("SKILL.md", "graph.yaml")),
        (agent_source, ("SKILL.md", "graph.yaml")),
    ):
        if not source.is_dir() or any(not (source / name).is_file() for name in files):
            raise ValueError(f"acceptance fixture is incomplete: {source}")
    uv_name = args.uv_executable or shutil.which("uv")
    if uv_name is None:
        raise ValueError("uv executable is required for clean package acceptance")
    uv = Path(uv_name).expanduser().resolve(strict=True)
    entries = _artifact_entries(manifest)
    with tempfile.TemporaryDirectory(prefix="graph skill release 验收 ") as temporary_name:
        temporary = Path(temporary_name).resolve(strict=True)
        artifact_root = temporary / "immutable candidate"
        copied_wheel = _copy_verified_artifact(
            wheel,
            artifact_root / wheel.name,
            cast(str, entries["wheel"]["sha256"]),
        )
        copied_sdist = _copy_verified_artifact(
            sdist,
            artifact_root / sdist.name,
            cast(str, entries["sdist"]["sha256"]),
        )
        channels = (
            ("pip-wheel", copied_wheel, "pip"),
            ("uv-wheel", copied_wheel, "uv"),
            ("pip-sdist", copied_sdist, "pip"),
        )
        observations: list[JsonObject] = []
        for channel, artifact, installer in channels:
            channel_root = temporary / channel
            environment_root = channel_root / "clean environment"
            work_root = channel_root / "运行 工作区"
            home = channel_root / "installer home"
            config = channel_root / "installer config"
            cache = channel_root / "installer cache"
            for directory in (work_root, home, config, cache):
                directory.mkdir(parents=True, exist_ok=True)
            environment = _controlled_environment(home=home, config=config, cache=cache)
            _create_uv_environment(
                uv=uv,
                root=environment_root,
                seed=installer == "pip",
                cwd=work_root,
                env=environment,
            )
            if installer == "pip":
                _install_with_pip(
                    environment_root=environment_root,
                    artifact=artifact,
                    cwd=work_root,
                    env=environment,
                )
            else:
                _install_with_uv(
                    uv=uv,
                    environment_root=environment_root,
                    artifact=artifact,
                    cwd=work_root,
                    env=environment,
                )
            logic_skill = work_root / "业务 技能" / "hello-world"
            agent_skill = work_root / "业务 技能" / "demo-echo-agent"
            shutil.copytree(logic_source, logic_skill)
            shutil.copytree(agent_source, agent_skill)
            smoke = _run_checked(
                [
                    str(_environment_python(environment_root)),
                    str(Path(__file__).resolve(strict=True)),
                    "installed-smoke",
                    "--environment-root",
                    str(environment_root),
                    "--work-root",
                    str(work_root),
                    "--logic-skill",
                    str(logic_skill),
                    "--agent-skill",
                    str(agent_skill),
                    "--expected-version",
                    cast(str, manifest["version"]),
                    "--channel",
                    channel,
                ],
                cwd=work_root,
                env=environment,
            )
            observations.append(
                _load_json_bytes(
                    smoke.stdout.encode("utf-8"),
                    source=f"{channel} installed smoke",
                )
            )
        evidence: JsonObject = {
            "schema_version": _ACCEPTANCE_SCHEMA,
            "distribution": _DISTRIBUTION,
            "version": manifest["version"],
            "source_commit": manifest["source_commit"],
            "artifact_manifest_sha256": _sha256(manifest_path),
            "artifacts": manifest["artifacts"],
            "observations": observations,
        }
    _atomic_json_write(Path(args.evidence).resolve(strict=False), evidence)
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and exercise one immutable Graph Skill Runtime release candidate"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate archives and write their hash manifest")
    validate.add_argument("--dist-dir", required=True)
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--source-commit", required=True)

    accept = commands.add_parser(
        "accept",
        help="Verify a hash manifest, install both artifacts, and run packaged smoke",
    )
    accept.add_argument("--dist-dir", required=True)
    accept.add_argument("--manifest", required=True)
    accept.add_argument("--expected-source-commit", required=True)
    accept.add_argument("--logic-skill", required=True)
    accept.add_argument("--agent-skill", required=True)
    accept.add_argument("--evidence", required=True)
    accept.add_argument("--uv-executable")

    installed = commands.add_parser("installed-smoke", help=argparse.SUPPRESS)
    installed.add_argument("--environment-root", required=True)
    installed.add_argument("--work-root", required=True)
    installed.add_argument("--logic-skill", required=True)
    installed.add_argument("--agent-skill", required=True)
    installed.add_argument("--expected-version", required=True)
    installed.add_argument(
        "--channel",
        choices=("pip-wheel", "uv-wheel", "pip-sdist"),
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = _validate_distributions(
                dist_dir=Path(args.dist_dir),
                source_commit=args.source_commit,
            )
            _atomic_json_write(Path(args.manifest).resolve(strict=False), result)
        elif args.command == "accept":
            result = _accept_distributions(args)
        else:
            result = _installed_distribution_smoke(args)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
