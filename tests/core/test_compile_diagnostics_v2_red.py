"""Compile-diagnostic regression tests for the portable gSkill v1 contract.

These tests keep the useful guarantees from the diagnostics-v2 work while
constructing only the runtime's current format: one root Agent Skill entry,
one graph.yaml topology, and internal AGENT.md or LOGIC.md phase documents.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.error_registry import ERROR_REGISTRY, export_error_catalog
from graph_skill_runtime.core.exceptions import SkillLoadError


def _schema(properties: dict[str, object], required: list[str] | None = None) -> str:
    schema: dict[str, object] = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    return json.dumps(schema, ensure_ascii=False, indent=4).replace("\n", "\n    ")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "diagnostic-skill"
    _write(
        root / "SKILL.md",
        "---\nname: diagnostic-skill\ndescription: Portable diagnostic fixture.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
    )
    return root


def _graph(
    root: Path,
    *,
    phases: list[tuple[str, tuple[str, ...], bool]],
    graph_id: str = "root",
    input_properties: dict[str, object] | None = None,
    input_required: list[str] | None = None,
    output_properties: dict[str, object] | None = None,
    output_required: list[str] | None = None,
    llm_role: str | None = None,
) -> None:
    phase_rows = []
    for phase_id, depends_on, output in phases:
        dependencies = ", ".join(depends_on)
        phase_rows.append(
            f"  - id: {phase_id}\n"
            f"    depends_on: [{dependencies}]\n"
            f"    output: {str(output).lower()}"
        )
    role_row = f"llm_role: {llm_role}\n" if llm_role is not None else ""
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Portable diagnostic graph.
{role_row}io:
  inputs:
    {_schema(input_properties or {}, input_required)}
  outputs:
    {_schema(output_properties or {}, output_required)}
phases:
{chr(10).join(phase_rows)}
""",
    )


def _agent(
    root: Path,
    phase_id: str,
    *,
    extra_frontmatter: str = "",
    include_io: bool = True,
    input_properties: dict[str, object] | None = None,
    input_required: list[str] | None = None,
    output_properties: dict[str, object] | None = None,
    output_required: list[str] | None = None,
    body: str = "<role>Analyze</role>\n<goal>Return a useful answer.</goal>\n",
) -> Path:
    rows = ["---", f"name: {phase_id}"]
    if extra_frontmatter:
        rows.append(extra_frontmatter.rstrip())
    if include_io:
        rows.extend(
            [
                "io:",
                "  inputs:",
                f"    {_schema(input_properties or {}, input_required)}",
                "  outputs:",
                f"    {_schema(output_properties or {}, output_required)}",
            ]
        )
    rows.extend(["---", body])
    path = root / "phases" / phase_id / "AGENT.md"
    _write(path, "\n".join(rows))
    return path.parent


def _logic(root: Path, phase_id: str, *, validator: bool = False) -> Path:
    phase_dir = root / "phases" / phase_id
    _write(
        phase_dir / "LOGIC.md",
        f"""---
name: {phase_id}
io:
  inputs:
    {_schema({})}
  outputs:
    {_schema({})}
validator: {str(validator).lower()}
---
<action>run</action>
""",
    )
    _write(phase_dir / "actions" / "run.py", "def run(inputs):\n    return {}\n")
    return phase_dir


def _raise(root: Path, **kwargs: Any) -> SkillLoadError:
    with pytest.raises(SkillLoadError) as caught:
        compile_skill(root, cache=False, **kwargs)
    return caught.value


def _issues(exc: SkillLoadError) -> list[object]:
    return list(exc.compile_result.issues)


def _codes(exc: SkillLoadError) -> set[str]:
    return {str(issue.rule_id) for issue in _issues(exc)}


