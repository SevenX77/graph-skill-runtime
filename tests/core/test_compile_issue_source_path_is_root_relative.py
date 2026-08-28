"""A compile diagnostic names its file relative to the business skill root."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import GraphAgentError


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _io(input_field: str, output_field: str) -> str:
    return f"""io:
  inputs:
    type: object
    required: [{input_field}]
    properties:
      {input_field}: {{type: string}}
  outputs:
    type: object
    required: [{output_field}]
    properties:
      {output_field}: {{type: string}}"""


def _child(
    root: Path,
    graph_id: str,
    *,
    input_field: str,
    output_field: str,
) -> Path:
    child = root / "graphs" / graph_id
    _write(
        child / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Portable child graph.
{_io(input_field, output_field)}
phases:
  - id: review
    depends_on: [input]
    output: true
""",
    )
    _write(
        child / "phases" / "review" / "AGENT.md",
        f"""---
name: review
llm_role: analyst
{_io(input_field, output_field)}
---
<role>Review the input.</role>
<goal>Turn {{{input_field}}} into {output_field}.</goal>
""",
    )
    return child


def _skill(tmp_path: Path) -> Path:
    """Root graph calls two flat registry graphs with a same-named phase."""
    root = tmp_path / "source-path-skill"
    _write(
        root / "SKILL.md",
        "---\nname: source-path-skill\ndescription: Diagnostic path fixture.\n---\n",
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Root diagnostic graph.
{_io("topic", "answer")}
phases:
  - id: alpha
    depends_on: [input]
    output: false
  - id: beta
    depends_on: [alpha]
    output: true
""",
    )
    _child(root, "first", input_field="topic", output_field="draft")
    _child(root, "second", input_field="draft", output_field="answer")
    _write(
        root / "phases" / "alpha" / "SUBGRAPH.md",
        f"""---
name: alpha
graph: first
{_io("topic", "draft")}
---
""",
    )
    _write(
        root / "phases" / "beta" / "SUBGRAPH.md",
        f"""---
name: beta
graph: second
{_io("draft", "answer")}
---
""",
    )
    return root


def _issues(root: Path) -> list[object]:
    with pytest.raises(GraphAgentError) as caught:
        compile_skill(root, cache=False)
    return list(caught.value.compile_result.issues)


def test_a_registry_graph_defect_is_not_reported_at_the_root_graph(tmp_path: Path) -> None:
    root = _skill(tmp_path)
    child_graph = root / "graphs" / "first" / "graph.yaml"
    child_graph.write_text(
        child_graph.read_text(encoding="utf-8").replace(
            "phases:", "no_such_graph_field: 1\nphases:", 1
        ),
        encoding="utf-8",
        newline="\n",
    )

    located = [(issue.rule_id, issue.source_path) for issue in _issues(root)]

    assert (
        "[F-v3-graph-schema-unknown-field]",
        "graphs/first/graph.yaml",
    ) in located
    assert ("[F-v3-graph-schema-unknown-field]", "graph.yaml") not in located


def test_same_named_phases_in_two_registry_graphs_stay_distinguishable(
    tmp_path: Path,
) -> None:
    root = _skill(tmp_path)
    for graph_id in ("first", "second"):
        phase = root / "graphs" / graph_id / "phases" / "review" / "AGENT.md"
        phase.write_text(
            phase.read_text(encoding="utf-8").replace(
                "<role>Review the input.</role>",
                "<no_such_tag>x</no_such_tag>\n<role>Review the input.</role>",
                1,
            ),
            encoding="utf-8",
            newline="\n",
        )

    paths = [issue.source_path for issue in _issues(root)]

    assert "graphs/first/phases/review/AGENT.md" in paths
    assert "graphs/second/phases/review/AGENT.md" in paths


def test_a_root_phase_defect_keeps_its_plain_relative_path(tmp_path: Path) -> None:
    root = _skill(tmp_path)
    node = root / "phases" / "alpha" / "SUBGRAPH.md"
    node.write_text(
        node.read_text(encoding="utf-8").replace(
            "graph:", "no_such_field: 1\ngraph:", 1
        ),
        encoding="utf-8",
        newline="\n",
    )

    paths = [issue.source_path for issue in _issues(root)]

    assert "phases/alpha/SUBGRAPH.md" in paths
