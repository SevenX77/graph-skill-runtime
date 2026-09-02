"""Skill fixtures for WS-E4 runtime edge event tests."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

#: One `graph.yaml` phase entry: its id, its direct upstreams, and whether it is
#: a graph output node. `input` is the graph-input sentinel, not a phase id.
PhaseSpec = tuple[str, list[str], bool]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _schema_yaml(properties: dict[str, Any], *, required: list[str] | None = None) -> str:
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    return json.dumps(schema, ensure_ascii=False, indent=4).replace("\n", "\n    ")


def _write_graph(
    root: Path,
    *,
    name: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    phases: list[PhaseSpec],
    required_inputs: list[str] | None = None,
    iterate: str | None = None,
    skill_entry: bool = True,
) -> None:
    """Write a portable gSkill v1 graph.

    ``skill_entry`` is False for a registry graph under ``graphs/<graph_id>/``:
    only a skill root owns the Agent Skills entrypoint, and its ``name`` must
    equal the root directory basename.
    """

    if skill_entry:
        _write(
            root / "SKILL.md",
            f"""---
name: {root.name}
description: WS-E4 runtime fixture skill for {name}.
---
Compile and run this graph skill with graph-skill-runtime.
""",
        )
    phase_list = "\n".join(
        "\n".join(
            (
                f"  - id: {phase_id}",
                f"    depends_on: [{', '.join(depends_on)}]",
                f"    output: {str(is_output).lower()}",
            )
        )
        for phase_id, depends_on, is_output in phases
    )
    iterate_block = f"{iterate.strip()}\n" if iterate else ""
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {name}
description: WS-E4 runtime fixture graph for {name}.
io:
  inputs:
    {_schema_yaml(inputs, required=required_inputs)}
  outputs:
    {_schema_yaml(outputs)}
phases:
{phase_list}
{iterate_block}""",
    )


def write_logic_phase(
    root: Path,
    phase_id: str,
    *,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    action_body: str,
    required: list[str] | None = None,
    iterate: str | None = None,
) -> None:
    iterate_block = f"{iterate.rstrip()}\n" if iterate else ""
    _write(
        root / "phases" / phase_id / "LOGIC.md",
        f"""---
name: {phase_id}
io:
  inputs:
    {_schema_yaml(inputs, required=required)}
  outputs:
    {_schema_yaml(outputs)}
actions: [{phase_id}]
validator: false
{iterate_block}---
<action>{phase_id}</action>
""",
    )
    _write(
        root / "phases" / phase_id / "actions" / f"{phase_id}.py",
        dedent(action_body).lstrip(),
    )


def write_serial_two_phase_skill(root: Path, *, name: str = "ws-e4-runtime-serial") -> None:
    _write_graph(
        root,
        name=name,
        inputs={"source": {"type": "string"}},
        outputs={"answer": {"type": "string"}},
        phases=[("prepare", ["input"], False), ("finish", ["prepare"], True)],
        required_inputs=["source"],
    )
    write_logic_phase(
        root,
        "prepare",
        inputs={"source": {"type": "string"}},
        outputs={"prepared": {"type": "string"}},
        required=["source"],
        action_body="""
            def prepare(inputs):
                return {"prepared": f"{inputs['source']}:prepared"}
        """,
    )
    write_logic_phase(
        root,
        "finish",
        inputs={"prepared": {"type": "string"}},
        outputs={"answer": {"type": "string"}},
        required=["prepared"],
        action_body="""
            def finish(inputs):
                return {"answer": f"{inputs['prepared']}:done"}
        """,
    )


def write_loop_accumulate_skill(root: Path) -> None:
    _write_graph(
        root,
        name="ws-e4-runtime-loop-reduce",
        inputs={"items": {"type": "array"}},
        outputs={"collected": {"type": "array"}},
        phases=[("collect", ["input"], True)],
    )
    write_logic_phase(
        root,
        "collect",
        inputs={"item": {}, "collected": {}},
        outputs={"piece": {}},
        required=["item", "collected"],
        iterate="""
iterate:
  mode: loop
  over: items
  item_var: item
  accumulate:
    var: collected
    init: []
    from: piece
    merge: append
""",
        action_body="""
            def collect(inputs):
                return {"piece": inputs["item"]}
        """,
    )


def write_batch_iterate_skill(root: Path) -> None:
    _write_graph(
        root,
        name="ws-e4-runtime-batch-dispatch",
        inputs={"items": {"type": "array"}},
        outputs={"seen": {"type": "array"}},
        phases=[("worker", ["input"], True)],
    )
    write_logic_phase(
        root,
        "worker",
        inputs={"item": {}},
        outputs={"seen": {}},
        required=["item"],
        iterate="""
iterate:
  mode: batch
  over: items
  item_var: item
  concurrency: 2
""",
        action_body="""
            def worker(inputs):
                return {"seen": inputs["item"]}
        """,
    )


def write_file_input_skill(root: Path) -> None:
    _write_graph(
        root,
        name="ws-e4-runtime-file-input",
        inputs={"title": {"type": "string"}},
        outputs={"answer": {"type": "string"}},
        phases=[("reader", ["input"], True)],
        required_inputs=["title"],
    )
    write_logic_phase(
        root,
        "reader",
        inputs={
            "title": {"type": "string"},
            "body": {"type": "string"},
        },
        outputs={"answer": {"type": "string"}},
        required=["title", "body"],
        action_body="""
            def reader(inputs):
                return {"answer": f"{inputs['title']}::{inputs['body']}"}
        """,
    )
