from __future__ import annotations

import pytest
import yaml

from graph_skill_runtime.core.graph_serializer import (
    GraphTopologySerializationError,
    serialize_graph_topology,
)
from graph_skill_runtime.core.manifest import ArtifactDeclaration, GraphPhaseRef, PhaseIOSchema

_IO = PhaseIOSchema(
    inputs={"type": "object", "properties": {}},
    outputs={"type": "object", "properties": {"report": {"type": "string"}}},
)


def _phase(phase_id: str, depends_on: list[str], *, output: bool = False) -> GraphPhaseRef:
    return GraphPhaseRef(id=phase_id, depends_on=tuple(depends_on), output=output)


def _serialize(phases: list[GraphPhaseRef]) -> dict[str, object]:
    return yaml.safe_load(
        serialize_graph_topology(
            graph_id="test-graph",
            description="Typed topology fixture.",
            io=_IO,
            phases=phases,
        )
    )


def test_linear_chain_emits_explicit_dependencies_and_output() -> None:
    document = _serialize(
        [_phase("a", ["input"]), _phase("b", ["a"]), _phase("c", ["b"], output=True)]
    )

    assert document["schema_version"] == "gskill.graph.v1"
    assert document["phases"] == [
        {"id": "a", "depends_on": ["input"], "output": False},
        {"id": "b", "depends_on": ["a"], "output": False},
        {"id": "c", "depends_on": ["b"], "output": True},
    ]


def test_diamond_fan_in_and_multiple_outputs_remain_explicit() -> None:
    document = _serialize(
        [
            _phase("a", ["input"]),
            _phase("b", ["a"], output=True),
            _phase("c", ["a"], output=True),
            _phase("d", ["b", "c"], output=True),
        ]
    )

    rows = {row["id"]: row for row in document["phases"]}
    assert rows["b"]["depends_on"] == ["a"]
    assert rows["c"]["depends_on"] == ["a"]
    assert rows["d"]["depends_on"] == ["b", "c"]
    assert {phase_id for phase_id, row in rows.items() if row["output"]} == {"b", "c", "d"}


def test_topology_without_an_output_cannot_be_serialized() -> None:
    with pytest.raises(GraphTopologySerializationError):
        _serialize([_phase("a", ["input"])])


def test_phase_without_a_dependency_cannot_be_represented() -> None:
    with pytest.raises(ValueError):
        _phase("a", [], output=True)


def test_cycle_can_be_serialized_for_bundle_compile_to_diagnose() -> None:
    document = _serialize(
        [_phase("a", ["b"], output=True), _phase("b", ["a"], output=True)]
    )
    assert document["phases"] == [
        {"id": "a", "depends_on": ["b"], "output": True},
        {"id": "b", "depends_on": ["a"], "output": True},
    ]


def test_root_artifact_declaration_is_serialized_as_typed_data() -> None:
    rendered = serialize_graph_topology(
        graph_id="artifact-graph",
        description="Artifact graph.",
        io=_IO,
        phases=[_phase("done", ["input"], output=True)],
        artifacts=[
            ArtifactDeclaration(
                artifact_id="report",
                stem="report",
                fields=("report",),
                mode="single",
                format="md",
            )
        ],
    )

    assert yaml.safe_load(rendered)["artifacts"] == [
        {
            "artifact_id": "report",
            "stem": "report",
            "fields": ["report"],
            "mode": "single",
            "format": "md",
        }
    ]
