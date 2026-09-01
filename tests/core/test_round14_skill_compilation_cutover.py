from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.graph_serializer import serialize_graph
from graph_skill_runtime.core.loader import SkillLoader
from graph_skill_runtime.core.manifest import (
    GraphManifest,
    GraphPhaseRef,
    LogicNodeAST,
    PhaseAST,
    PhaseIOSchema,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _object_schema(*properties: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "string"} for name in properties},
        "required": list(properties),
    }


def _new_skill(parent: Path, name: str = "round14") -> Path:
    root = parent / name
    _write(
        root / "SKILL.md",
        f"---\nname: {name}\ndescription: Exercise the portable compiler contract.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
    )
    return root


def _phase(
    phase_id: str,
    *,
    depends_on: list[str] | None = None,
    output: bool = True,
) -> dict[str, Any]:
    return {
        "id": phase_id,
        "depends_on": ["input"] if depends_on is None else depends_on,
        "output": output,
    }


def _graph(
    root: Path,
    *,
    schema_version: str = "gskill.graph.v1",
    graph_id: str = "root",
    phases: list[dict[str, Any]] | None = None,
    omit_phases: bool = False,
    inputs_field: str = "text",
    outputs_field: str = "result",
    extra: dict[str, Any] | None = None,
) -> None:
    document: dict[str, Any] = {
        "schema_version": schema_version,
        "graph_id": graph_id,
        "description": "Exercise the portable compiler contract.",
        "io": {
            "inputs": _object_schema(inputs_field),
            "outputs": _object_schema(outputs_field),
        },
    }
    if not omit_phases:
        document["phases"] = phases if phases is not None else [_phase("main")]
    if extra:
        document.update(extra)
    _write(root / "graph.yaml", yaml.safe_dump(document, sort_keys=False, allow_unicode=True))


def _markdown(frontmatter: dict[str, Any], body: str = "") -> str:
    rendered = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    return f"---\n{rendered}---\n{body}"


def _agent_phase(
    root: Path,
    phase_id: str = "main",
    *,
    extra: dict[str, Any] | None = None,
    body: str | None = None,
) -> None:
    phase_body = body or """<role>Tester</role>
<goal>Exercise the portable compiler contract.</goal>
<step id="S1" name="check">Use @protocol:P1 and @example:E1.</step>
<protocol id="P1">Return a precise result.</protocol>
<example id="E1">Input text becomes a result string.</example>
"""
    frontmatter: dict[str, Any] = {
        "name": phase_id,
        "validator": False,
        "io": {
            "inputs": _object_schema("text"),
            "outputs": _object_schema("result"),
        },
        "references": [
            {"id": "R1", "path": "references/r1.md", "summary": "Reference"}
        ],
        "examples": [
            {"id": "E2", "path": "examples/e2.md", "summary": "Document example"}
        ],
    }
    if extra:
        frontmatter.update(extra)
    _write(root / "phases" / phase_id / "AGENT.md", _markdown(frontmatter, phase_body))
    _write(root / "references" / "r1.md", "reference\n")
    _write(root / "examples" / "e2.md", "example\n")


def _logic_phase(
    root: Path,
    phase_id: str = "main",
    *,
    input_field: str = "text",
    output_field: str = "result",
    validator: object = False,
) -> None:
    frontmatter = {
        "name": phase_id,
        "io": {
            "inputs": _object_schema(input_field),
            "outputs": _object_schema(output_field),
        },
        "actions": ["run"],
        "validator": validator,
    }
    _write(
        root / "phases" / phase_id / "LOGIC.md",
        _markdown(frontmatter, "<action>run</action>\n"),
    )
    _write(
        root / "phases" / phase_id / "actions" / "run.py",
        f"def run(inputs):\n    return {{'{output_field}': inputs['{input_field}']}}\n",
    )


def _subgraph_phase(
    root: Path,
    phase_id: str = "main",
    *,
    graph_id: str = "child",
    input_field: str = "text",
    output_field: str = "result",
) -> None:
    frontmatter = {
        "name": phase_id,
        "graph": graph_id,
        "io": {
            "inputs": _object_schema(input_field),
            "outputs": _object_schema(output_field),
        },
        "validator": False,
    }
    _write(root / "phases" / phase_id / "SUBGRAPH.md", _markdown(frontmatter))


