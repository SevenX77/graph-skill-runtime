"""Typed contracts for portable graph declarations and phase documents."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from graph_skill_runtime.core.skill_resolver_protocol import SKILL_ID_PATTERN
from graph_skill_runtime.gskill_version import (
    GSKILL_METADATA_KEY,
    GSKILL_SCHEMA_VERSION,
    GSkillSchemaVersion,
)

AGENT_SKILL_NAME_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
GRAPH_ID_PATTERN = AGENT_SKILL_NAME_PATTERN
PHASE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"


class RootSkillManifest(BaseModel):
    """Agent Skills metadata from the business skill's root ``SKILL.md``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1, max_length=64, pattern=AGENT_SKILL_NAME_PATTERN)
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = Field(default=None, min_length=1)
    compatibility: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict[str, str] = Field(default_factory=dict)
    allowed_tools: str | None = Field(default=None, alias="allowed-tools", min_length=1)

    @model_validator(mode="after")
    def _require_gskill_identity(self) -> RootSkillManifest:
        marker = self.metadata.get(GSKILL_METADATA_KEY)
        if marker != GSKILL_SCHEMA_VERSION:
            raise ValueError(
                f"metadata.{GSKILL_METADATA_KEY} must equal {GSKILL_SCHEMA_VERSION!r}"
            )
        return self


class GraphPhaseRef(BaseModel):
    """One phase and its explicit incoming topology edges in ``graph.yaml``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=PHASE_ID_PATTERN)
    depends_on: tuple[str, ...] = Field(min_length=1)
    output: bool

    @model_validator(mode="after")
    def _dependencies_are_unique(self) -> GraphPhaseRef:
        if self.id == "input":
            raise ValueError("phase id 'input' is reserved for the graph input sentinel")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError(f"phase {self.id!r} repeats a depends_on entry")
        if "input" in self.depends_on and len(self.depends_on) != 1:
            raise ValueError(f"phase {self.id!r} must use the input sentinel by itself")
        invalid = [
            dependency
            for dependency in self.depends_on
            if dependency != "input" and re.fullmatch(PHASE_ID_PATTERN, dependency) is None
        ]
        if invalid:
            raise ValueError(f"phase {self.id!r} has invalid dependencies: {', '.join(invalid)}")
        return self


class ArtifactDeclaration(BaseModel):
    """Portable definition of one artifact a run may request by stable id."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=PHASE_ID_PATTERN)
    stem: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    fields: tuple[str, ...] = Field(min_length=1)
    mode: Literal["single", "per-item"]
    format: Literal["json", "md"]

    @field_validator("fields")
    @classmethod
    def _fields_are_nonempty_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not field_name.strip() for field_name in value):
            raise ValueError("artifact fields must not contain blank names")
        if len(set(value)) != len(value):
            raise ValueError("artifact fields must be unique")
        return value


class PhaseIOSchema(BaseModel):
    """Inline JSON Schema contract for a graph or phase boundary."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(..., min_length=1)
    outputs: dict[str, Any] = Field(..., min_length=1)


class AgentRegistryItem(BaseModel):
    """Named subgraph binding available to an Agent body."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    graph: str = Field(pattern=GRAPH_ID_PATTERN)
    description: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _validate_subgraph(cls, data: Any) -> Any:
        import re

        if not isinstance(data, dict):
            return data
        allowed = {"name", "graph", "description"}
        for k in data:
            if k not in allowed:
                raise ValueError(f"[F-v3-agent-subgraph-invalid] Extra field {k!r} not allowed in subgraph spec")
        name = data.get("name")
        if name is None or not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError("[F-v3-agent-subgraph-invalid] Subgraph name is missing or invalid")
        graph = data.get("graph")
        if graph is None or not isinstance(graph, str) or not graph:
            raise ValueError("[F-v3-agent-subgraph-invalid] Subgraph graph id is missing or invalid")
        description = data.get("description")
        if description is None or not isinstance(description, str) or len(description) == 0:
            raise ValueError("[F-v3-agent-subgraph-invalid] Subgraph description is missing or invalid")
        return data


