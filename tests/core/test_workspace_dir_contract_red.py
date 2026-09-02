from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from graph_skill_runtime.core import runner as engine_runner
from graph_skill_runtime.core.runner import run_skill


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_logic_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Workspace-dir contract fixture with one deterministic LOGIC phase.
---
Compile and run this graph skill with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: workspace-dir-contract
description: Workspace-dir contract fixture with one deterministic LOGIC phase.
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
    required: [topic]
  outputs:
    type: object
    properties:
      answer:
        type: string
phases:
  - id: draft
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "draft" / "LOGIC.md",
        """---
name: draft
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
---
<action>draft</action>
""",
    )
    _write(
        root / "phases" / "draft" / "actions" / "draft.py",
        "def draft(inputs):\n"
        "    topic = inputs.get('topic', 'missing')\n"
        "    return {'answer': f'draft:{topic}'}\n",
    )


def _engine_callable(name: str) -> Callable[..., Any]:
    value = getattr(engine_runner, name, None)
    assert callable(value), f"engine runner {name} must remain characterized"
    return value


@pytest.mark.parametrize(
    "name",
    ["run_skill", "predict_skill", "evaluate_golden_baseline"],
)
def test_public_engine_entrypoints_require_workspace_dir_argument(name: str) -> None:
    entrypoint = _engine_callable(name)
    parameter = inspect.signature(entrypoint).parameters.get("workspace_dir")

    assert parameter is not None, f"{name} must expose a workspace_dir parameter"
    assert parameter.default is inspect.Signature.empty, f"{name}.workspace_dir must be required"


def test_run_skill_missing_workspace_dir_raises_type_error(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    skill_root = tmp_path / "skill"
    _write_logic_skill(skill_root)

    with pytest.raises(TypeError, match="workspace_dir"):
        run_skill(skill_root, skill_resolver=mock_skill_resolver, topic="red")


@pytest.mark.parametrize("workspace_dir", [Path("relative-workspace"), Path("../escape")])
def test_run_skill_rejects_non_absolute_workspace_dir(
    tmp_path: Path,
    mock_skill_resolver: object,
    workspace_dir: Path,
) -> None:
    skill_root = tmp_path / "skill"
    _write_logic_skill(skill_root)

    with pytest.raises((TypeError, ValueError), match="workspace_dir"):
        run_skill(
            skill_root,
            workspace_dir=workspace_dir,
            skill_resolver=mock_skill_resolver,
            topic="red",
        )


def test_run_skill_writes_artifacts_under_workspace_runs_run_id(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    skill_root = tmp_path / "skill"
    workspace_dir = tmp_path / "workspace"
    run_id = "workspace-run-contract"
    _write_logic_skill(skill_root)

    result = run_skill(
        skill_root,
        workspace_dir=workspace_dir,
        thread_id=run_id,
        skill_resolver=mock_skill_resolver,
        topic="red",
    )

    run_dir = workspace_dir / "runs" / result.run_id
    assert result.run_id == run_id
    assert run_dir.is_dir()
    assert (run_dir / "trace.jsonl").is_file()


def test_run_skill_pathless_file_output_defaults_to_run_artifacts_dir(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    skill_root = tmp_path / "skill"
    workspace_dir = tmp_path / "workspace"
    run_id = "workspace-artifacts-contract"
    _write_logic_skill(skill_root)
    graph_path = skill_root / "graph.yaml"
    graph_path.write_text(
        graph_path.read_text(encoding="utf-8").replace(
            "      answer:\n        type: string",
            "      answer:\n"
            "        type: string\n"
            "      artifact_payload:\n"
            "        type: object\n"
            "        target: file",
        ),
        encoding="utf-8",
    )
    logic_path = skill_root / "phases" / "draft" / "LOGIC.md"
    logic_path.write_text(
        logic_path.read_text(encoding="utf-8").replace(
            "      answer:\n        type: string",
            "      answer:\n"
            "        type: string\n"
            "      artifact_payload:\n"
            "        type: object\n"
            "        target: file",
        ),
        encoding="utf-8",
    )
    action_path = skill_root / "phases" / "draft" / "actions" / "draft.py"
    action_path.write_text(
        "def draft(inputs):\n"
        "    topic = inputs.get('topic', 'missing')\n"
        "    return {\n"
        "        'answer': f'draft:{topic}',\n"
        "        'artifact_payload': {'topic': topic},\n"
        "    }\n",
        encoding="utf-8",
    )

    run_skill(
        skill_root,
        workspace_dir=workspace_dir,
        thread_id=run_id,
        skill_resolver=mock_skill_resolver,
        topic="red",
    )

    artifact_path = workspace_dir / "runs" / run_id / "artifacts" / "artifact_payload.json"
    assert artifact_path.is_file()
    assert artifact_path.read_text(encoding="utf-8")


def test_run_skill_signature_no_longer_accepts_trace_dir() -> None:
    assert "trace_dir" not in inspect.signature(run_skill).parameters
