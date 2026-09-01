"""Portable graph schema-version boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader


def _write_skill(parent: Path, schema_version_literal: str) -> Path:
    root = parent / "schema-version-skill"
    (root / "phases" / "hello" / "actions").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: schema-version-skill\ndescription: Schema version fixture.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
        encoding="utf-8",
    )
    (root / "graph.yaml").write_text(
        f"""schema_version: {schema_version_literal}
graph_id: root
description: Schema version graph.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
phases:
  - id: hello
    depends_on: [input]
    output: true
""",
        encoding="utf-8",
    )
    (root / "phases" / "hello" / "LOGIC.md").write_text(
        """---
name: hello
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}
---
<action>hello</action>
""",
        encoding="utf-8",
    )
    (root / "phases" / "hello" / "actions" / "hello.py").write_text(
        "def hello(inputs):\n    return {}\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize("literal", ["gskill.graph.v1", '"gskill.graph.v1"'])
def test_exact_portable_version_accepts_quoted_or_plain_yaml(
    tmp_path: Path,
    literal: str,
) -> None:
    root = _write_skill(tmp_path, literal)

    compiled = compile_skill(root, cache=False)

    assert compiled.manifest.schema_version == "gskill.graph.v1"


@pytest.mark.parametrize("literal", ["v0.3.0", "1.5"])
def test_every_non_v1_version_fails_with_the_version_code(
    tmp_path: Path,
    literal: str,
) -> None:
    root = _write_skill(tmp_path, literal)

    with pytest.raises(SkillLoadError) as exc_info:
        SkillLoader().compile_skill(root)
    assert exc_info.value.payload.code == "[F-v3-graph-schema-version-mismatch]"
