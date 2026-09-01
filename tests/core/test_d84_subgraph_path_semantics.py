from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.graph_assembler import assemble_graph
from graph_skill_runtime.core.manifest import AgentNodeAST, SubgraphNodeAST
from graph_skill_runtime.core.topology_projection import (
    load_child_graph_topology_projection,
    read_subgraph_graph_id,
)


class ExplodingResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve_skill(self, skill_id: str) -> Path:
        self.calls.append(skill_id)
        raise AssertionError(f"graph registry references must not resolve external skill {skill_id!r}")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _root_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Portable graph registry test skill.
metadata:
  gskill: gskill.graph.v1
---

Use the graph-skill runtime to execute this skill.
""",
    )


def _graph(root: Path, *, graph_id: str, phase: str) -> None:
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Graph {graph_id}.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
phases:
  - id: {phase}
    depends_on: [input]
    output: true
""",
    )


def _logic_graph(root: Path, *, graph_id: str = "child") -> None:
    _graph(root, graph_id=graph_id, phase="done")
    _write(
        root / "phases" / "done" / "LOGIC.md",
        """---
name: Identity
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}
---
<action>identity</action>
""",
    )
    _write(root / "phases" / "done" / "actions" / "identity.py", "def identity(inputs):\n    return {}\n")


def _subgraph_parent(root: Path, graph_id: str) -> None:
    _root_skill(root)
    _graph(root, graph_id="parent", phase="delegate")
    _write(
        root / "phases" / "delegate" / "SUBGRAPH.md",
        f"""---
name: Delegate
graph: {graph_id}
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
---
""",
    )


def _agent_ast_payload() -> dict[str, Any]:
    return {
        "mode": "agent",
        "name": "Planner",
        "role": "Planner",
        "goal": "Plan the work.",
        "io": {
            "inputs": {"type": "object", "properties": {}},
            "outputs": {"type": "object", "properties": {}},
        },
        "subagents": [
            {
                "name": "worker",
                "target_skill": "demo-worker",
                "description": "External subagent uses an Agent Skill name.",
            }
        ],
        "subgraphs": [
            {
                "name": "child_graph",
                "graph": "child",
                "description": "Internal child graph uses a registry id.",
            }
        ],
    }


def test_subgraph_ast_accepts_graph_id_and_rejects_paths() -> None:
    ast = SubgraphNodeAST.model_validate(
        {
            "mode": "subgraph",
            "name": "Delegate",
            "graph": "child-graph",
            "io": {"inputs": {"type": "object"}, "outputs": {"type": "object"}},
        }
    )

    assert ast.graph == "child-graph"
    for retired_field in ("path", "target_skill"):
        with pytest.raises(ValidationError):
            SubgraphNodeAST.model_validate(
                {
                    "mode": "subgraph",
                    "name": "Delegate",
                    retired_field: "child-graph",
                    "io": {"inputs": {"type": "object"}, "outputs": {"type": "object"}},
                }
            )


def test_flat_registry_graph_compiles_and_assembles_without_external_resolver(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    _subgraph_parent(parent, "child")
    _logic_graph(parent / "graphs" / "child")
    resolver = ExplodingResolver()

    compiled = compile_skill(parent, cache=False, skill_resolver=resolver)
    assembled = assemble_graph(compiled, skill_resolver=resolver)

    assert resolver.calls == []
    assert assembled.phase_ids == ["delegate"]
    assert sorted(compiled.graph_registry) == ["child", "parent"]


def test_graph_reference_remains_valid_after_skill_relocation(tmp_path: Path) -> None:
    origin = tmp_path / "origin" / "parent"
    _subgraph_parent(origin, "child")
    _logic_graph(origin / "graphs" / "child")
    compile_skill(origin, cache=False)

    relocated = tmp_path / "ephemeral" / "parent"
    shutil.copytree(origin, relocated)
    compiled = compile_skill(relocated, cache=False)

    assert compiled.graph_registry["child"].graph_root == (relocated / "graphs" / "child").resolve()
    assert assemble_graph(compiled).phase_ids == ["delegate"]


def test_unknown_graph_reference_is_one_structured_compile_diagnostic(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    _subgraph_parent(root, "missing-child")

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    issues = exc_info.value.compile_result.issues
    assert [item.rule_id for item in issues] == ["[F-v3-graph-reference-unknown]"]
    assert issues[0].source_path == "phases/delegate/SUBGRAPH.md"


def test_agent_subgraphs_use_graph_ids_while_subagents_keep_target_skill() -> None:
    ast = AgentNodeAST.model_validate(_agent_ast_payload())

    assert ast.subgraphs[0].graph == "child"
    assert ast.subagents[0].target_skill == "demo-worker"

    payload = _agent_ast_payload()
    payload["subgraphs"][0] = {
        "name": "child_graph",
        "path": "graphs/child",
        "description": "Paths are not portable graph identities.",
    }
    with pytest.raises(ValidationError, match="path"):
        AgentNodeAST.model_validate(payload)


def test_topology_projection_exposes_graph_id_and_flat_registry_child(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    _subgraph_parent(root, "child")
    _logic_graph(root / "graphs" / "child")

    assert read_subgraph_graph_id(root, "delegate") == "child"
    child = load_child_graph_topology_projection(parent_skill_dir=root, graph_id="child")
    assert child.name == "child"
    assert child.path == str((root / "graphs" / "child").resolve())
    assert child.phases == ["done"]