def _expect_code(exc: pytest.ExceptionInfo[SkillLoadError], code: str) -> None:
    assert exc.value.payload is not None
    assert exc.value.payload.code == code


def test_valid_portable_graph_uses_graph_yaml_as_the_only_phase_registry(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(root)

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    assert compiled.manifest.schema_version == "gskill.graph.v1"
    assert compiled.manifest.phases == (
        GraphPhaseRef(id="main", depends_on=("input",), output=True),
    )
    assert compiled.nodes[0].ast.mode == "agent"


def test_schema_version_without_namespace_is_rejected(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, schema_version="graph.v1")
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-schema-version-mismatch]")


def test_legacy_schema_version_is_rejected_with_otherwise_portable_shape(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, schema_version="v0.3.0")
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-schema-version-mismatch]")


@pytest.mark.parametrize("mode", ["skill", "agent", "logic", "subgraph"])
def test_phase_frontmatter_mode_is_forbidden_metadata(
    tmp_path: Path, mode: str, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(root, extra={"mode": mode})

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-agent-schema-unknown-field]")


@pytest.mark.parametrize("field", ["schema_version", "graph_skill_id", "phase_id"])
def test_phase_frontmatter_rejects_root_only_metadata(
    tmp_path: Path, field: str, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(root, extra={field: "polluted"})

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-agent-schema-unknown-field]")


def test_phase_ast_rejects_legacy_skill_mode_at_pydantic_layer() -> None:
    payload = {
        "mode": "skill",
        "name": "main",
        "io": {
            "inputs": _object_schema("text"),
            "outputs": _object_schema("result"),
        },
    }

    with pytest.raises(ValidationError):
        TypeAdapter(PhaseAST).validate_python(payload)


def test_logic_node_ast_accepts_validator_boolean_and_defaults_false() -> None:
    ast = LogicNodeAST.model_validate(
        {
            "mode": "logic",
            "name": "main",
            "io": {
                "inputs": _object_schema("text"),
                "outputs": _object_schema("result"),
            },
            "actions": ["run"],
        }
    )

    assert ast.validator is False


def test_logic_validator_must_be_boolean(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _logic_phase(root, validator="yes")

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-logic-validator-type-invalid]")


def test_phase_directory_with_multiple_node_files_uses_ambiguous_code(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(root)
    _logic_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phase-mode-ambiguous]")


def test_declared_phase_without_node_file_uses_node_missing_code(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    (root / "phases" / "main").mkdir(parents=True)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phase-node-missing]")


def test_graph_without_phases_is_rejected(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, omit_phases=True)
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phases-missing]")


def test_graph_phase_without_depends_on_is_rejected(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[{"id": "main", "output": True}])
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-depends-unknown]")


def test_graph_phase_id_must_match_physical_directory(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[_phase("other")])
    _agent_phase(root, "main")

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phase-name-mismatch]")


def test_duplicate_phase_registration_uses_dedicated_code(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[_phase("main"), _phase("main")])
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phase-id-duplicate]")


def test_unknown_depends_on_uses_dedicated_code(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[_phase("main", depends_on=["missing"])])
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-depends-unknown]")


def test_graph_cycle_uses_dedicated_code(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(
        root,
        phases=[
            _phase("first", depends_on=["second"], output=False),
            _phase("second", depends_on=["first"]),
        ],
    )
    _agent_phase(root, "first")
    _agent_phase(root, "second")

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-phase-cycle]")


def test_empty_depends_on_is_rejected_at_the_typed_boundary(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[_phase("main", depends_on=[])])
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-depends-unknown]")
    assert exc.value.payload is not None
    assert exc.value.payload.field_path == "phases.0.depends_on"


def test_unknown_dep_does_not_add_a_cascade_island_diagnostic(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(
        root,
        phases=[
            _phase("first", output=True),
            _phase("orphan", depends_on=["missing"], output=False),
        ],
    )
    _agent_phase(root, "first")
    _agent_phase(root, "orphan")

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-depends-unknown]")
    issues = exc.value.compile_result.issues
    assert not [
        issue for issue in issues if issue.rule_id == "[F-v3-graph-phase-island]"
    ]


