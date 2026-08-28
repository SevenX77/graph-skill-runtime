from __future__ import annotations

import pytest
import yaml

from graph_skill_runtime.core.graph_serializer import (
    GraphTopologySerializationError,
    serialize_graph_topology_from_yaml,
)
from graph_skill_runtime.core.manifest import GraphPhaseRef


def _phase(phase_id: str, depends_on: list[str], *, output: bool) -> GraphPhaseRef:
    return GraphPhaseRef(id=phase_id, depends_on=tuple(depends_on), output=output)


_ORIGINAL = """schema_version: gskill.graph.v1
graph_id: research-pipeline
description: Research pipeline
llm_role: analyst
io:
  inputs:
    type: object
    properties:
      topic: {type: string}
  outputs:
    type: object
    properties:
      report: {type: string}
phases:
  - id: draft
    depends_on: [input]
    output: true
iterate:
  mode: batch
  over: $.items
  item_var: item
  concurrency: 2
artifacts:
  - artifact_id: report
    stem: report
    fields: [report]
    mode: single
    format: md
"""


def test_typed_round_trip_replaces_only_topology_and_canonicalizes_yaml() -> None:
    rendered = serialize_graph_topology_from_yaml(
        original_yaml=_ORIGINAL,
        phases=(
            _phase("draft", ["input"], output=False),
            _phase("review", ["draft"], output=True),
        ),
    )
    document = yaml.safe_load(rendered)

    assert document["graph_id"] == "research-pipeline"
    assert document["description"] == "Research pipeline"
    assert document["llm_role"] == "analyst"
    assert document["io"]["outputs"]["properties"] == {"report": {"type": "string"}}
    assert document["iterate"]["concurrency"] == 2
    assert document["artifacts"][0]["artifact_id"] == "report"
    assert document["phases"] == [
        {"id": "draft", "depends_on": ["input"], "output": False},
        {"id": "review", "depends_on": ["draft"], "output": True},
    ]
    assert serialize_graph_topology_from_yaml(
        original_yaml=rendered,
        phases=(
            _phase("draft", ["input"], output=False),
            _phase("review", ["draft"], output=True),
        ),
    ) == rendered


def test_unknown_graph_field_is_rejected_instead_of_preserved() -> None:
    with pytest.raises(GraphTopologySerializationError, match="extra"):
        serialize_graph_topology_from_yaml(
            original_yaml=_ORIGINAL + "x-studio: {zoom: 0.8}\n",
            phases=(_phase("draft", ["input"], output=True),),
        )


def test_duplicate_yaml_key_is_rejected() -> None:
    duplicate = _ORIGINAL.replace(
        "description: Research pipeline\n",
        "description: First\ndescription: Second\n",
    )

    with pytest.raises(GraphTopologySerializationError, match="duplicate"):
        serialize_graph_topology_from_yaml(
            original_yaml=duplicate,
            phases=(_phase("draft", ["input"], output=True),),
        )