class ReferenceSpec(BaseModel):
    """Reference resource declared on an Agent."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z][A-Za-z0-9_-]*$")
    path: str = Field(min_length=1)
    summary: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _validate_reference(cls, data: Any) -> Any:
        import re

        if not isinstance(data, dict):
            return data
        allowed = {"id", "path", "summary"}
        for k in data:
            if k not in allowed:
                raise ValueError(f"[F-v3-resource-reference-invalid] Extra field {k!r} not allowed in reference spec")
        val_id = data.get("id")
        if val_id is None or not isinstance(val_id, str) or not re.match(r"^[A-Z][A-Za-z0-9_-]*$", val_id):
            raise ValueError("[F-v3-resource-reference-id-invalid] Reference id is missing or invalid")
        path = data.get("path")
        if path is None or not isinstance(path, str) or len(path) == 0:
            raise ValueError("[F-v3-resource-reference-invalid] Reference path is missing or invalid")
        summary = data.get("summary")
        if summary is None or not isinstance(summary, str) or len(summary) == 0:
            raise ValueError("[F-v3-resource-reference-summary-missing] Reference summary is missing or invalid")
        return data


class ExampleSpec(BaseModel):
    """Document example declared on an Agent frontmatter."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z][A-Za-z0-9_-]*$")
    path: str = Field(min_length=1)
    summary: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _validate_example(cls, data: Any) -> Any:
        import re

        if not isinstance(data, dict):
            return data
        allowed = {"id", "path", "summary"}
        for k in data:
            if k not in allowed:
                raise ValueError(f"[F-v3-resource-example-invalid] Extra field {k!r} not allowed in example spec")
        val_id = data.get("id")
        if val_id is None or not isinstance(val_id, str) or not re.match(r"^[A-Z][A-Za-z0-9_-]*$", val_id):
            raise ValueError("[F-v3-resource-example-id-invalid] Example id is missing or invalid")
        path = data.get("path")
        if path is None or not isinstance(path, str) or len(path) == 0:
            raise ValueError("[F-v3-resource-example-path-missing] Example path is missing or invalid")
        summary = data.get("summary")
        if summary is None or not isinstance(summary, str) or len(summary) == 0:
            raise ValueError("[F-v3-resource-example-summary-missing] Example summary is missing or invalid")
        return data


class AgentExample(BaseModel):
    """One inline Agent example parsed from body XML."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z][A-Za-z0-9_-]*$")
    content: str = Field(min_length=1)


class AgentStep(BaseModel):
    """One ordered Agent step parsed from body XML."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1)
    content: str = Field(min_length=1)


class AgentProtocol(BaseModel):
    """One Agent protocol parsed from body XML."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    content: str = Field(min_length=1)


class SubagentSpec(BaseModel):
    """External Agent Skill declared as a callable tool on an AGENT phase."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    target_skill: str = Field(pattern=SKILL_ID_PATTERN)
    description: str = Field(min_length=1)


class IterateAccumulateSpec(BaseModel):
    """Declarative loop accumulator spec."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    var: str = Field(min_length=1)
    init: Any
    from_: str = Field(alias="from", min_length=1)
    merge: Literal["append", "extend", "merge", "replace"]


class IterateSpec(BaseModel):
    """Unified MVP1 iterate declaration for graph or phase runtime."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["batch", "loop"]
    over: str = Field(min_length=1)
    item_var: str = Field(min_length=1)
    range: tuple[int, int] | None = None
    concurrency: int = Field(default=1, ge=1)
    accumulate: IterateAccumulateSpec | None = None

    @model_validator(mode="after")
    def _mode_contract_is_complete(self) -> IterateSpec:
        if self.range is not None and self.range[0] > self.range[1]:
            raise ValueError("iterate range start must not exceed its end")
        if self.mode == "loop" and self.accumulate is None:
            raise ValueError("loop iterate requires accumulate")
        if self.mode == "batch" and self.accumulate is not None:
            raise ValueError("batch iterate does not accept accumulate")
        return self


class GraphManifest(BaseModel):
    """One root or registry graph parsed from ``graph.yaml``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: GSkillSchemaVersion
    graph_id: str = Field(min_length=1, max_length=64, pattern=GRAPH_ID_PATTERN)
    description: str = Field(min_length=1)
    llm_role: str | None = Field(default=None, min_length=1)
    io: PhaseIOSchema
    phases: tuple[GraphPhaseRef, ...] = Field(min_length=1)
    iterate: IterateSpec | None = None
    artifacts: tuple[ArtifactDeclaration, ...] = ()

    @model_validator(mode="after")
    def _local_identifiers_are_unique(self) -> GraphManifest:
        phase_ids = [phase.id for phase in self.phases]
        if len(set(phase_ids)) != len(phase_ids):
            raise ValueError("graph phase ids must be unique")
        if len({phase_id.casefold() for phase_id in phase_ids}) != len(phase_ids):
            raise ValueError("graph phase ids must be unique without relying on case")
        if not any(phase.output for phase in self.phases):
            raise ValueError("graph must declare at least one output phase")
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("artifact ids must be unique")
        return self


class _BaseNodeAST(BaseModel):
    """Fields shared by all portable phase node AST variants."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    raw_blocks: dict[str, str] = Field(default_factory=dict)
    allow_sequential_overwrite: list[str] = Field(default_factory=list)
    iterate: IterateSpec | None = None

    @field_validator("allow_sequential_overwrite")
    @classmethod
    def _overwrite_fields_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("allow_sequential_overwrite fields must be unique")
        return value


class LogicNodeAST(_BaseNodeAST):
    """Deterministic Python phase node parsed from ``LOGIC.md``."""

    mode: Literal["logic"]
    io: PhaseIOSchema
    actions: list[str] = Field(default_factory=list, min_length=1)
    validator: StrictBool = False

    @field_validator("actions")
    @classmethod
    def _actions_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("logic actions must be unique")
        return value


