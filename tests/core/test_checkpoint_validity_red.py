"""RED tests for node-scoped checkpoint validity."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

from graph_skill_runtime.core.compiler import compile_skill


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _schema(properties: dict[str, Any], *, required: list[str] | None = None) -> str:
    payload: dict[str, Any] = {"type": "object", "properties": properties}
    if required is not None:
        payload["required"] = required
    return json.dumps(payload, ensure_ascii=False, indent=4).replace("\n", "\n    ")


def _fanout_skill(root: Path) -> None:
    graph_input = _schema({"topic": {"type": "string"}}, required=["topic"])
    graph_output = _schema(
        {
            "a": {"type": "string"},
            "b": {"type": "string"},
            "summary": {"type": "string"},
        },
        required=["a", "b", "summary"],
    )
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: A fan-out fan-in graph for node-scoped checkpoint validity.
---
Compile and run this graph skill with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: checkpoint-validity-red
description: A fan-out fan-in graph for node-scoped checkpoint validity.
io:
  inputs:
    {graph_input}
  outputs:
    {graph_output}
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
    )
    _logic_phase(
        root,
        "prepare",
        inputs=graph_input,
        outputs=_schema({"prepared": {"type": "string"}}, required=["prepared"]),
        action_body='return {"prepared": f"prepared:{inputs[\'topic\']}"}',
    )
    _logic_phase(
        root,
        "branch_a",
        inputs=_schema({"prepared": {"type": "string"}}, required=["prepared"]),
        outputs=_schema({"a": {"type": "string"}}, required=["a"]),
        action_body='return {"a": f"a:{inputs[\'prepared\']}"}',
    )
    _logic_phase(
        root,
        "branch_b",
        inputs=_schema({"prepared": {"type": "string"}}, required=["prepared"]),
        outputs=_schema({"b": {"type": "string"}}, required=["b"]),
        action_body='return {"b": f"b:{inputs[\'prepared\']}"}',
    )
    _logic_phase(
        root,
        "assemble",
        inputs=_schema(
            {"a": {"type": "string"}, "b": {"type": "string"}},
            required=["a", "b"],
        ),
        outputs=_schema({"summary": {"type": "string"}}, required=["summary"]),
        action_body='return {"summary": f"{inputs[\'a\']}|{inputs[\'b\']}"}',
    )


def _logic_phase(
    root: Path,
    phase_id: str,
    *,
    inputs: str,
    outputs: str,
    action_body: str,
) -> None:
    _write(
        root / "phases" / phase_id / "LOGIC.md",
        f"""---
name: {phase_id}
io:
  inputs:
    {inputs}
  outputs:
    {outputs}
actions: [{phase_id}]
validator: false
---
<action>{phase_id}</action>
""",
    )
    _write(
        root / "phases" / phase_id / "actions" / f"{phase_id}.py",
        dedent(
            f"""
            def {phase_id}(inputs):
                {action_body}
            """
        ).lstrip(),
    )


def test_checkpoint_validity_is_node_scoped_not_global(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    from graph_skill_runtime.core.checkpoint_validity import checkpoint_validity_by_phase

    skill_root = tmp_path / "skill"
    _fanout_skill(skill_root)
    compiled = compile_skill(skill_root, skill_resolver=mock_skill_resolver)

    validity = checkpoint_validity_by_phase(compiled, dirty_phase_ids={"branch_b"})

    assert validity == {
        "prepare": True,
        "branch_a": True,
        "branch_b": False,
        "assemble": False,
    }
