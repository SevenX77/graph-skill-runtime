"""Portable tool/action path containment tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader


def _write_minimal_graph(parent: Path, action_body: str) -> Path:
    root = parent / "action-path-test"
    (root / "phases" / "prepare" / "actions").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: action-path-test
description: Exercise action path containment.
---
""",
        encoding="utf-8",
    )
    (root / "graph.yaml").write_text(
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise action path containment.
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}
phases:
  - id: prepare
    depends_on: [input]
    output: true
""",
        encoding="utf-8",
    )
    (root / "phases" / "prepare" / "LOGIC.md").write_text(
        """---
name: prepare
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}
---
<action>prepare</action>
""",
        encoding="utf-8",
    )
    (root / "phases" / "prepare" / "actions" / "prepare.py").write_text(
        action_body,
        encoding="utf-8",
    )
    return root


def test_in_tree_action_reference_still_loads(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = _write_minimal_graph(tmp_path, "def prepare(inputs):\n    return {}\n")

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    assert "prepare" in compiled.actions.for_phase("prepare")


def test_action_local_write_fatals_as_purity_violation(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = _write_minimal_graph(
        tmp_path,
        "def prepare(inputs):\n    open('out.txt', 'w').write('bad')\n    return {}\n",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)
    assert exc_info.value.payload.code == "[F-v3-logic-action-purity-violation]"


def test_graph_level_actions_directory_is_rejected(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _write_minimal_graph(tmp_path, "def prepare(inputs):\n    return {}\n")
    (root / "actions").mkdir()

    with pytest.raises(SkillLoadError, match="graph-level actions/ is not allowed"):
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)