def test_graph_yaml_reports_multiple_independent_field_errors(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write(
        root / "graph.yaml",
        """schema_version: wrong
graph_id: INVALID_ID
description: Broken graph metadata.
io: 123
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _agent(root, "main")

    codes = _codes(_raise(root))

    assert "[F-v3-graph-schema-version-mismatch]" in codes
    assert "[F-v3-graph-name-invalid]" in codes
    assert "[F-v3-graph-io-not-object]" in codes


def test_graph_metadata_error_does_not_mask_phase_body_errors(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: INVALID_ID
description: Broken graph id.
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _agent(root, "main", body="Plain prose without required blocks.\n")

    exc = _raise(root)
    codes = _codes(exc)

    assert "[F-v3-graph-name-invalid]" in codes
    assert "[F-v3-agent-role-missing]" in codes
    assert "[F-v3-agent-goal-missing]" in codes
    assert {"graph.yaml", "phases/main/AGENT.md"} <= {
        str(issue.source_path) for issue in _issues(exc)
    }


def test_resource_tool_and_dataflow_validators_share_one_result(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _graph(
        root,
        phases=[("main", ("input",), True)],
        output_properties={"answer": {"type": "string"}},
    )
    _agent(
        root,
        "main",
        extra_frontmatter=(
            "tools:\n"
            "  - ghost_tool\n"
            "references:\n"
            "  - id: R1\n"
            "    path: refs/missing.md\n"
            "    summary: Missing reference fixture."
        ),
        input_properties={"orphan": {"type": "string"}},
        input_required=["orphan"],
        output_properties={"answer": {"type": "string"}},
    )

    codes = _codes(_raise(root))

    assert "[F-v3-resource-reference-path-invalid]" in codes
    assert "[F-v3-agent-tool-unknown]" in codes
    assert "[F-v3-graph-dataflow-source-missing]" in codes


@pytest.mark.parametrize(
    ("allowed_roles", "should_fail"),
    [({"analyst"}, False), (None, False), (set(), True), ({"writer"}, True)],
)
def test_host_role_registry_is_optional_and_fail_closed_when_injected(
    tmp_path: Path,
    allowed_roles: set[str] | None,
    should_fail: bool,
) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    _agent(root, "main", extra_frontmatter="llm_role: analyst")

    if should_fail:
        assert "[F-v3-agent-llm-role-unknown]" in _codes(
            _raise(root, allowed_roles=allowed_roles)
        )
    else:
        assert compile_skill(root, cache=False, allowed_roles=allowed_roles) is not None


def test_allowed_roles_is_provider_neutral_and_engine_has_no_gateway_import() -> None:
    signature = inspect.signature(compile_skill)
    annotation = str(signature.parameters["allowed_roles"].annotation)
    assert "set" in annotation and "str" in annotation

    engine_package = Path(__file__).resolve().parents[2] / "src" / "graph_skill_runtime"
    offenders = [
        str(path)
        for path in engine_package.rglob("*.py")
        if re.search(
            r"^\s*(from|import)\s+graph_agent_gateway\b",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    ]
    assert not offenders


def test_missing_validator_module_is_a_compile_error(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    _logic(root, "main", validator=True)

    assert "[F-v3-logic-validator-missing]" in _codes(_raise(root))


def test_validator_check_is_static_and_does_not_execute_user_code(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    phase_dir = _logic(root, "main", validator=True)
    _write(
        phase_dir / "validator.py",
        "from pathlib import Path as _P\n"
        '_P(__file__).with_name("SIDE_EFFECT.txt").write_text("boom", encoding="utf-8")\n'
        "import definitely_missing_package\n",
    )

    codes = _codes(_raise(root))

    assert "[F-v3-logic-validator-entrypoint-missing]" in codes
    assert not (phase_dir / "SIDE_EFFECT.txt").exists()


def test_agent_missing_io_is_a_compile_error(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    _agent(root, "main", include_io=False)

    assert "[F-v3-agent-io-schema-invalid]" in _codes(_raise(root))


def test_role_and_goal_are_reported_for_each_invalid_agent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _graph(
        root,
        phases=[
            ("first", ("input",), False),
            ("second", ("first",), True),
        ],
    )
    for phase_id in ("first", "second"):
        _agent(root, phase_id, body="Plain prose.\n")

    exc = _raise(root)
    codes = _codes(exc)
    paths = {str(issue.source_path) for issue in _issues(exc)}

    assert "[F-v3-agent-role-missing]" in codes
    assert "[F-v3-agent-goal-missing]" in codes
    assert "phases/first/AGENT.md" in paths
    assert "phases/second/AGENT.md" in paths


@pytest.mark.parametrize(
    ("extra_frontmatter", "expected_code", "unexpected_code"),
    [
        (
            "max_iterations: 999",
            "[F-v3-agent-max-iterations-invalid]",
            "[F-v3-agent-schema-unknown-field]",
        ),
        (
            "totally_unknown_field: 1",
            "[F-v3-agent-schema-unknown-field]",
            "[F-v3-agent-max-iterations-invalid]",
        ),
    ],
)
def test_phase_schema_uses_the_most_specific_available_code(
    tmp_path: Path,
    extra_frontmatter: str,
    expected_code: str,
    unexpected_code: str,
) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    _agent(root, "main", extra_frontmatter=extra_frontmatter)

    codes = _codes(_raise(root))

    assert expected_code in codes
    assert unexpected_code not in codes


_RESOURCE_CASES = [
    (
        "references:\n  - id: badid\n    path: refs/r.md\n    summary: ok",
        "[F-v3-resource-reference-id-invalid]",
    ),
    (
        'references:\n  - id: R1\n    path: refs/r.md\n    summary: ""',
        "[F-v3-resource-reference-summary-missing]",
    ),
    (
        'references:\n  - id: R1\n    path: ""\n    summary: ok',
        "[F-v3-resource-reference-invalid]",
    ),
    (
        "examples:\n  - id: badid\n    path: examples/e.md\n    summary: ok",
        "[F-v3-resource-example-id-invalid]",
    ),
    (
        'examples:\n  - id: E1\n    path: ""\n    summary: ok',
        "[F-v3-resource-example-path-missing]",
    ),
    (
        "examples:\n  - id: E1\n    path: examples/e.md\n    summary: ok\n    extra: 1",
        "[F-v3-resource-example-invalid]",
    ),
]


@pytest.mark.parametrize(("frontmatter", "expected_code"), _RESOURCE_CASES)
def test_resource_schema_errors_keep_their_specific_codes(
    tmp_path: Path,
    frontmatter: str,
    expected_code: str,
) -> None:
    root = _root(tmp_path)
    _graph(root, phases=[("main", ("input",), True)])
    _agent(root, "main", extra_frontmatter=frontmatter)

    codes = _codes(_raise(root))

    assert expected_code in codes
    assert "[F-v3-agent-schema-unknown-field]" not in codes


def test_error_catalog_tracks_registry_without_a_stale_numeric_freeze() -> None:
    catalog = export_error_catalog()
    items = catalog["items"]

    assert {item["code"] for item in items} == set(ERROR_REGISTRY)
    assert all(item["remediation"] for item in items)
    assert all(metadata.code == code for code, metadata in ERROR_REGISTRY.items())
    assert "[F-v3-resource-reference-path-missing]" not in ERROR_REGISTRY
    assert "[F-v3-resource-example-path-missing]" in ERROR_REGISTRY
