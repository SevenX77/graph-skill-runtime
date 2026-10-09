"""Installed private-interpreter layout shared by packaging and lifecycle adapters."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

from ownership import InstallError


def current_target() -> str:
    platform = sysconfig.get_platform().lower()
    if platform.endswith(("arm64", "aarch64")):
        arch = "arm64"
    elif platform.endswith(("x86_64", "amd64")):
        arch = "x64"
    else:
        raise InstallError(f"Unsupported interpreter architecture: {platform}")
    if sys.platform not in {"win32", "darwin", "linux"}:
        raise InstallError(f"Unsupported platform: {sys.platform}")
    return f"{sys.platform}-{arch}"


def executable_paths(target: str) -> dict[str, str]:
    windows = target.startswith("win32-")
    return {
        "node": "runtimes/node/" + ("node.exe" if windows else "bin/node"),
        "python": "runtimes/python/" + ("python.exe" if windows else "bin/python3"),
    }


def runtime_python(root: Path) -> Path:
    return root / executable_paths(current_target())["python"]


def runtime_node(root: Path) -> Path:
    return root / executable_paths(current_target())["node"]
