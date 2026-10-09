"""Inspect a source-bound archive; optionally exercise its private interpreters."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from bundle import REPOSITORY, ROOT, product_files, source_identity
from ownership import InstallError, digest, json_bytes
from runtime_layout import current_target


def verify_members(source: zipfile.ZipFile, prefix: str, identity: dict) -> dict:
    names = source.namelist()
    if len(names) != len(set(names)):
        raise InstallError("Duplicate archive members")
    for name in names:
        path = PurePosixPath(name)
        if not name.startswith(prefix) or path.is_absolute() or ".." in path.parts or "\\" in name:
            raise InstallError(f"Unsafe archive member: {name}")
    manifest = json.loads(source.read(prefix + "bundle.json"))
    if any(manifest.get(key) != value for key, value in identity.items()):
        raise InstallError("Archive/source identity mismatch")
    inventory = manifest["files"]
    if set(names) != {prefix + name for name in [*inventory, "bundle.json"]}:
        raise InstallError("Archive inventory is not closed")
    for name, checksum in inventory.items():
        if digest(source.read(prefix + name)) != checksum:
            raise InstallError(f"Archive member hash mismatch: {name}")
    return manifest


def verify_source(source: zipfile.ZipFile, prefix: str, manifest: dict) -> int:
    wheel_name = manifest["runtime_wheel"]
    wheel_bytes = source.read(prefix + wheel_name)
    if digest(wheel_bytes) != manifest["runtime"]["sha256"]:
        raise InstallError("Runtime wheel digest mismatch")
    for name, path in product_files(Path(wheel_name)).items():
        if name != wheel_name and source.read(prefix + name) != path.read_bytes():
            raise InstallError(f"Source/payload mismatch: {name}")
    site = "runtimes/python/" + (
        "Lib/site-packages/" if manifest["target"].startswith("win32-") else "lib/python3.13/site-packages/"
    )
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel:
        runtime_files = [name for name in wheel.namelist() if name.startswith("graph_skill_runtime/")]
        for name in runtime_files:
            if wheel.read(name) != source.read(prefix + site + name):
                raise InstallError(f"Installed runtime differs from wheel: {name}")
            if wheel.read(name) != (REPOSITORY / "src" / name).read_bytes():
                raise InstallError(f"Runtime wheel differs from source: {name}")
    return len(runtime_files)


def native_smoke(source: zipfile.ZipFile, prefix: str, manifest: dict) -> dict:
    if current_target() != manifest["target"]:
        raise InstallError("Native smoke requires the matching target host")
    with tempfile.TemporaryDirectory(prefix="graph-skill-accept-") as temporary:
        destination = Path(temporary)
        for item in source.infolist():
            output = destination / item.filename
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(source.read(item))
            if os.name != "nt":
                output.chmod(item.external_attr >> 16 & 0o777)
        payload = destination / prefix
        executables = manifest["runtimes"]["executables"]
        python = str(payload / executables["python"])
        node = str(payload / executables["node"])
        # These overrides belong only to this child process; host profiles are untouched.
        environment = {**os.environ, "HOME": str(destination / "home"),
                       "USERPROFILE": str(destination / "home"),
                       "LOCALAPPDATA": str(destination / "local"),
                       "APPDATA": str(destination / "roaming"),
                       "XDG_CACHE_HOME": str(destination / "cache"),
                       "XDG_CONFIG_HOME": str(destination / "config"),
                       "XDG_DATA_HOME": str(destination / "data")}
        commands = [
            [node, "--version"],
            [python, "-I", "-B", "-m", "graph_skill_runtime", "--version"],
            [python, "-I", "-B", "-c", "import cryptography, mcp, langgraph, pydantic_core, orjson"],
            [python, "-I", "-B", "-m", "graph_skill_runtime", "compile",
             str(REPOSITORY / "examples/hello-world")],
        ]
        results = []
        for command in commands:
            results.append(subprocess.check_output(
                command, cwd=destination, env=environment, text=True, encoding="utf-8"
            ).strip())
        def profile_snapshot() -> dict[str, bytes]:
            return {
                str(path.relative_to(destination)): path.read_bytes()
                for name in ("home", "local", "roaming", "config", "data")
                for path in (destination / name).rglob("*") if path.is_file()
            }

        before = profile_snapshot()
        discovery = json.loads(subprocess.check_output(
            [node, str(payload / "bin/graph-skill.mjs"), "detect"],
            cwd=destination, env=environment, text=True, encoding="utf-8"
        ))
        if discovery.get("schema") != "graph-skill.client-discovery.v1" or {
            client["target"] for client in discovery["clients"]
        } != {"codex", "claude"}:
            raise InstallError("Packaged client discovery did not return the required inventory")
        if profile_snapshot() != before:
            raise InstallError("Packaged discovery changed host or product files")
        return {"commands": len(commands) + 1, "output": results, "discovery": discovery}


def inspect(archive: Path, expected_source: str, native: bool) -> dict:
    identity = source_identity()
    if identity["source_commit"] != expected_source:
        raise InstallError("Inspection checkout does not match expected source")
    with zipfile.ZipFile(archive) as source:
        prefix = archive.stem + "/"
        manifest = verify_members(source, prefix, identity)
        count = verify_source(source, prefix, manifest)
        if not manifest["target"].startswith("win32-"):
            for name in ["install.sh", *manifest["runtimes"]["executables"].values()]:
                if not (source.getinfo(prefix + name).external_attr >> 16) & 0o111:
                    raise InstallError(f"Missing executable permissions: {name}")
        return {
            "source": identity, "target": manifest["target"], "files_verified": len(manifest["files"]),
            "runtime_files_verified": count, "sha256": digest(archive.read_bytes()),
            "size": archive.stat().st_size,
            "native_smoke": native_smoke(source, prefix, manifest) if native else "unverified",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    result = inspect(args.archive.resolve(strict=True), args.expected_source, args.native)
    output = ROOT / "release" / f"{args.archive.stem}-inspection.json"
    output.write_bytes(json_bytes(result))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
