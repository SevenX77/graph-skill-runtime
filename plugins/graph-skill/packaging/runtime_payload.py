"""Build-time assembly of checksum-pinned, relocatable native runtimes."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import posixpath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from ownership import InstallError, digest, json_bytes, plain_path
from runtime_layout import executable_paths

LOCK = Path(__file__).with_name("runtime-lock.json")


def fetch(asset: dict, cache: Path) -> Path:
    """Reuse only bytes matching the pinned upstream digest."""
    suffix = ".zip" if asset["url"].endswith(".zip") else ".tar.gz"
    destination = cache / (asset["sha256"] + suffix)
    plain_path(destination)
    if destination.exists():
        if digest(destination.read_bytes()) != asset["sha256"]:
            raise InstallError(f"Runtime download cache changed: {destination}")
        return destination
    cache.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="download-", suffix=".part", dir=cache)
    os.close(descriptor)
    temporary = Path(temporary_name)
    print(f"Downloading {asset['url']}", flush=True)
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "graph-skill-builder"})
    try:
        checksum = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                checksum.update(chunk)
                output.write(chunk)
        if checksum.hexdigest() != asset["sha256"]:
            raise InstallError(f"Upstream checksum mismatch: {asset['url']}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def relative_member(name: str, prefix: str) -> str:
    path = PurePosixPath(name)
    if "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts:
        raise InstallError(f"Unsafe upstream archive member: {name}")
    if not path.parts or path.parts[0] != prefix:
        raise InstallError(f"Unexpected upstream archive root: {name}")
    return PurePosixPath(*path.parts[1:]).as_posix() if len(path.parts) > 1 else ""


def linked_file(name: str, members: dict, prefix: str, seen: frozenset = frozenset()) -> tarfile.TarInfo:
    if name in seen or name not in members:
        raise InstallError(f"Cyclic or absent upstream link: {name}")
    item = members[name]
    if item.isfile():
        return item
    if not (item.issym() or item.islnk()):
        raise InstallError(f"Upstream link is not a regular file: {name}")
    if item.linkname.startswith("/") or "\\" in item.linkname or ":" in item.linkname:
        raise InstallError(f"Unsafe upstream link: {name}")
    target = posixpath.normpath(
        posixpath.join(posixpath.dirname(name), item.linkname) if item.issym() else item.linkname
    )
    relative_member(target, prefix)
    return linked_file(target, members, prefix, seen | {name})


def staging_path(destination: Path, name: str, blobs: Path) -> Path:
    output = destination / name
    # Preserve distinct Linux names such as 2621A and 2621a on a Windows
    # build machine without changing either final archive name or contents.
    if output.exists():
        output = blobs / digest((str(destination) + name).encode("utf-8"))
    plain_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def extract_tar(
    archive: Path, destination: Path, prefix: str, blobs: Path, selected: set[str] | None = None
) -> dict[str, Path]:
    with tarfile.open(archive, "r:gz") as source:
        entries = source.getmembers()
        members = {item.name: item for item in entries}
        if len(members) != len(entries):
            raise InstallError("Duplicate upstream archive member")
        wanted = {}
        for item in entries:
            name = relative_member(item.name, prefix)
            if name and not item.isdir() and (selected is None or name in selected):
                wanted[item.name] = name
        canonical = {name: linked_file(name, members, prefix) for name in wanted}
        originals = {item.name: item for item in canonical.values()}
        materialized = materialize_files(source, originals, destination, prefix, blobs)
        records = {}
        for name, relative in wanted.items():
            original = canonical[name]
            if name == original.name:
                records[relative] = materialized[name]
            else:
                output = staging_path(destination, relative, blobs)
                shutil.copyfile(materialized[original.name], output)
                output.chmod(0o755 if original.mode & 0o111 else 0o644)
                records[relative] = output
        return records


def materialize_files(source: tarfile.TarFile, originals: dict, destination: Path, prefix: str, blobs: Path) -> dict:
    result = {}
    # Forward-order reads avoid repeatedly decompressing the full tarball for
    # thousands of terminal-database aliases. Links copy these owned files.
    for item in sorted(originals.values(), key=lambda item: item.offset_data):
        output = staging_path(destination, relative_member(item.name, prefix), blobs)
        stream = source.extractfile(item)
        if stream is None:
            raise InstallError(f"Unreadable upstream archive member: {item.name}")
        with stream, output.open("xb") as writer:
            shutil.copyfileobj(stream, writer)
        output.chmod(0o755 if item.mode & 0o111 else 0o644)
        result[item.name] = output
    return result


def extract_node(archive: Path, destination: Path, target: str, version: str, blobs: Path) -> dict[str, Path]:
    prefix = f"node-v{version}-{target.replace('win32', 'win')}"
    if not target.startswith("win32-"):
        return extract_tar(archive, destination, prefix, blobs, {"bin/node", "LICENSE", "README.md"})
    records = {}
    with zipfile.ZipFile(archive) as source:
        for name in ("node.exe", "LICENSE", "README.md"):
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(source.read(f"{prefix}/{name}"))
            records[name] = output
    return records


def run_build(argv: list[str], repository: Path) -> None:
    environment = {**os.environ, "UV_COMPILE_BYTECODE": "false", "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(argv, cwd=repository, env=environment, check=True, stdout=subprocess.DEVNULL)


def install_dependencies(stage: Path, repository: Path, target: dict, version: str, wheel: Path) -> tuple[dict, set]:
    """uv is a builder prerequisite; it is never invoked by the user installer."""
    uv = shutil.which("uv")
    if uv is None:
        raise InstallError("Building complete archives requires uv on the build machine")
    requirements = stage / "runtime/requirements.txt"
    run_build(
        [
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--no-default-groups",
            "--no-emit-project",
            "--no-header",
            "--output-file",
            str(requirements),
        ],
        repository,
    )
    windows = "windows" in target["python_platform"]
    suffix = "Lib/site-packages" if windows else f"lib/python{'.'.join(version.split('.')[:2])}/site-packages"
    site = stage / "runtimes/python" / suffix
    common = [
        uv,
        "pip",
        "install",
        "--target",
        str(site),
        "--python-version",
        version,
        "--python-platform",
        target["python_platform"],
        "--only-binary",
        ":all:",
        "--require-hashes",
        "--no-config",
        "--link-mode",
        "copy",
    ]
    wheel_input = stage / "runtime/local-wheel.txt"
    wheel_input.write_text(f"{wheel.as_uri()} --hash=sha256:{digest(wheel.read_bytes())}\n", encoding="utf-8")
    try:
        # Resolve the wheel's declared requirements against the complete hash-
        # pinned export. A stale/incompatible supplied wheel must fail here,
        # rather than silently producing an incomplete offline environment.
        run_build([*common, "-r", str(requirements), "-r", str(wheel_input)], repository)
    finally:
        wheel_input.unlink()
    # Entry points always use python -m. Remove build-machine script paths and
    # local-wheel URLs rather than carrying non-relocatable launchers in a release.
    removed = clean_build_metadata(site, stage)
    return {
        "requirements_sha256": digest(requirements.read_bytes()),
        "uv_lock_sha256": digest((repository / "uv.lock").read_bytes()),
    }, removed


def clean_build_metadata(site: Path, stage: Path) -> set[Path]:
    removed = set()
    scripts = site / "bin"
    if scripts.exists():
        plain_path(scripts)
        if not scripts.resolve().is_relative_to(stage.resolve()):
            raise InstallError("Generated script directory escaped staging")
        removed.update(path for path in scripts.rglob("*") if path.is_file())
        shutil.rmtree(scripts)
    for path in site.glob("*.dist-info/direct_url.json"):
        removed.add(path)
        path.unlink()
    for record in site.glob("*.dist-info/RECORD"):
        with record.open(encoding="utf-8", newline="") as source:
            rows = [row for row in csv.reader(source) if site / row[0] not in removed]
        with record.open("w", encoding="utf-8", newline="") as output:
            csv.writer(output).writerows(rows)
    return removed


def assemble(stage: Path, repository: Path, target_name: str, wheel: Path, cache: Path) -> tuple[dict, dict]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    target = lock["targets"][target_name]
    node = fetch(target["node"], cache)
    python = fetch(target["python"], cache)
    blobs = stage.parent / "archive-members"
    node_files = extract_node(node, stage / "runtimes/node", target_name, lock["node_version"], blobs)
    python_files = extract_tar(python, stage / "runtimes/python", "python", blobs)
    members = {"runtimes/node/" + name: path for name, path in node_files.items()}
    members.update({"runtimes/python/" + name: path for name, path in python_files.items()})
    (stage / "runtime").mkdir(exist_ok=True)
    dependencies, removed = install_dependencies(stage, repository, target, lock["python_version"], wheel)
    members = {name: path for name, path in members.items() if path not in removed}
    executables = executable_paths(target_name)
    for name in executables.values():
        if not (stage / name).is_file():
            raise InstallError(f"Missing packaged executable: {name}")
    result = {
        "target": target_name,
        "node_version": lock["node_version"],
        "python_version": lock["python_version"],
        "executables": executables,
        "upstream": target,
        "lock_sha256": digest(LOCK.read_bytes()),
        **dependencies,
    }
    (stage / "runtime/provenance.json").write_bytes(json_bytes(result))
    return result, members
