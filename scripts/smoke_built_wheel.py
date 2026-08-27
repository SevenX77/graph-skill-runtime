#!/usr/bin/env python
"""Fail when a release wheel leaks the retired package or non-runtime examples."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REQUIRED_MEMBERS = {
    "graph_skill_runtime/__init__.py",
    "graph_skill_runtime/py.typed",
    "graph_skill_runtime/skills/builtin/md-patch/SKILL.md",
}
FORBIDDEN_MEMBERS = {
    "graph_skill_runtime/CHANGELOG.md",
    "graph_skill_runtime/requirements.txt",
}
FORBIDDEN_PREFIXES = (
    "graph_agent/",
    "graph_skill_runtime/examples/",
)


def validate_wheel(path: Path) -> None:
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError(f"expected one wheel path, got {path}")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())

    missing = sorted(REQUIRED_MEMBERS - names)
    forbidden = sorted(FORBIDDEN_MEMBERS & names)
    forbidden.extend(
        sorted(name for name in names if name.startswith(FORBIDDEN_PREFIXES))
    )
    if missing or forbidden:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if forbidden:
            details.append("forbidden: " + ", ".join(forbidden[:10]))
        raise ValueError("invalid wheel contents; " + "; ".join(details))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: smoke_built_wheel.py <wheel>", file=sys.stderr)
        return 2
    try:
        validate_wheel(Path(argv[0]))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
