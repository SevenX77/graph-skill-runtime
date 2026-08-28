"""Canonical ``graph.yaml`` serialization for portable gSkills."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import yaml
from ruamel.yaml import YAML as RuamelYAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError

from graph_skill_runtime.core.manifest import (
    ArtifactDeclaration,
    GraphManifest,
    GraphPhaseRef,
    IterateSpec,
    PhaseIOSchema,
)


class GraphTopologySerializationError(ValueError):
    def __init__(self, code: str, message: str, detail: dict[str, object] | None = None) -> None:
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


def serialize_graph(manifest: GraphManifest) -> str:
    """Serialize a validated graph declaration to canonical UTF-8 YAML text."""

    document = manifest.model_dump(mode="json", exclude_none=True)
    return cast(
        str,
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False),
    )


def serialize_graph_topology_from_yaml(
    *,
    original_yaml: str,
    phases: Sequence[GraphPhaseRef],
) -> str:
    """Replace only typed phase topology after validating the complete source document."""

    try:
        yaml_reader = RuamelYAML(typ="safe")
        yaml_reader.allow_duplicate_keys = False
        loaded = yaml_reader.load(original_yaml)
        if not isinstance(loaded, dict):
            raise TypeError("graph.yaml must contain one mapping")
        manifest = GraphManifest.model_validate({**loaded, "phases": list(phases)})
    except (TypeError, ValueError, RuamelYAMLError) as exc:
        raise GraphTopologySerializationError(
            code="serializer_graph_invalid",
            message=f"graph.yaml is not a valid portable graph declaration: {exc}",
        ) from exc
    return serialize_graph(manifest)


def serialize_graph_topology(
    *,
    graph_id: str,
    description: str | None,
    io: PhaseIOSchema,
    phases: Sequence[GraphPhaseRef],
    llm_role: str | None = None,
    iterate: IterateSpec | None = None,
    artifacts: Sequence[ArtifactDeclaration] = (),
) -> str:
    """Build and serialize one complete, typed graph declaration."""

    try:
        manifest = GraphManifest(
            schema_version="gskill.graph.v1",
            graph_id=graph_id,
            description=description or "",
            llm_role=llm_role,
            io=io,
            phases=tuple(phases),
            iterate=iterate,
            artifacts=tuple(artifacts),
        )
    except ValueError as exc:
        raise GraphTopologySerializationError(
            code="serializer_graph_invalid",
            message=f"cannot serialize invalid graph topology: {exc}",
        ) from exc
    return serialize_graph(manifest)


__all__ = [
    "GraphTopologySerializationError",
    "serialize_graph",
    "serialize_graph_topology",
    "serialize_graph_topology_from_yaml",
]
