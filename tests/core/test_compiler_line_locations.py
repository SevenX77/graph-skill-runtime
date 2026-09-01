"""Line-location guarantees for portable graph and phase documents."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader
from graph_skill_runtime.core.parser import locate_line_for_pydantic_loc, parse_markdown_parts

_EMPTY_IO = """io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "line-location-skill"
    _write(
        root / "SKILL.md",
        "---\nname: line-location-skill\ndescription: Line location fixture.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
    )
    return root


def _write_minimal_logic_skill(
    root: Path,
    *,
    graph_extra: str = "",
    logic_extra: str = "",
) -> None:
    graph_extra_row = f"{graph_extra}\n" if graph_extra else ""
    logic_extra_row = f"{logic_extra}\n" if logic_extra else ""
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Line location graph.
{graph_extra_row}io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    required: [answer]
    properties:
      answer: {{type: string}}
phases:
  - id: prepare
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "prepare" / "LOGIC.md",
        f"""---
name: prepare
{logic_extra_row}io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    required: [answer]
    properties:
      answer: {{type: string}}
---
<action>prepare</action>
""",
    )
    _write(
        root / "phases" / "prepare" / "actions" / "prepare.py",
        "def prepare(inputs):\n    return {'answer': 'ok'}\n",
    )


def _write_agent_graph(
    root: Path,
    *,
    phases: list[tuple[str, tuple[str, ...], bool]],
    bodies: dict[str, str] | None = None,
) -> dict[str, Path]:
    phase_rows: list[str] = []
    for phase_id, dependencies, output in phases:
        phase_rows.append(
            f"  - id: {phase_id}\n"
            f"    depends_on: [{', '.join(dependencies)}]\n"
            f"    output: {str(output).lower()}"
        )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Agent line location graph.
{_EMPTY_IO}
phases:
{chr(10).join(phase_rows)}
""",
    )
    paths: dict[str, Path] = {}
    for phase_id, _, _ in phases:
        path = root / "phases" / phase_id / "AGENT.md"
        _write(
            path,
            f"""---
