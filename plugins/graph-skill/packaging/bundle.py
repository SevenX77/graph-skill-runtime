"""Build the user-installable toolkit archive from explicit, already built inputs."""

from __future__ import annotations

import argparse
import email
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from ownership import InstallError, digest, json_bytes, plain_path
from runtime_layout import current_target
from runtime_payload import LOCK, assemble

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = ROOT.parent.parent


def source_identity() -> dict:
    """Bind a release to a committed source tree before packaging any bytes."""
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=REPOSITORY, text=True, encoding="utf-8"
        ).strip()

    if git("status", "--porcelain", "--untracked-files=normal"):
        raise InstallError("Commit source changes before building a release archive")
    return {"source_commit": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}")}


def wheel_metadata(path: Path) -> dict:
    with zipfile.ZipFile(path) as wheel:
        members = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(members) != 1:
            raise InstallError("Expected one wheel metadata record")
        metadata = email.message_from_bytes(wheel.read(members[0]))
        if metadata["Name"] != "graph-skill-runtime":
            raise InstallError("The supplied wheel is not graph-skill-runtime")
        if any(name.startswith(("plugins/", "graph_skill_runtime/examples/")) for name in wheel.namelist()):
            raise InstallError("Runtime wheel contains UI or business example assets")
        return {"name": metadata["Name"], "version": metadata["Version"], "sha256": digest(path.read_bytes())}


def notices() -> bytes:
    # Preserve licensing for installed JavaScript dependencies, including the
    # build tool. This intentionally includes a superset of bundled libraries.
    blocks = ["JavaScript dependency notices\nBundled from the dependencies resolved by package-lock.json.\n"]
    modules = ROOT / "node_modules"
    packages = []
    for child in sorted(modules.iterdir()):
        if child.name.startswith("@") and child.is_dir():
            packages.extend(sorted(child.iterdir()))
        elif child.is_dir() and not child.name.startswith("."):
            packages.append(child)
    for directory in packages:
        if not (directory / "package.json").is_file():
            continue
        metadata = json.loads((directory / "package.json").read_text(encoding="utf-8"))
        blocks.append(
            f"\n--- {metadata.get('name')} {metadata.get('version')} ---\n"
            f"Declared license: {metadata.get('license', 'see package')}\n"
        )
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name.lower().startswith(("license", "licence", "notice", "copying")):
                blocks.append(path.read_text(encoding="utf-8", errors="replace"))
    return ("\n".join(blocks) + "\n").encode("utf-8")


def product_files(wheel: Path) -> dict[str, Path]:
    files = {
        "package.json": ROOT / "package.json",
        "README.md": ROOT / "README.md",
        "VALIDATION.md": ROOT / "VALIDATION.md",
        "install.cmd": ROOT / "install.cmd",
        "install.sh": ROOT / "install.sh",
        "bin/graph-skill.mjs": ROOT / "bin/graph-skill.mjs",
        "references/portable-gskill.md": REPOSITORY / "docs/skill-spec/01-PORTABLE-GSKILL-V1.md",
        "LICENSE": REPOSITORY / "LICENSE",
        "runtime/" + wheel.name: wheel,
    }
    for name in ("entry.py", "install.py", "hosts.py", "ownership.py", "runtime_layout.py", "runtime-lock.json"):
        files["packaging/" + name] = ROOT / "packaging" / name
    for name in ("server.mjs", "after-tool.mjs", "canvas.html"):
        files["dist/" + name] = ROOT / "dist" / name
    for skill in ("graph-skill", "graph-skill-canvas"):
        for path in sorted((ROOT / "skills" / skill).rglob("*.md")):
            files[path.relative_to(ROOT).as_posix()] = path
        if f"skills/{skill}/SKILL.md" not in files:
            raise InstallError(f"Missing Skill: {skill}")
    return files


def write_archive(members: dict[str, Path], destination: Path, prefix: str) -> int:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, path in sorted(members.items()):
            member = zipfile.ZipInfo(f"{prefix}/{name}")
            member.create_system = 3
            member.compress_type = zipfile.ZIP_DEFLATED
            executable = name == "install.sh" or name.startswith(("runtimes/node/bin/", "runtimes/python/bin/"))
            mode = 0o100755 if executable else 0o100644
            member.external_attr = mode << 16
            with path.open("rb") as source, target.open(member, "w", force_zip64=True) as output:
                shutil.copyfileobj(source, output)
    return len(members)


def build(wheel: Path, platform: str) -> dict:
    source_binding = source_identity()
    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise InstallError("Toolkit version must have three numeric components")
    plain_path(wheel)
    runtime = wheel_metadata(wheel)
    output = ROOT / "release"
    plain_path(output)
    output.mkdir(exist_ok=True)
    name = f"graph-skill-{version}-{platform}"
    archive = output / f"{name}.zip"
    plain_path(archive)
    with tempfile.TemporaryDirectory(prefix="bundle-", dir=output) as temporary:
        work = Path(temporary)
        stage = work / "payload"
        stage.mkdir()
        for member, source in product_files(wheel).items():
            plain_path(source)
            dest = stage / member
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        (stage / "THIRD_PARTY_NOTICES.txt").write_bytes(notices())
        runtimes, native_members = assemble(stage, REPOSITORY, platform, wheel, output / "download-cache")
        staged_native = set(native_members.values())
        members = {
            path.relative_to(stage).as_posix(): path
            for path in stage.rglob("*")
            if path.is_file() and path not in staged_native
        }
        members.update(native_members)
        inventory = {name: digest(path.read_bytes()) for name, path in sorted(members.items())}
        manifest = {
            "schema": "graph-skill.toolkit-bundle.v2",
            "version": version,
            "target": platform,
            "runtime_wheel": "runtime/" + wheel.name,
            "runtime": runtime,
            "runtimes": runtimes,
            "source_status": "assembled from a clean committed source checkout",
            **source_binding,
            "files": inventory,
        }
        (stage / "bundle.json").write_bytes(json_bytes(manifest))
        members["bundle.json"] = stage / "bundle.json"
        staged_archive = work / archive.name
        count = write_archive(members, staged_archive, name)
        if source_identity() != source_binding:
            raise InstallError("Source identity changed during archive assembly")
        shutil.copyfile(staged_archive, archive)
    result = {
        "archive": str(archive),
        "sha256": digest(archive.read_bytes()),
        "size": archive.stat().st_size,
        "files": count,
        "runtime": runtime,
        "runtimes": runtimes,
        **source_binding,
    }
    receipt = output / f"{name}.json"
    plain_path(receipt)
    receipt.write_bytes(json_bytes(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-wheel", required=True, type=Path)
    parser.add_argument(
        "--platform", choices=tuple(json.loads(LOCK.read_text(encoding="utf-8"))["targets"])
    )
    args = parser.parse_args()
    print(json.dumps(build(args.runtime_wheel.resolve(strict=True), args.platform or current_target()), indent=2))


if __name__ == "__main__":
    main()
