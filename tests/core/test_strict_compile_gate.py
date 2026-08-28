from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _root(parent: Path) -> Path:
    return parent / "strict-compile"


def _skill_entry(root: Path) -> None:
    _write(
        root / "SKILL.md",
        """---
name: strict-compile
description: Exercise strict portable compile boundaries.
---
""",
    )


def _graph(
    root: Path,
    *,
    input_field: str = "topic",
    output_field: str = "answer",
    phase: str = "main",
) -> None:
    _skill_entry(root)
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Exercise strict portable compile boundaries.
io:
  inputs:
    type: object
    properties:
      {input_field}:
        type: string
    required: [{input_field}]
  outputs:
    type: object
    properties:
      {output_field}:
        type: string
    required: [{output_field}]
phases:
  - id: {phase}
    depends_on: [input]
    output: true
""",
    )


def _agent(
    root: Path,
    *,
    input_field: str = "topic",
    output_field: str = "answer",
    tool: str | None = None,
    reference_path: str | None = None,
    example_path: str | None = None,
) -> None:
    tools = f"tools:\n  - {tool}\n" if tool else ""
    references = (
        f"references:\n  - id: R1\n    path: {reference_path}\n    summary: Ref.\n"
        if reference_path
        else ""
    )
    examples = (
        f"examples:\n  - id: E1\n    path: {example_path}\n    summary: Example.\n"
        if example_path
        else ""
    )
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"""---
name: main
io:
  inputs:
    type: object
    properties:
      {input_field}:
        type: string
    required: [{input_field}]
  outputs:
    type: object
    properties:
      {output_field}:
        type: string
    required: [{output_field}]
{tools}{references}{examples}---
<role>
Assistant.
</role>
<goal>
Produce the declared output.
</goal>
""",
    )


def _compile(root: Path, mock_skill_resolver: object) -> None:
    SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)


def _assert_code(exc_info: pytest.ExceptionInfo[SkillLoadError], code: str) -> None:
    assert exc_info.value.payload.code == code


def test_phase_config_is_compile_fatal(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = _root(tmp_path)
    _graph(root)
    _write(
        root / "phases" / "main" / "AGENT.md",
        """---
name: main
phase_config:
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
      required: [answer]
---
<role>
Assistant.
</role>
<goal>
Produce the declared output.
</goal>
""",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-agent-schema-unknown-field]")
    assert exc_info.value.payload.field_path == "phase_config"


def test_required_io_must_be_declared_in_properties(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _skill_entry(root)
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise strict portable compile boundaries.
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
    required: [missing]
  outputs:
    type: object
    properties:
      answer:
        type: string
    required: [answer]
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _agent(root)

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-graph-io-schema-invalid]")


def test_phase_required_input_without_source_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, input_field="topic", output_field="answer")
    _agent(root, input_field="missing", output_field="answer")

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-graph-dataflow-source-missing]")


def test_phase_declared_input_without_source_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, input_field="topic", output_field="answer")
    _write(
        root / "phases" / "main" / "AGENT.md",
        """---
name: main
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
      chapter_lines:
        type: array
        items:
          type: string
      chapter_number:
        type: integer
    required: [topic]
  outputs:
    type: object
    properties:
      answer:
        type: string
    required: [answer]
---
<role>
Assistant.
</role>
<goal>
Produce the declared output.
</goal>
""",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-graph-dataflow-source-missing]")
    issues = exc_info.value.compile_result.issues  # type: ignore[attr-defined]
    assert [issue.field_path for issue in issues] == [
        "main.io.inputs.properties.chapter_lines",
        "main.io.inputs.properties.chapter_number",
    ]


def test_required_root_output_must_be_available_at_output_phase(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, input_field="topic", output_field="answer")
    _agent(root, input_field="topic", output_field="summary")

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-graph-dataflow-source-missing]")


def test_unknown_declared_agent_tool_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root)
    _agent(root, tool="missing_tool")

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-agent-tool-unknown]")


def test_reference_path_must_resolve_to_readable_file(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root)
    _agent(root, reference_path="refs/missing.md")

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-resource-reference-path-invalid]")


def test_example_path_must_resolve_to_readable_file(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root)
    _agent(root, example_path="examples/missing.md")

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-resource-example-path-invalid]")


@pytest.mark.parametrize("bad_path", [r"refs\guide.md", "C:/refs/guide.md"])
def test_declared_resource_paths_must_be_portable_relative_paths(
    tmp_path: Path,
    mock_skill_resolver: object,
    bad_path: str,
) -> None:
    root = _root(tmp_path)
    _graph(root)
    _agent(root, reference_path=bad_path)

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-resource-reference-path-invalid]")


def test_logic_action_inputs_mutation_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, output_field="normalized")
    _write(
        root / "phases" / "main" / "LOGIC.md",
        """---
name: main
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
      normalized:
        type: string
    required: [normalized]
actions: [normalize]
---
<action>normalize</action>
""",
    )
    _write(
        root / "phases" / "main" / "actions" / "normalize.py",
        "def normalize(inputs):\n    inputs['normalized'] = 'bad'\n    return {}\n",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-logic-action-purity-violation]")


def test_logic_action_context_signature_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, output_field="normalized")
    _write(
        root / "phases" / "main" / "LOGIC.md",
        """---
name: main
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
      normalized:
        type: string
    required: [normalized]
actions: [normalize]
---
<action>normalize</action>
""",
    )
    _write(
        root / "phases" / "main" / "actions" / "normalize.py",
        "def normalize(context):\n    return {'normalized': 'bad'}\n",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        _compile(root, mock_skill_resolver)

    _assert_code(exc_info, "[F-v3-logic-action-entrypoint-missing]")


def test_compile_does_not_write_pycache_into_skill_actions(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _root(tmp_path)
    _graph(root, output_field="normalized")
    actions_dir = root / "phases" / "main" / "actions"
    _write(
        root / "phases" / "main" / "LOGIC.md",
        """---
name: main
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
      normalized:
        type: string
    required: [normalized]
actions: [normalize]
---
<action>normalize</action>
""",
    )
    _write(
        actions_dir / "normalize.py",
        "def normalize(inputs):\n    return {'normalized': inputs['topic']}\n",
    )

    _compile(root, mock_skill_resolver)

    assert not (actions_dir / "__pycache__").exists()


def test_nested_json_schema_remains_legal(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = _root(tmp_path)
    _skill_entry(root)
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise strict portable compile boundaries.
io:
  inputs:
    type: object
    properties:
      records:
        type: array
        items:
          type: object
          properties:
            text:
              type: string
          required: [text]
    required: [records]
  outputs:
    type: object
    properties:
      answer:
        type: object
        properties:
          value:
            type: string
        required: [value]
    required: [answer]
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _agent(root, input_field="records", output_field="answer")

    _compile(root, mock_skill_resolver)
