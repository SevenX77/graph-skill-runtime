"""Resolver and graph-reference regression tests after the portable cutover."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from graph_skill_runtime.core import graph_assembler, loader
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.graph_assembler import assemble_graph
from graph_skill_runtime.core.manifest import SubagentSpec, SubgraphNodeAST
from graph_skill_runtime.core.runner import run_skill


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _entry(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"---\nname: {root.name}\ndescription: Portable resolver fixture.\n---\n",
    )


def _graph(
    root: Path,
    *,
    graph_id: str,
    phase_id: str,
    with_text_input: bool = False,
) -> None:
    input_schema = (
        """type: object
    required: [text]
    properties:
      text: {type: string}"""
        if with_text_input
        else """type: object
    properties: {}"""
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Resolver graph {graph_id}.
llm_role: analyst
io:
  inputs:
    {input_schema}
  outputs:
    type: object
    properties: {{}}
phases:
  - id: {phase_id}
    depends_on: [input]
    output: true
""",
    )


def _logic_graph(root: Path, *, graph_id: str = "root", business_skill: bool = True) -> None:
    if business_skill:
        _entry(root)
    _graph(root, graph_id=graph_id, phase_id="done", with_text_input=True)
    _write(
        root / "phases" / "done" / "LOGIC.md",
        """---
name: done
io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: string}
  outputs:
    type: object
    properties: {}
---
<action>identity</action>
""",
    )
    _write(
        root / "phases" / "done" / "actions" / "identity.py",
        "def identity(inputs):\n    return {}\n",
    )


def _subagent_parent(root: Path, target_skill: str) -> None:
    _entry(root)
    _graph(root, graph_id="root", phase_id="main")
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"""---
name: main
subagents:
  - name: child_expert
    target_skill: {target_skill}
    description: Resolve child by Agent Skills name.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
---
<role>Parent agent.</role>
<goal>Delegate work when needed.</goal>
""",
    )


def _subgraph_parent(root: Path) -> None:
    _entry(root)
    _graph(root, graph_id="root", phase_id="child", with_text_input=True)
    _write(
        root / "phases" / "child" / "SUBGRAPH.md",
        """---
name: child
graph: child
io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: string}
  outputs:
    type: object
    properties: {}
---
""",
    )
    _logic_graph(root / "graphs" / "child", graph_id="child", business_skill=False)


def test_compile_and_assemble_default_to_a_local_agent_skill_resolver(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    _subagent_parent(parent, "child")
    _logic_graph(child)

    compiled = compile_skill(parent, cache=False)
    assembled = assemble_graph(compiled)

    assert assembled.graph is not None
    assert compiled.subagents_by_phase["main"][0].root == child.resolve()


def test_run_skill_defaults_to_the_local_resolver(tmp_path: Path) -> None:
    skill_root = tmp_path / "standalone"
    _logic_graph(skill_root)

    result = run_skill(
        skill_root,
        text="hello",
        workspace_dir=(tmp_path / "workspace").resolve(),
    )

    assert result.success is True


def test_subagent_spec_rejects_legacy_path_field() -> None:
    with pytest.raises(ValidationError):
        SubagentSpec.model_validate(
            {
                "name": "legacy_child",
                "path": "subskills/child",
                "description": "Legacy path must be removed.",
            }
        )


def test_subagent_spec_exposes_only_agent_skill_identity() -> None:
    assert "path" not in SubagentSpec.model_fields
    assert "target_skill" in SubagentSpec.model_fields
    assert not hasattr(loader, "_resolve_subagent" + "_root")


@pytest.mark.parametrize("legacy_field", ["path", "sub_skill_ref"])
def test_subgraph_ast_rejects_legacy_location_fields(legacy_field: str) -> None:
    with pytest.raises(ValidationError):
        SubgraphNodeAST.model_validate(
            {
                "mode": "subgraph",
                "name": "child",
                "graph": "child",
                legacy_field: "subskills/child",
                "io": {
                    "inputs": {"type": "object"},
                    "outputs": {"type": "object"},
                },
            }
        )


def test_subgraph_ast_requires_a_graph_id() -> None:
    with pytest.raises(ValidationError, match="graph"):
        SubgraphNodeAST.model_validate(
            {
                "mode": "subgraph",
                "name": "child",
                "io": {
                    "inputs": {"type": "object"},
                    "outputs": {"type": "object"},
                },
            }
        )


def test_graph_assembler_exposes_no_legacy_path_resolver() -> None:
    assert not hasattr(graph_assembler, "_resolve_sub_skill" + "_path")


def test_flat_registry_subgraph_compiles_and_assembles_without_a_skill_resolver(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    _subgraph_parent(parent)

    compiled = compile_skill(parent, cache=False)
    graph = assemble_graph(compiled)

    assert graph.phase_ids == ["child"]
    assert sorted(compiled.graph_registry) == ["child", "root"]