def test_missing_output_phase_is_compile_fatal(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, phases=[_phase("main", output=False)])
    _agent_phase(root)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-graph-output-phase-invalid]")


@pytest.mark.parametrize(
    ("extra", "relative_path", "expected_code"),
    [
        ({"io_inputs_ref": "io/inputs.json"}, None, "[F-v3-graph-schema-unknown-field]"),
        ({"io_outputs_ref": "io/outputs.json"}, None, "[F-v3-graph-schema-unknown-field]"),
        ({}, "io/inputs.json", "[F-v3-graph-io-physical-file-deprecated]"),
        ({}, "io/outputs.json", "[F-v3-graph-io-physical-file-deprecated]"),
    ],
)
def test_physical_or_reference_based_root_io_is_rejected(
    tmp_path: Path,
    extra: dict[str, Any],
    relative_path: str | None,
    expected_code: str,
    mock_skill_resolver: object,
) -> None:
    root = _new_skill(tmp_path)
    _graph(root, extra=extra)
    _agent_phase(root)
    if relative_path is not None:
        _write(root / relative_path, "{}\n")

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, expected_code)


@pytest.mark.parametrize(
    "body",
    [
        '<role>Tester</role><goal>Goal</goal><steps><step id="S1">bad</step></steps>',
        "<role>Tester</role><goal>Goal</goal><exit_contract>bad</exit_contract>",
    ],
)
def test_agent_body_rejects_non_whitelisted_top_level_tags(
    tmp_path: Path, body: str, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(root, body=body)

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-agent-body-tag-unknown]")


def test_agent_body_extracts_inline_examples_for_mentions(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(
        root,
        body="""<role>Tester</role>
<goal>Use @example:E1.</goal>
<example id="E1">Inline body example.</example>
""",
    )

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    assert compiled.nodes[0].ast.examples_inline[0].id == "E1"


def test_missing_mention_target_is_rejected(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _new_skill(tmp_path)
    _graph(root)
    _agent_phase(
        root,
        body="""<role>Tester</role>
<goal>Use @reference:MISSING.</goal>
""",
    )

    with pytest.raises(SkillLoadError) as exc:
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    _expect_code(exc, "[F-v3-mention-target-not-found]")


def test_subgraph_io_input_mismatch_is_allowed_at_compile_time(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    parent = _new_skill(tmp_path, "parent")
    child = parent / "graphs" / "child"
    _graph(parent, inputs_field="parent_input")
    _subgraph_phase(parent, input_field="parent_input", output_field="result")
    _graph(
        child,
        graph_id="child",
        inputs_field="child_input",
        outputs_field="result",
    )
    _logic_phase(child, input_field="child_input")

    compiled = SkillLoader().compile_skill(parent, skill_resolver=mock_skill_resolver)

    assert compiled.nodes[0].phase_name == "main"


def test_subgraph_io_output_mismatch_is_allowed_at_compile_time(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    parent = _new_skill(tmp_path, "parent")
    child = parent / "graphs" / "child"
    _graph(parent, outputs_field="parent_output")
    _subgraph_phase(parent, output_field="parent_output")
    _graph(
        child,
        graph_id="child",
        inputs_field="text",
        outputs_field="child_output",
    )
    _logic_phase(child, output_field="child_output")

    compiled = SkillLoader().compile_skill(parent, skill_resolver=mock_skill_resolver)

    assert compiled.nodes[0].phase_name == "main"


def test_graph_serializer_fresh_render_emits_only_portable_yaml() -> None:
    manifest = GraphManifest(
        schema_version="gskill.graph.v1",
        graph_id="serializer",
        description="Serializer fixture.",
        io=PhaseIOSchema(
            inputs=_object_schema("text"), outputs=_object_schema("result")
        ),
        phases=(GraphPhaseRef(id="main", depends_on=("input",), output=True),),
    )

    rendered = serialize_graph(manifest)

    assert "schema_version: gskill.graph.v1" in rendered
    assert "graph_id: serializer" in rendered
    assert "- id: main" in rendered
    assert "depends_on:" in rendered
    assert "- input" in rendered
    assert "output: true" in rendered
    assert "<phase" not in rendered
