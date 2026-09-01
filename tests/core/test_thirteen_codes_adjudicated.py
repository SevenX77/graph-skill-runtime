"""The registry holds no code without an emitter; wired seams actually fire.

Adjudication 2026-08-19 (decision doc
`.kiro/specs/decision-2026-08-19-an-error-code-either-fires-or-leaves.md`):
13 registry codes had no production emitter. Eleven leave the registry — nine
describe conditions covered by live codes, unrepresentable in MVP1, or
contradicting pinned behavior, and the two subgraph-io 1:1 codes pin a gate
the MVP1 design explicitly removed (skill-syntax mvp1-alignment §3.4 「父图和
子图 IO 不需要字段全集一一相等」, gate deleted by commit cad7dbc0; they had
only been retained to keep the old 99-code count, which this adjudication
abandons). Two describe real unchecked compile gates — they get emitters,
pinned here by building the violating skill and compiling it.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.error_registry import ERROR_REGISTRY
from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.skill_resolver_protocol import SkillResolutionError

_DELETED = [
    "[F-v3-graph-phase-dir-missing]",
    "[F-v3-agent-name-invalid]",
    "[F-v3-logic-name-invalid]",
    "[F-v3-mention-type-unknown]",
    "[F-v3-mention-unused-registry-entry]",
    "[F-v3-reference-reader-input-invalid]",
    "[F-v3-reference-reader-output-invalid]",
    "[F-v3-cognitive-slot-render-failed]",
    "[F-v3-cognitive-output-schema-render-failed]",
    "[F-v3-subgraph-io-mismatch]",
    "[F-v3-subgraph-io-schema-incompatible]",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _schema_yaml(properties: dict[str, Any], *, required: list[str] | None = None) -> str:
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    return json.dumps(schema, ensure_ascii=False, indent=4).replace("\n", "\n    ")


def _write_graph(
    root: Path,
    *,
    graph_id: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    required_inputs: list[str] | None = None,
) -> None:
    phase_id = "work" if graph_id == "root" else "inner"
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Exercise the portable subgraph seam.
io:
  inputs:
    {_schema_yaml(inputs, required=required_inputs)}
  outputs:
    {_schema_yaml(outputs)}
phases:
  - id: {phase_id}
    depends_on: [input]
    output: true
""",
    )


def _write_logic_phase(
    root: Path,
    phase_id: str,
    *,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    required: list[str] | None,
    action_body: str,
) -> None:
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
---
<action>{phase_id}</action>
""",
    )
    _write(
        root / "phases" / phase_id / "actions" / f"{phase_id}.py",
        dedent(action_body).lstrip(),
    )


def test_no_adjudicated_dead_code_remains_registered() -> None:
    remaining = [code for code in _DELETED if code in ERROR_REGISTRY]
    assert remaining == [], (
        "these codes were adjudicated OUT (no emitter, condition covered "
        f"elsewhere or unrepresentable): {remaining}"
    )


def _child(root: Path, in_field: str, out_field: str) -> None:
    _write_graph(
        root,
        graph_id="child",
        inputs={in_field: {"type": "string"}},
        outputs={out_field: {"type": "string"}},
        required_inputs=[in_field],
    )
    _write_logic_phase(
        root,
        "inner",
        inputs={in_field: {"type": "string"}},
        outputs={out_field: {"type": "string"}},
        required=[in_field],
        action_body=f"""
            def inner(inputs):
                return {{"{out_field}": inputs["{in_field}"]}}
        """,
    )


def _subgraph_md(
    phase_dir: Path, *, graph_id: str, io_yaml: str, name: str = "work"
) -> None:
    phase_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {name}",
        f"graph: {graph_id}",
        *io_yaml.strip().split(chr(10)),
        "---",
    ]
    (phase_dir / "SUBGRAPH.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def _parent(parent: Path) -> Path:
    root = parent / "seam-parent"
    _write(
        root / "SKILL.md",
        """---
name: seam-parent
description: Exercise the portable subgraph seam.
metadata:
  gskill: gskill.graph.v1
---
""",
    )
    _write_graph(
        root,
        graph_id="root",
        inputs={"text": {"type": "string"}},
        outputs={"result": {"type": "string"}},
        required_inputs=["text"],
    )
    return root


def _codes_of(exc: SkillLoadError) -> set[str]:
    issues = getattr(getattr(exc, "compile_result", None), "issues", None) or []
    codes = {issue.rule_id for issue in issues}
    payload = getattr(exc, "payload", None)
    if payload is not None and getattr(payload, "code", None):
        codes.add(payload.code)
    return codes


IO_OK = """io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: string}
  outputs:
    type: object
    required: [result]
    properties:
      result: {type: string}"""


class TestSubgraphSeamGates:
    def test_a_non_one_to_one_seam_compiles_by_design(
        self, tmp_path: Path, mock_skill_resolver: object
    ) -> None:
        """Parent SUBGRAPH declares an output the child does not produce AND a
        same-name input with a different type — and that COMPILES, on purpose.

        skill-syntax mvp1-alignment §3.4: 父图和子图 IO 不需要字段全集一一相等;
        the compile gate was removed by cad7dbc0 (StateMapper guards the seam at
        runtime via [F-v3-runtime-state-mapping-failed]). This pin keeps the
        adjudication from re-wiring the two deleted 1:1 codes by accident.
        """
        root = _parent(tmp_path)
        _child(root / "graphs" / "child", "text", "result")
        io = """io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: number}
  outputs:
    type: object
    required: [result, phantom]
    properties:
      result: {type: string}
      phantom: {type: string}"""
        _subgraph_md(root / "phases" / "work", graph_id="child", io_yaml=io)

        compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)

    def test_a_matching_seam_still_compiles(
        self, tmp_path: Path, mock_skill_resolver: object
    ) -> None:
        root = _parent(tmp_path)
        _child(root / "graphs" / "child", "text", "result")
        _subgraph_md(root / "phases" / "work", graph_id="child", io_yaml=IO_OK)

        compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)

    def test_an_invalid_subgraph_name_is_fatal(
        self, tmp_path: Path, mock_skill_resolver: object
    ) -> None:
        """A display name may contain spaces, but it must not be empty."""
        root = _parent(tmp_path)
        _child(root / "graphs" / "child", "text", "result")
        _subgraph_md(
            root / "phases" / "work",
            graph_id="child",
            io_yaml=IO_OK,
            name="",
        )

        with pytest.raises(SkillLoadError) as exc_info:
            compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)

        assert "[F-v3-subgraph-name-invalid]" in _codes_of(exc_info.value)


class TestResolverInterfaceGate:
    def test_a_resolver_without_resolve_skill_fails_at_the_boundary(
        self, tmp_path: Path
    ) -> None:
        """Fail fast at the compile entry instead of an AttributeError somewhere
        deep once a subgraph finally needs the resolver.

        Resolver-domain errors are caller misconfiguration, not skill content:
        they surface as SkillResolutionError, the same seam
        [F-v3-resolver-missing] already uses, not as aggregated SkillLoadError
        diagnostics.
        """
        root = _parent(tmp_path)
        _child(root / "graphs" / "child", "text", "result")
        _subgraph_md(root / "phases" / "work", graph_id="child", io_yaml=IO_OK)

        class NotAResolver:
            pass

        with pytest.raises(SkillResolutionError) as exc_info:
            compile_skill(root, cache=False, skill_resolver=NotAResolver())

        assert exc_info.value.code == "[F-v3-resolver-interface-invalid]"
