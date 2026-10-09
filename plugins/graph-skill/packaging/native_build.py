"""Build-only Intel macOS cryptography support with private static OpenSSL."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

from ownership import InstallError, digest
from runtime_layout import current_target


def require_native_target(target_name: str, recipe: dict) -> None:
    if target_name != "darwin-x64" or recipe["package"] != "cryptography":
        raise InstallError("Native dependency compilation is defined only for Intel macOS cryptography")
    if current_target() != target_name:
        raise InstallError("Build the Intel Mac archive on an Intel macOS build host")


def prepare(source: Path, stage: Path, repository: Path, recipe: dict) -> tuple[dict, dict]:
    """Compile verified OpenSSL source outside the deliverable and record inputs."""
    require_native_target("darwin-x64", recipe)
    prefix = source.parent / "openssl-install"
    environment = {
        **os.environ,
        "MACOSX_DEPLOYMENT_TARGET": recipe["deployment_target"],
        "OPENSSL_STATIC": "1",
        "OPENSSL_DIR": str(prefix),
    }
    commands = [
        ["perl", "Configure", "darwin64-x86_64-cc", "no-shared", "no-tests",
         f"--prefix={prefix}", f"-mmacosx-version-min={recipe['deployment_target']}"],
        ["make", f"-j{os.cpu_count() or 2}"],
        ["make", "install_sw"],
    ]
    log = repository / "plugins/graph-skill/release/native-build.log"
    with log.open("w", encoding="utf-8") as output:
        for command in commands:
            print(f"Native dependency build: {command[0]}", flush=True)
            subprocess.run(command, cwd=source, env=environment, check=True,
                           stdout=output, stderr=subprocess.STDOUT)
    packages = tomllib.loads((repository / "uv.lock").read_text(encoding="utf-8"))["package"]
    package = next(item for item in packages if item["name"] == recipe["package"])
    provenance = {
        "package": package["name"],
        "version": package["version"],
        "sdist": package["sdist"],
        "openssl": recipe["openssl"],
        "deployment_target": recipe["deployment_target"],
        "static_libraries": {
            name: digest((prefix / "lib" / name).read_bytes())
            for name in ("libssl.a", "libcrypto.a")
        },
        "compiler": subprocess.check_output(["clang", "--version"], text=True).strip(),
        "rust": subprocess.check_output(["rustc", "--version"], text=True).strip(),
    }
    shutil.copyfile(source / "LICENSE.txt", stage / "runtime/OPENSSL_LICENSE.txt")
    return environment, provenance


def inspect_extension(site: Path, python: Path, expected: dict) -> dict:
    """Reject architecture or linkage leaks before a release archive is written."""
    extensions = list((site / "cryptography/hazmat/bindings").glob("_rust*.so"))
    if len(extensions) != 1:
        raise InstallError("Expected one native cryptography extension")
    extension = extensions[0]
    subprocess.run(["lipo", str(extension), "-verify_arch", "x86_64"], check=True)
    linked = subprocess.check_output(["otool", "-L", str(extension)], text=True)
    dependencies = [line.strip().split(" (", 1)[0] for line in linked.splitlines()[1:]]
    if any(not name.startswith(("/usr/lib/", "/System/Library/")) for name in dependencies):
        raise InstallError(f"Native dependency requires a build-machine library: {dependencies}")
    code = (
        "import json, cryptography; from cryptography.hazmat.backends.openssl.backend import backend; "
        "from cryptography.fernet import Fernet; key=Fernet.generate_key(); f=Fernet(key); "
        "assert f.decrypt(f.encrypt(b'graph-skill')) == b'graph-skill'; "
        "print(json.dumps({'version':cryptography.__version__, 'openssl':backend.openssl_version_text()}))"
    )
    result = json.loads(subprocess.check_output([str(python), "-I", "-B", "-c", code], text=True))
    if result["version"] != expected["version"] or not result["openssl"].startswith(
        f"OpenSSL {expected['openssl']['version']} "
    ):
        raise InstallError(f"Unexpected native dependency versions: {result}")
    return {"extension_sha256": digest(extension.read_bytes()), "linked_libraries": dependencies, **result}
