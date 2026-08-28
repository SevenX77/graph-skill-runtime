#!/usr/bin/env python
"""Fail when a release wheel leaks the retired package or non-runtime examples."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

REQUIRED_MEMBERS = {
    "graph_skill_runtime/__init__.py",
    "graph_skill_runtime/migration/atomic_publish.py",
    "graph_skill_runtime/migration/studio_v030.py",
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
MOIRAI_PREFIX = "graph_skill_runtime/integrations/assets/moirai/"
MOIRAI_MANIFEST = MOIRAI_PREFIX + "integration.json"


def _manifest_string_items(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(
            f"MoirAI integration manifest field {field!r} must be a non-empty string list"
        )
    return tuple(value)


def _moirai_members(archive: zipfile.ZipFile) -> set[str]:
    try:
        raw = archive.read(MOIRAI_MANIFEST)
        manifest = json.loads(raw.decode("utf-8"))
    except KeyError as exc:
        raise ValueError(f"wheel is missing the MoirAI integration manifest: {MOIRAI_MANIFEST}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"wheel contains an invalid MoirAI integration manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("wheel MoirAI integration manifest must contain an object")
    try:
        roles = manifest["roles"]
        skills = manifest["skills"]
        knowledge = _manifest_string_items(manifest["knowledge"], field="knowledge")
    except KeyError as exc:
        raise ValueError(f"wheel MoirAI integration manifest is missing field {exc.args[0]!r}") from exc
    if not isinstance(roles, list) or not isinstance(skills, list):
        raise ValueError("wheel MoirAI integration roles and skills must be lists")
    try:
        role_ids = tuple(item["id"] for item in roles if isinstance(item, dict))
        skill_ids = tuple(item["id"] for item in skills if isinstance(item, dict))
    except KeyError as exc:
        raise ValueError(f"wheel MoirAI integration entry is missing field {exc.args[0]!r}") from exc
    if len(role_ids) != len(roles) or not all(isinstance(item, str) and item for item in role_ids):
        raise ValueError("wheel MoirAI integration roles must contain non-empty string ids")
    if len(skill_ids) != len(skills) or not all(isinstance(item, str) and item for item in skill_ids):
        raise ValueError("wheel MoirAI integration skills must contain non-empty string ids")
    return {
        MOIRAI_MANIFEST,
        *(MOIRAI_PREFIX + f"roles/{role_id}.md" for role_id in role_ids),
        *(MOIRAI_PREFIX + f"skills/{skill_id}/SKILL.md" for skill_id in skill_ids),
        *(MOIRAI_PREFIX + f"knowledge/{filename}" for filename in knowledge),
    }


def validate_wheel(path: Path) -> None:
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError(f"expected one wheel path, got {path}")
    with zipfile.ZipFile(path) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        expected_moirai = _moirai_members(archive)

    missing = sorted((REQUIRED_MEMBERS | expected_moirai) - names)
    forbidden = sorted(FORBIDDEN_MEMBERS & names)
    forbidden.extend(
        sorted(name for name in names if name.startswith(FORBIDDEN_PREFIXES))
    )
    forbidden.extend(
        sorted(
            name
            for name in names
            if name.startswith(MOIRAI_PREFIX) and name not in expected_moirai
        )
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
