"""Installed private-interpreter layout shared by packaging and lifecycle adapters."""

from __future__ import annotations

import platform
import sys
import sysconfig
from pathlib import Path

from ownership import InstallError


def current_target() -> str:
    # A macOS universal2 Python contains both slices; its build tag cannot
    # identify the architecture of the process that is running the installer.
    architecture = platform.machine().lower() if sys.platform == "darwin" else sysconfig.get_platform().lower()
    if architecture.endswith(("arm64", "aarch64")):
        arch = "arm64"
    elif architecture.endswith(("x86_64", "amd64")):
        arch = "x64"
    else:
        raise InstallError(f"Unsupported interpreter architecture: {architecture}")
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