class SubgraphNodeAST(_BaseNodeAST):
    """Subgraph delegation phase node parsed from ``SUBGRAPH.md``."""

    mode: Literal["subgraph"]
    graph: str = Field(pattern=GRAPH_ID_PATTERN)
    io: PhaseIOSchema
    # Authoring flag; not an executable validator module path.
    validator: StrictBool = False


class AgentNodeAST(_BaseNodeAST):
    """Agent phase node parsed from internal ``AGENT.md``."""

    mode: Literal["agent"]
    role: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    steps: list[AgentStep] = Field(default_factory=list)
    protocols: list[AgentProtocol] = Field(default_factory=list)
    io: PhaseIOSchema
    # Authoring flag; not an executable validator module path.
    validator: StrictBool = False
    tools: list[str] = Field(default_factory=list)
    subagents: list[SubagentSpec] = Field(default_factory=list)
    subgraphs: list[AgentRegistryItem] = Field(default_factory=list)
    references: list[ReferenceSpec] = Field(default_factory=list)
    examples: list[ExampleSpec] = Field(default_factory=list)
    examples_inline: list[AgentExample] = Field(default_factory=list)
    max_iterations: int = Field(default=10, ge=1, le=50)
    llm_role: str | None = None
    # Round 8 opt-in mining (migration decision 2026-08-15 §3.4): phases keep
    # strong isolation unless they declare the context planes they may read —
    # "working_memory" mounts query_working_memory, "artifact" mounts
    # read_artifact. The Literal makes any other value a compile diagnostic.
    context_access: list[Literal["working_memory", "artifact"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _registries_are_unique(self) -> AgentNodeAST:
        registries: dict[str, list[str]] = {
            "tools": list(self.tools),
            "subagents": [item.name for item in self.subagents],
            "subgraphs": [item.name for item in self.subgraphs],
            "references": [item.id for item in self.references],
            "examples": [item.id for item in self.examples],
            "context_access": list(self.context_access),
        }
        for name, values in registries.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} entries must be unique")
        return self

    @field_validator("max_iterations", mode="before")
    @classmethod
    def _validate_max_iterations(cls, value: Any) -> Any:
        if value is not None:
            # Type conversion and range are two independent defects with two
            # different causes; the range check must not sit inside the
            # int(value) try block, or its own except (ValueError, TypeError)
            # swallows the "out of range" ValueError it just raised and
            # re-reports it as "not an integer" — wrong for an input (e.g.
            # -1) that IS a valid integer.
            try:
                val = int(value)
            except (ValueError, TypeError) as err:
                raise ValueError("[F-v3-agent-max-iterations-invalid] max_iterations must be an integer") from err
            if not (1 <= val <= 50):
                raise ValueError("[F-v3-agent-max-iterations-invalid] max_iterations must be between 1 and 50")
        return value

    # Priority switch: true makes the graph-level default llm_role win over
    # this node's own llm_role, WITHOUT rewriting/erasing the node value
    # (portable gSkill v1 contract §5.2).
    use_graph_llm_role: bool = False
    system_prompt: str = ""

    @model_validator(mode="after")
    def _render_system_prompt(self) -> AgentNodeAST:
        if not self.system_prompt:
            step_lines = "\n".join(f"- {step.name}: {step.content}" for step in self.steps)
            protocol_lines = "\n".join(f"- {protocol.id}: {protocol.content}" for protocol in self.protocols)
            parts = [f"Role: {self.role}", f"Goal: {self.goal}"]
            if step_lines:
                parts.append("Steps:\n" + step_lines)
            if protocol_lines:
                parts.append("Protocols:\n" + protocol_lines)
            self.system_prompt = "\n\n".join(parts)
        return self


# Conventional fallback role looked up in the host's role registry when
# neither the node nor the graph names one (portable gSkill v1 contract §5.2).
DEFAULT_LLM_ROLE = "graph_skill_runtime"


def effective_llm_role(phase_ast: AgentNodeAST, graph_llm_role: str | None) -> str:
    """Resolve the role an agent phase actually runs as.

    ``use_graph_llm_role`` on -> the graph-level default wins (the node's own
    ``llm_role`` stays in the file but is inactive). Off -> the node's own
    value wins, inheriting the graph default when the node has none. When
    neither names a role, fall back to ``DEFAULT_LLM_ROLE``.
    """
    if phase_ast.use_graph_llm_role:
        return graph_llm_role or DEFAULT_LLM_ROLE
    return phase_ast.llm_role or graph_llm_role or DEFAULT_LLM_ROLE


PhaseAST = Annotated[
    LogicNodeAST | SubgraphNodeAST | AgentNodeAST,
    Field(discriminator="mode"),
]


__all__ = [
    "AgentNodeAST",
    "AgentExample",
    "AgentProtocol",
    "AgentRegistryItem",
    "AgentStep",
    "ArtifactDeclaration",
    "ExampleSpec",
    "GraphManifest",
    "GraphPhaseRef",
    "IterateAccumulateSpec",
    "IterateSpec",
    "LogicNodeAST",
    "PhaseAST",
    "PhaseIOSchema",
    "ReferenceSpec",
    "RootSkillManifest",
    "SubagentSpec",
    "SubgraphNodeAST",
]
