"""Read-only human topology projections from portable graph declarations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from graph_skill_runtime.core.authored_text import read_authored_text
from graph_skill_runtime.core.parser import parse_markdown_parts

_PHASE_FILE_TO_MODE = {
    "LOGIC.md": "logic",
    "SUBGRAPH.md": "subgraph",
    "AGENT.md": "agent",
}


@dataclass(frozen=True)
class GraphTopologyProjection:
    phases: list[str]
    graph_topology: list[dict[str, object]]


@dataclass(frozen=True)
class ChildGraphTopologyProjection(GraphTopologyProjection):
    path: str
    name: str
    description: str


class SubgraphTopologyProjectionError(ValueError):
    def __init__(self, code: str, reason: str, graph_id: str) -> None:
        self.code = code
        self.reason = reason
        self.graph_id = graph_id
        super().__init__(reason)


def load_graph_topology_projection(graph_dir: Path) -> GraphTopologyProjection:
    graph_path = graph_dir / "graph.yaml"
    if not graph_path.is_file():
        return GraphTopologyProjection(phases=[], graph_topology=[])
    try:
        document = yaml.safe_load(read_authored_text(graph_path))
    except (OSError, yaml.YAMLError):
        return GraphTopologyProjection(phases=[], graph_topology=[])
    if not isinstance(document, dict):
        return GraphTopologyProjection(phases=[], graph_topology=[])

    phase_rows = document.get("phases")
    if not isinstance(phase_rows, list):
        return GraphTopologyProjection(phases=[], graph_topology=[])
    topology: list[dict[str, object]] = []
    for raw_phase in phase_rows:
        if not isinstance(raw_phase, dict) or not isinstance(raw_phase.get("id"), str):
            continue
        phase_id = str(raw_phase["id"])
        mode = phase_mode_for(graph_dir, phase_id)
        row: dict[str, object] = {
            "id": phase_id,
            "src": f"phases/{phase_id}",
            "depends_on": _string_list(raw_phase.get("depends_on")),
            "mode": mode,
        }
        if mode == "subgraph":
            target = read_subgraph_graph_id(graph_dir, phase_id)
            if target is not None:
                row["graph"] = target
        if raw_phase.get("output") is True:
            row["output"] = True
        topology.append(row)
    return GraphTopologyProjection(
        phases=[str(row["id"]) for row in topology],
        graph_topology=topology,
    )


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def phase_mode_for(graph_dir: Path, phase_id: str) -> str:
    phase_dir = graph_dir / "phases" / phase_id
    for filename, mode in _PHASE_FILE_TO_MODE.items():
        if (phase_dir / filename).is_file():
            return mode
    return ""


def read_subgraph_graph_id(graph_dir: Path, phase_id: str) -> str | None:
    phase_path = graph_dir / "phases" / phase_id / "SUBGRAPH.md"
    if not phase_path.is_file():
        return None
    frontmatter, _body, _line_meta = parse_markdown_parts(phase_path)
    target = frontmatter.get("graph")
    return target.strip() if isinstance(target, str) and target.strip() else None


def load_child_graph_topology_projection(
    *,
    parent_skill_dir: Path,
    graph_id: str,
) -> ChildGraphTopologyProjection:
    graph_dir = resolve_registry_graph_root(parent_skill_dir=parent_skill_dir, graph_id=graph_id)
    document = yaml.safe_load(read_authored_text(graph_dir / "graph.yaml"))
    projection = load_graph_topology_projection(graph_dir)
    description = document.get("description") if isinstance(document, dict) else ""
    return ChildGraphTopologyProjection(
        path=str(graph_dir),
        name=graph_id,
        description=description if isinstance(description, str) else "",
        phases=projection.phases,
        graph_topology=projection.graph_topology,
    )


def resolve_registry_graph_root(*, parent_skill_dir: Path, graph_id: str) -> Path:
    expected_parent = parent_skill_dir.resolve() / "graphs"
    graph_dir = (expected_parent / graph_id).resolve()
    try:
        graph_dir.relative_to(expected_parent)
    except ValueError as exc:
        raise SubgraphTopologyProjectionError(
            "SUBGRAPH_ID_INVALID", "graph id escapes the flat registry", graph_id
        ) from exc
    if graph_dir.name != graph_id or not (graph_dir / "graph.yaml").is_file():
        raise SubgraphTopologyProjectionError(
            "SUBGRAPH_ID_NOT_FOUND", "graph id is not present in the flat registry", graph_id
        )
    return graph_dir


__all__ = [
    "ChildGraphTopologyProjection",
    "GraphTopologyProjection",
    "SubgraphTopologyProjectionError",
    "load_child_graph_topology_projection",
    "load_graph_topology_projection",
    "phase_mode_for",
    "read_subgraph_graph_id",
    "resolve_registry_graph_root",
]
