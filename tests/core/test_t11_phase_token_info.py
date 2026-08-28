from __future__ import annotations

from pathlib import Path

import yaml

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.loader import get_phase_token_info


def _write_portable_phase_token_skill(parent: Path) -> Path:
    root = parent / "phase-token-smoke"
    (root / "phases" / "prepare" / "actions").mkdir(parents=True)
    (root / "phases" / "branch_a" / "actions").mkdir(parents=True)
    (root / "phases" / "branch_b" / "actions").mkdir(parents=True)
    (root / "phases" / "assemble" / "actions").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: phase-token-smoke
description: Exercise portable graph phase source tokens.
---
""",
        encoding="utf-8",
    )
    (root / "graph.yaml").write_text(
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise portable graph phase source tokens.
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
    output: false
  - id: branch_a
    depends_on: [prepare]
    output: false
  - id: branch_b
    depends_on: [prepare]
    output: false
  - id: assemble
    depends_on: [branch_a, branch_b]
    output: true
""",
        encoding="utf-8",
    )
    for phase_id in ("prepare", "branch_a", "branch_b", "assemble"):
        (root / "phases" / phase_id / "LOGIC.md").write_text(
            f"""---
name: {phase_id}
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
---
<action>{phase_id}</action>
""",
            encoding="utf-8",
        )
        (root / "phases" / phase_id / "actions" / f"{phase_id}.py").write_text(
            f"def {phase_id}(inputs):\n    return {{}}\n",
            encoding="utf-8",
        )
    return root


def test_portable_phase_token_info_has_yaml_and_source_line(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = _write_portable_phase_token_skill(tmp_path)
    graph_lines = (skill_root / "graph.yaml").read_text(encoding="utf-8").splitlines()
    compiled = compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)

    info = get_phase_token_info(compiled, "prepare")

    assert info is not None
    assert yaml.safe_load(info.raw_text) == {
        "id": "prepare",
        "depends_on": ["input"],
        "output": False,
    }
    expected_line = next(
        index for index, line in enumerate(graph_lines, start=1) if line.strip() == "- id: prepare"
    )
    assert info.line_start == info.line_end == expected_line
    assert info.attrs == {"depends_on": "input", "output": "false"}


def test_portable_phase_tokens_expose_typed_topology_attributes(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = _write_portable_phase_token_skill(tmp_path)
    compiled = compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)

    for phase_id in ("prepare", "branch_a", "branch_b", "assemble"):
        info = get_phase_token_info(compiled, phase_id)
        assert info is not None
        assert yaml.safe_load(info.raw_text)["id"] == phase_id
        assert set(info.attrs) == {"depends_on", "output"}

    assemble = get_phase_token_info(compiled, "assemble")
    assert assemble is not None
    assert assemble.attrs["depends_on"] == "branch_a,branch_b"
    assert assemble.attrs["output"] == "true"


def test_missing_phase_token_info_returns_none(tmp_path: Path, mock_skill_resolver: object) -> None:
    skill_root = _write_portable_phase_token_skill(tmp_path)
    compiled = compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)

    assert get_phase_token_info(compiled, "missing") is None
