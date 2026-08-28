"""A predict stub must know the output schema of phases nested in subgraphs.

Decision doc: .kiro/specs/decision-2026-08-15-predict-nested-phase-schema.md

The schema fed to the heuristic stub used to be collected in the runner by
walking the ROOT skill's compiled nodes. Subgraphs are compiled separately at
assembly time, so their phases never appeared there: the stub fell back to
`{"value": "<mock_unknown>"}`, the finish gate rejected it every round, and the
phase burned its whole iteration budget before dying on exit control. Since a
skill may legitimately have no top-level agent phase at all (every phase a
subgraph), that made such skills structurally unable to pass predict.
"""

from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.core.runner import predict_skill

_SKILL_ENTRY = """---
name: parent
description: Exercise predict schemas inside flat-registry subgraphs.
---
"""

_CHILD_GRAPH = """schema_version: gskill.graph.v1
graph_id: child
description: Produce a headline inside an internal graph.
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {type: string}
  outputs:
    type: object
    required: [headline]
    properties:
      headline: {type: string}
phases:
  - id: write
    depends_on: [input]
    output: true
"""

_CHILD_AGENT = """---
name: write
llm_role: analyst
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {type: string}
  outputs:
    type: object
    required: [headline]
    properties:
      headline: {type: string}
---
<role>Headline writer.</role>
<goal>Write one headline for the topic, then finish the task.</goal>
"""

_PARENT_GRAPH = """schema_version: gskill.graph.v1
graph_id: root
description: Delegate prediction to one internal graph.
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {type: string}
  outputs:
    type: object
    required: [headline]
    properties:
      headline: {type: string}
phases:
  - id: delegate
    depends_on: [input]
    output: true
"""

_PARENT_SUBGRAPH = """---
name: delegate
graph: child
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {type: string}
  outputs:
    type: object
    required: [headline]
    properties:
      headline: {type: string}
---
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _nested_skill(root: Path) -> Path:
    parent = root / "parent"
    _write(parent / "SKILL.md", _SKILL_ENTRY)
    _write(parent / "graph.yaml", _PARENT_GRAPH)
    _write(parent / "phases" / "delegate" / "SUBGRAPH.md", _PARENT_SUBGRAPH)
    child = parent / "graphs" / "child"
    _write(child / "graph.yaml", _CHILD_GRAPH)
    _write(child / "phases" / "write" / "AGENT.md", _CHILD_AGENT)
    return parent


def test_predict_gives_the_stub_the_schema_of_a_phase_inside_a_subgraph(
    tmp_path: Path,
) -> None:
    """The nested agent phase must produce its DECLARED field, not the
    schema-less `{"value": "<mock_unknown>"}` placeholder."""
    skill = _nested_skill(tmp_path)

    result = predict_skill(skill, workspace_dir=tmp_path / "ws", topic="mirrors")

    assert result.success, f"predict failed: {result.error}"
    assert "headline" in result.context, (
        "the nested phase's declared output never reached the blackboard; "
        f"context={result.context}"
    )
    nested = [phase for phase in result.phases if phase.phase_name == "write"]
    assert nested, f"phases={[p.phase_name for p in result.phases]}"
    assert "value" not in nested[0].outputs, (
        "stub fell back to the schema-less placeholder for a nested phase: "
        f"{nested[0].outputs}"
    )


_SECOND_CHILD_GRAPH = _CHILD_GRAPH.replace("graph_id: child", "graph_id: child-b").replace(
    "headline", "verdict"
)
_SECOND_CHILD_AGENT = _CHILD_AGENT.replace("headline", "verdict")

_TWO_CHILD_PARENT_GRAPH = """schema_version: gskill.graph.v1
graph_id: root
description: Delegate prediction to two internal graphs with same-named phases.
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {type: string}
  outputs:
    type: object
    required: [headline, verdict]
    properties:
      headline: {type: string}
      verdict: {type: string}
phases:
  - id: first
    depends_on: [input]
    output: false
  - id: second
    depends_on: [first]
    output: true
"""


def _subgraph_md(name: str, graph_id: str, field: str) -> str:
    return f"""---
name: {name}
graph: {graph_id}
io:
  inputs:
    type: object
    required: [topic]
    properties:
      topic: {{type: string}}
  outputs:
    type: object
    required: [{field}]
    properties:
      {field}: {{type: string}}
---
"""


def test_same_phase_name_in_two_subgraphs_each_gets_its_own_schema(tmp_path: Path) -> None:
    """Phase names are unique only WITHIN a skill. Two subgraphs may both call
    their phase `write`; each must be stubbed against its own declared output,
    not whichever one happened to register that name last."""
    parent = tmp_path / "parent"
    _write(parent / "SKILL.md", _SKILL_ENTRY)
    _write(parent / "graph.yaml", _TWO_CHILD_PARENT_GRAPH)
    _write(
        parent / "phases" / "first" / "SUBGRAPH.md",
        _subgraph_md("first", "child", "headline"),
    )
    _write(
        parent / "phases" / "second" / "SUBGRAPH.md",
        _subgraph_md("second", "child-b", "verdict"),
    )
    _write(parent / "graphs" / "child" / "graph.yaml", _CHILD_GRAPH)
    _write(parent / "graphs" / "child" / "phases" / "write" / "AGENT.md", _CHILD_AGENT)
    _write(parent / "graphs" / "child-b" / "graph.yaml", _SECOND_CHILD_GRAPH)
    _write(
        parent / "graphs" / "child-b" / "phases" / "write" / "AGENT.md",
        _SECOND_CHILD_AGENT,
    )

    result = predict_skill(parent, workspace_dir=tmp_path / "ws", topic="mirrors")

    assert result.success, f"predict failed: {result.error}"
    assert "headline" in result.context and "verdict" in result.context, (
        "one of the two same-named phases was stubbed against the other's schema; "
        f"context={result.context}"
    )
