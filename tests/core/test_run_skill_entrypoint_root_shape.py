"""Red tests for public run_skill entrypoint root-shape failures."""

from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.core.runner import resume_skill, run_skill


def _write_valid_portable_skill(skill_root: Path) -> None:
    phase_dir = skill_root / "phases" / "main"
    phase_dir.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: portable-skill\ndescription: Use this test skill to verify strict root addressing.\n---\n",
        encoding="utf-8",
    )
    (skill_root / "graph.yaml").write_text(
        """schema_version: gskill.graph.v1
graph_id: main
description: Strict root addressing fixture.
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
phases:
  - id: main
    depends_on: [input]
    output: true
""",
        encoding="utf-8",
    )
    (phase_dir / "LOGIC.md").write_text(
        """---
name: main
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
actions: [main]
validator: false
---
<action>main</action>
""",
        encoding="utf-8",
    )
    actions_dir = phase_dir / "actions"
    actions_dir.mkdir()
    (actions_dir / "main.py").write_text("def main(inputs):\n    return {}\n", encoding="utf-8")


def test_run_skill_single_markdown_file_returns_portable_root_error(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_file = tmp_path / "ordinary.md"
    skill_file.write_text("# ordinary markdown\n", encoding="utf-8")

    result = run_skill(
        skill_file,
        workspace_dir=tmp_path / "workspace",
        skill_resolver=mock_skill_resolver,
    )

    assert result.success is False
    assert result.context == {}
    assert result.error is not None
    assert result.error.code == "[F-v3-graph-root-missing]"


def test_run_skill_single_skill_md_file_without_graph_returns_portable_root_error(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(
        """---
name: legacy
description: Missing its required portable graph declaration.
metadata:
  gskill: gskill.graph.v1
---
""",
        encoding="utf-8",
    )

    result = run_skill(
        skill_file,
        workspace_dir=tmp_path / "workspace",
        skill_resolver=mock_skill_resolver,
    )

    assert result.success is False
    assert result.context == {}
    assert result.error is not None
    assert result.error.code == "[F-v3-graph-root-missing]"


def test_run_skill_rejects_a_valid_bundle_skill_file_instead_of_inferring_its_parent(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = tmp_path / "portable-skill"
    _write_valid_portable_skill(skill_root)

    result = run_skill(
        skill_root / "SKILL.md",
        workspace_dir=tmp_path / "workspace",
        skill_resolver=mock_skill_resolver,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "[F-v3-graph-root-missing]"


def test_resume_skill_rejects_a_valid_bundle_skill_file_instead_of_inferring_its_parent(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = tmp_path / "portable-skill"
    _write_valid_portable_skill(skill_root)

    result = resume_skill(
        skill_root / "SKILL.md",
        workspace_dir=tmp_path / "workspace",
        run_id="strict-root-resume",
        checkpointer=object(),
        skill_resolver=mock_skill_resolver,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "[F-v3-graph-root-missing]"
