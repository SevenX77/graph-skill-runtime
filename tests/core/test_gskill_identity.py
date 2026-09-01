from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.gskill_version import (
    GSKILL_MAJOR,
    GSKILL_SCHEMA_VERSION,
    distribution_major,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _bundle(root: Path, *, marker: str | None) -> None:
    metadata = "" if marker is None else f"metadata:\n  gskill: {marker}\n"
    _write(
        root / "SKILL.md",
        f"---\nname: {root.name}\ndescription: gSkill identity fixture.\n{metadata}---\n",
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: {GSKILL_SCHEMA_VERSION}
graph_id: main
description: Identity fixture.
io:
  inputs: {{type: object, properties: {{}}}}
  outputs: {{type: object, properties: {{}}}}
phases:
  - id: done
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "done" / "LOGIC.md",
        """---
name: done
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
actions: [done]
---
<action>done</action>
""",
    )
    _write(root / "phases" / "done" / "actions" / "done.py", "def done(inputs):\n    return {}\n")


@pytest.mark.parametrize("marker", [None, "gskill.graph.v2", "ordinary-skill"])
def test_compile_rejects_a_root_without_the_runtime_gskill_identity(
    tmp_path: Path,
    marker: str | None,
) -> None:
    root = tmp_path / "identity-fixture"
    _bundle(root, marker=marker)

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    payload = exc_info.value.payload
    assert payload is not None
    assert payload.code == "[F-v3-skill-metadata-invalid]"
    assert GSKILL_SCHEMA_VERSION in payload.message


def test_compile_accepts_the_exact_runtime_gskill_identity(tmp_path: Path) -> None:
    root = tmp_path / "identity-fixture"
    _bundle(root, marker=GSKILL_SCHEMA_VERSION)

    compiled = compile_skill(root, cache=False)

    assert compiled.skill_manifest is not None
    assert compiled.skill_manifest.metadata["gskill"] == GSKILL_SCHEMA_VERSION


def test_distribution_major_equals_the_only_supported_gskill_syntax_major() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert distribution_major(pyproject["project"]["version"]) == GSKILL_MAJOR