name: {phase_id}
llm_role: analyst
{_EMPTY_IO}
---
{(bodies or {}).get(phase_id, "<role>R</role>" + chr(10) + "<goal>G</goal>" + chr(10))}""",
        )
        paths[phase_id] = path
    return paths


def _compile_error(root: Path) -> SkillLoadError:
    with pytest.raises(SkillLoadError) as caught:
        SkillLoader().compile_skill(root)
    return caught.value


def _issues(exc: SkillLoadError) -> list[object]:
    return list(exc.compile_result.issues)


def _issue(exc: SkillLoadError, code: str, source_path: str | None = None) -> object:
    matches = [
        issue
        for issue in _issues(exc)
        if issue.rule_id == code
        and (source_path is None or issue.source_path == source_path)
    ]
    assert matches, [(issue.rule_id, issue.source_path, issue.line) for issue in _issues(exc)]
    return matches[0]


def _line(path: Path, needle: str) -> int:
    return next(
        index
        for index, row in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in row
    )


def test_graph_validation_error_names_graph_yaml(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root)
    graph = root / "graph.yaml"
    graph.write_text(
        graph.read_text(encoding="utf-8").replace("graph_id: root", "graph_id: INVALID_ID"),
        encoding="utf-8",
        newline="\n",
    )

    exc = _compile_error(root)
    issue = _issue(exc, "[F-v3-graph-name-invalid]")

    assert "graph.yaml" in str(exc)
    assert issue.source_path == "graph.yaml"
    assert issue.field_path == "graph_id"
    assert issue.line == _line(graph, "graph_id:")


def test_graph_field_error_has_relative_source_and_field_path(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root, graph_extra="unexpected_root: true")

    exc = _compile_error(root)
    issue = _issue(exc, "[F-v3-graph-schema-unknown-field]")

    assert issue.source_path == "graph.yaml"
    assert issue.field_path == "unexpected_root"
    assert exc.payload is not None
    assert exc.payload.source_path == "graph.yaml"
    assert exc.payload.field_path == "unexpected_root"


def test_graph_yaml_parse_error_has_relative_source_path(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root)
    _write(root / "graph.yaml", "schema_version: [unterminated\n")

    exc = _compile_error(root)
    issue = _issue(exc, "[F-v3-graph-schema-unknown-field]")

    assert issue.source_path == "graph.yaml"
    assert issue.field_path is None


def test_phase_field_error_has_relative_source_and_field_path(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root, logic_extra='validator: "yes"')

    exc = _compile_error(root)
    issue = _issue(exc, "[F-v3-logic-validator-type-invalid]")

    assert issue.source_path == "phases/prepare/LOGIC.md"
    assert issue.field_path == "validator"


def test_public_error_payload_round_trips_location_axes(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root, graph_extra="unexpected_root: true")

    with pytest.raises(SkillLoadError) as caught:
        compile_skill(root, cache=False)

    payload = caught.value.payload
    assert payload is not None
    dumped = payload.model_dump(mode="json")
    assert dumped["source_path"] == "graph.yaml"
    assert dumped["field_path"] == "unexpected_root"
    assert caught.value.error_payload["source_path"] == "graph.yaml"
    assert caught.value.error_payload["field_path"] == "unexpected_root"


def test_locate_line_returns_one_indexed_line(tmp_path: Path) -> None:
    phase = tmp_path / "AGENT.md"
    _write(
        phase,
        "---\n"
        "name: hello\n"
        "subgraphs:\n"
        "  - name: phase_a\n"
        "    graph: graph-a\n"
        "---\n",
    )
    frontmatter, _, _ = parse_markdown_parts(phase)

    assert locate_line_for_pydantic_loc(frontmatter, ("name",)) == 2
    assert locate_line_for_pydantic_loc(frontmatter, ("subgraphs", 0, "graph")) == 5


def test_locate_line_returns_none_for_plain_dict() -> None:
    assert locate_line_for_pydantic_loc({"name": "x"}, ("name",)) is None


@pytest.mark.parametrize(
    ("body", "code", "needle"),
    [
        ("<goal>Done.</goal>\n<role></role>\n", "[F-v3-agent-role-missing]", "<role>"),
        ("<role>R</role>\n<goal></goal>\n", "[F-v3-agent-goal-missing]", "<goal>"),
        (
            "<role>R</role>\n<goal>G</goal>\n<bogus>x</bogus>\n",
            "[F-v3-agent-body-tag-unknown]",
            "<bogus>",
        ),
    ],
)
def test_agent_body_error_points_to_the_authored_tag_line(
    tmp_path: Path,
    body: str,
    code: str,
    needle: str,
) -> None:
    root = _root(tmp_path)
    phase = _write_agent_graph(
        root,
        phases=[("act", ("input",), True)],
        bodies={"act": body},
    )["act"]

    issue = _issue(_compile_error(root), code)

    assert issue.source_path == "phases/act/AGENT.md"
    assert issue.line == _line(phase, needle)


@pytest.mark.parametrize(
    ("body", "code", "remaining_tag"),
    [
        ("<goal>Done.</goal>\n", "[F-v3-agent-role-missing]", "<goal>"),
        ("<role>R</role>\n", "[F-v3-agent-goal-missing]", "<role>"),
    ],
)
def test_missing_agent_block_points_to_body_start(
    tmp_path: Path,
    body: str,
    code: str,
    remaining_tag: str,
) -> None:
    root = _root(tmp_path)
    phase = _write_agent_graph(
        root,
        phases=[("act", ("input",), True)],
        bodies={"act": body},
    )["act"]

    issue = _issue(_compile_error(root), code)

    assert issue.line == _line(phase, remaining_tag)


def test_empty_action_points_to_its_tag_line(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_minimal_logic_skill(root)
    logic = root / "phases" / "prepare" / "LOGIC.md"
    logic.write_text(
        logic.read_text(encoding="utf-8").replace(
            "<action>prepare</action>",
            "<action>prepare</action>\n<action></action>",
        ),
        encoding="utf-8",
        newline="\n",
    )

    issue = _issue(_compile_error(root), "[F-v3-logic-actions-empty]")

    assert issue.line == _line(logic, "<action></action>")


def test_forbidden_topology_tag_points_to_its_agent_file_line(tmp_path: Path) -> None:
    root = _root(tmp_path)
    phase = _write_agent_graph(
        root,
        phases=[("act", ("input",), True)],
        bodies={"act": "<role>R</role>\n<goal>G</goal>\n<edge>x</edge>\n"},
    )["act"]

    exc = _compile_error(root)

    assert "forbidden" in str(exc)
    assert exc.payload is not None
    assert exc.payload.source_path == "phases/act/AGENT.md"
    assert re.search(rf"{re.escape(str(phase))}:\d+", str(exc))
    assert _issues(exc)[0].line == _line(phase, "<edge>")


@pytest.mark.parametrize(
    ("phases", "code", "phase_id"),
    [
        ([("solo", ("solo",), True)], "[F-v3-graph-phase-cycle]", "solo"),
        ([("solo", ("ghost",), True)], "[F-v3-graph-depends-unknown]", "solo"),
        (
            [("a", ("b",), False), ("b", ("a",), True)],
            "[F-v3-graph-phase-cycle]",
            "a",
        ),
    ],
)
def test_topology_error_points_to_a_phase_entry_line(
    tmp_path: Path,
    phases: list[tuple[str, tuple[str, ...], bool]],
    code: str,
    phase_id: str,
) -> None:
    root = _root(tmp_path)
    _write_agent_graph(root, phases=phases)
    graph = root / "graph.yaml"

    issue = _issue(_compile_error(root), code)

    assert issue.source_path == "graph.yaml"
    if len(phases) == 1:
        assert issue.line == _line(graph, f"- id: {phase_id}")
    else:
        phase_lines = {_line(graph, f"- id: {item[0]}") for item in phases}
        assert issue.line in phase_lines


def test_missing_role_and_goal_are_reported_together(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_agent_graph(
        root,
        phases=[("act", ("input",), True)],
        bodies={"act": "Plain prose.\n"},
    )

    codes = {issue.rule_id for issue in _issues(_compile_error(root))}

    assert "[F-v3-agent-role-missing]" in codes
    assert "[F-v3-agent-goal-missing]" in codes


def test_defects_in_separate_nodes_do_not_hide_each_other(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_agent_graph(
        root,
        phases=[("first", ("input",), False), ("second", ("first",), True)],
        bodies={"first": "Plain prose.\n", "second": "Plain prose.\n"},
    )

    paths = {issue.source_path for issue in _issues(_compile_error(root))}

    assert "phases/first/AGENT.md" in paths
    assert "phases/second/AGENT.md" in paths


def test_two_unknown_dependencies_are_reported_together(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_agent_graph(
        root,
        phases=[
            ("a", ("input",), False),
            ("b", ("ghost-one",), True),
            ("c", ("ghost-two",), True),
        ],
    )

    unknown = [
        issue
        for issue in _issues(_compile_error(root))
        if issue.rule_id == "[F-v3-graph-depends-unknown]"
    ]
    messages = " | ".join(issue.message for issue in unknown)

    assert len(unknown) == 2
    assert "ghost-one" in messages
    assert "ghost-two" in messages


def test_topology_defect_does_not_hide_agent_body_defect(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_agent_graph(
        root,
        phases=[("a", ("input",), False), ("b", ("ghost",), True)],
        bodies={"a": "<role>R</role>\n", "b": "<role>R</role>\n<goal>G</goal>\n"},
    )

    codes = {issue.rule_id for issue in _issues(_compile_error(root))}

    assert "[F-v3-graph-depends-unknown]" in codes
    assert "[F-v3-agent-goal-missing]" in codes
