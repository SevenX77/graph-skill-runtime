"""Compile-path RED tests for mvp1 LOGIC LE2 purity hard bans."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from graph_skill_runtime.core.error_registry import ERROR_REGISTRY, ErrorCodeMetadata
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader

PURITY_CODE = "[F-v3-logic-action-purity-violation]"


def _write_minimal_logic_skill(parent: Path, action_body: str) -> Path:
    root = parent / "purity-le2-test"
    (root / "phases" / "prepare" / "actions").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: purity-le2-test
description: Exercise compile-time logic action purity checks.
---
""",
        encoding="utf-8",
    )
    (root / "graph.yaml").write_text(
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise compile-time logic action purity checks.
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
        dedent(action_body).lstrip(),
        encoding="utf-8",
    )
    return root


def _compile(root: Path, mock_skill_resolver: object) -> None:
    SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)


def _assert_compile_purity_fatal(
    tmp_path: Path,
    mock_skill_resolver: object,
    action_body: str,
    *message_fragments: str,
) -> None:
    root = _write_minimal_logic_skill(tmp_path, action_body)

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    payload = exc_info.value.payload
    assert payload is not None
    assert payload.code == PURITY_CODE
    assert payload.source_path is not None
    assert payload.source_path.endswith("phases/prepare/actions/prepare.py")
    assert "prepare.py:" in payload.message
    for fragment in message_fragments:
        assert fragment.lower() in payload.message.lower()


@pytest.mark.parametrize(
    ("action_body", "message_fragments"),
    [
        (
            """
            from graph_skill_runtime import run_skill

            def prepare(inputs):
                run_skill("child.skill", workspace_dir="workspace")
                return {}
            """,
            ("run_skill",),
        ),
        (
            """
            def prepare(inputs):
                open("input.txt").read()
                return {}
            """,
            ("open", "file"),
        ),
        (
            """
            def prepare(inputs):
                open("out.txt", "w").write("bad")
                return {}
            """,
            ("open", "file"),
        ),
        (
            """
            import sys

            def prepare(inputs):
                sys.path.append("../outside")
                return {}
            """,
            ("sys.path",),
        ),
        (
            """
            import sys

            def prepare(inputs):
                sys.path = ["../outside"]
                return {}
            """,
            ("sys.path",),
        ),
        (
            """
            import sys

            def prepare(inputs):
                sys.path[0] = "../outside"
                return {}
            """,
            ("sys.path",),
        ),
        (
            """
            from pathlib import Path

            def prepare(inputs):
                Path("input.txt").exists()
                return {}
            """,
            ("exists", "file"),
        ),
        (
            """
            import glob

            def prepare(inputs):
                glob.glob("*.txt")
                return {}
            """,
            ("glob.glob", "file"),
        ),
        (
            """
            import importlib

            def prepare(inputs):
                runner = importlib.import_module("graph_skill_runtime.core.runner")
                runner.run_skill("child.skill", workspace_dir="workspace")
                return {}
            """,
            ("import",),
        ),
    ],
)
def test_le2_forbidden_action_code_fails_during_compile(
    tmp_path: Path,
    mock_skill_resolver: object,
    action_body: str,
    message_fragments: tuple[str, ...],
) -> None:
    _assert_compile_purity_fatal(
        tmp_path,
        mock_skill_resolver,
        action_body,
        *message_fragments,
    )


def test_pure_action_still_compiles_under_le2_purity(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    root = _write_minimal_logic_skill(
        tmp_path,
        """
        import json

        def prepare(inputs):
            payload = json.loads("{}")
            value = str(payload.get("value", "ok")).strip()
            return {}
        """,
    )

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    assert "prepare" in compiled.actions.for_phase("prepare")


def test_purity_violation_error_code_remains_compile_fatal() -> None:
    metadata = ERROR_REGISTRY[PURITY_CODE]

    assert isinstance(metadata, ErrorCodeMetadata)
    assert metadata.code == PURITY_CODE
    assert metadata.level == "FATAL"
    assert metadata.stage == ("编译期",)
