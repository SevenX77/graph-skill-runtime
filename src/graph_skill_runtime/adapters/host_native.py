"""Cooperative host-native AgentTask construction and validation."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import TypeAdapter

from graph_skill_runtime.adapters.agent_handoffs import AgentHandoffRecord
from graph_skill_runtime.core.loader import CompiledSkill, PhaseDocument
from graph_skill_runtime.core.manifest import AgentNodeAST
from graph_skill_runtime.core.result import RunResult as CoreRunResult
from graph_skill_runtime.domain.models import (
    AgentRequired,
    AgentResult,
    AgentTask,
    JsonObject,
    PhaseAddress,
    RunRequest,
    RunResult,
)

_JSON_OBJECT = TypeAdapter(JsonObject)
_TASK_NAMESPACE = uuid.UUID("d80dd15e-443b-54c9-b6d7-cb8fc4ba09c0")


class HostNativeContractError(ValueError):
    """The graph or submitted result cannot satisfy host-native semantics."""


def host_native_agent_phases(compiled: CompiledSkill) -> dict[str, PhaseDocument]:
    """Return supported root Agent phases or fail before execution begins.

    Phase 3 supports a root DAG whose Agent wait points are unambiguous. Agent
    phases nested in registry graphs, graph/phase iteration, or a parallel
    branch need an address richer than the current single task contract; those
    shapes are rejected instead of silently running an embedded model.
    """

    root_graph_id = compiled.manifest.graph_id
    nested_agents = [
        f"{graph_id}/{node.phase_name}"
        for graph_id, graph in compiled.graph_registry.items()
        if graph_id != root_graph_id
        for node in graph.nodes
        if isinstance(node.ast, AgentNodeAST)
    ]
    if nested_agents:
        raise HostNativeContractError(
            "host-native Agent phases in registry subgraphs are not supported yet: "
            + ", ".join(sorted(nested_agents))
        )

    phases = {
        node.phase_name: node
        for node in compiled.nodes
        if isinstance(node.ast, AgentNodeAST)
    }
    if not phases:
        return phases
    if compiled.manifest.iterate is not None:
        raise HostNativeContractError(
            "host-native Agent phases cannot run inside graph-level iterate"
        )
    iterated = [
        phase_id
        for phase_id, node in phases.items()
        if cast(AgentNodeAST, node.ast).iterate is not None
    ]
    if iterated:
        raise HostNativeContractError(
            "host-native Agent phase iterate is not supported yet: "
            + ", ".join(sorted(iterated))
        )

    dependencies = {
        phase.id: {item for item in phase.depends_on if item != "input"}
        for phase in compiled.manifest.phases
    }

    def ancestors(phase_id: str) -> set[str]:
        result: set[str] = set()
        pending = list(dependencies[phase_id])
        while pending:
            item = pending.pop()
            if item in result:
                continue
            result.add(item)
            pending.extend(dependencies[item])
        return result

    ancestor_map = {phase_id: ancestors(phase_id) for phase_id in dependencies}
    for agent_phase in phases:
        incomparable = [
            phase_id
            for phase_id in dependencies
            if phase_id != agent_phase
            and phase_id not in ancestor_map[agent_phase]
            and agent_phase not in ancestor_map[phase_id]
        ]
        if incomparable:
            raise HostNativeContractError(
                f"host-native Agent phase {agent_phase!r} is parallel with: "
                + ", ".join(sorted(incomparable))
            )
    return phases


def _phase_inputs(schema: dict[str, object], context: dict[str, object]) -> JsonObject:
    properties = schema.get("properties")
    if isinstance(properties, dict):
        selected = {name: context[name] for name in properties if name in context}
    else:
        selected = {
            name: value for name, value in context.items() if name != "phase_outputs"
        }
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(selected)
    except (SchemaError, JsonSchemaValidationError) as exc:
        raise HostNativeContractError(
            f"paused Agent phase inputs do not satisfy its JSON Schema: {exc.message}"
        ) from exc
    return _JSON_OBJECT.validate_python(selected)


def _instructions(node: AgentNodeAST, inputs: JsonObject) -> str:
    steps = "\n".join(
        f"{index}. {step.name}: {step.content}"
        for index, step in enumerate(node.steps, start=1)
    ) or "1. Complete the stated goal."
    protocols = "\n".join(
        f"- {protocol.content}" for protocol in node.protocols
    ) or "- Follow the host's normal safety and tool policies."
    return (
        "Execute one graph-skill Agent phase in a fresh, clean host-native "
        "subagent context. Do not run or resume the parent graph yourself.\n\n"
        f"Role\n{node.role}\n\n"
        f"Goal\n{node.goal}\n\n"
        f"Steps\n{steps}\n\n"
        f"Protocols\n{protocols}\n\n"
        "Inputs (JSON)\n"
        f"{json.dumps(inputs, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "Return exactly one JSON object that validates against this output "
        "schema; do not wrap it in Markdown:\n"
        f"{json.dumps(node.io.outputs, ensure_ascii=False, indent=2, sort_keys=True)}"
    )


def _allowed_paths(request: RunRequest, node: AgentNodeAST) -> tuple[str, ...]:
    skill_root = Path(request.profile.skill_root).resolve(strict=False)
    state_root = Path(request.profile.state_root).resolve(strict=False)
    if request.profile.profile.permissions.filesystem == "skill-and-state":
        return (str(skill_root), str(state_root))
    declared = [item.path for item in node.references]
    declared.extend(item.path for item in node.examples)
    result: list[str] = []
    for relative in declared:
        candidate = (skill_root / relative).resolve(strict=False)
        if not candidate.is_relative_to(skill_root):
            raise HostNativeContractError(
                f"declared Agent resource escapes the skill root: {relative}"
            )
        result.append(str(candidate))
    return tuple(dict.fromkeys(result))


def _deadline(request: RunRequest, address: PhaseAddress) -> str | None:
    override = next(
        (item for item in request.node_overrides if item.address == address),
        None,
    )
    if override is None or override.timeout_seconds is None:
        return None
    return (datetime.now(UTC) + timedelta(seconds=override.timeout_seconds)).isoformat()


def build_agent_handoff(
    request: RunRequest,
    compiled: CompiledSkill,
    phases: dict[str, PhaseDocument],
    result: CoreRunResult,
    *,
    mode: Literal["run", "resume"],
) -> AgentHandoffRecord:
    """Turn a durable graph pause into one durable public AgentTask."""

    paused = result.paused_at
    if paused is None or paused.reason != "breakpoint":
        raise HostNativeContractError("the engine did not stop at an Agent phase")
    phase = phases.get(paused.phase_name)
    if phase is None or not isinstance(phase.ast, AgentNodeAST):
        raise HostNativeContractError(
            f"engine paused before non-Agent phase {paused.phase_name!r}"
        )
    if not paused.checkpoint_id:
        raise HostNativeContractError("Agent pause has no durable checkpoint id")

    address = PhaseAddress(
        graph_id=compiled.manifest.graph_id,
        phase_id=paused.phase_name,
    )
    context = cast(dict[str, object], result.context)
    inputs = _phase_inputs(cast(dict[str, object], phase.ast.io.inputs), context)
    identity = "\n".join(
        (
            request.run_id,
            address.value,
            paused.checkpoint_id,
            paused.checkpoint_ns or "",
        )
    )
    task_id = str(uuid.uuid5(_TASK_NAMESPACE, identity))
    tools = tuple(
        dict.fromkeys(
            [
                *phase.ast.tools,
                *(item.name for item in phase.ast.subagents),
                *(item.name for item in phase.ast.subgraphs),
            ]
        )
    )
    task = AgentTask(
        task_id=task_id,
        run_id=request.run_id,
        address=address,
        instructions=_instructions(phase.ast, inputs),
        inputs=inputs,
        output_schema=_JSON_OBJECT.validate_python(phase.ast.io.outputs),
        allowed_tools=tools,
        allowed_paths=_allowed_paths(request, phase.ast),
        network=request.profile.profile.permissions.network,
        deadline=_deadline(request, address),
        required_capabilities=request.profile.profile.required_capabilities,
    )
    checkpoint_ref = f"gskill-handoff-v1:{task_id}"
    required = AgentRequired(task=task, checkpoint_ref=checkpoint_ref)
    response = RunResult(
        status="agent_required",
        run_id=request.run_id,
        mode=mode,
        request=request,
        outputs=_JSON_OBJECT.validate_python(result.context),
        trace_path=str(result.trace_path) if result.trace_path is not None else None,
        agent_required=required,
    )
    return AgentHandoffRecord(
        checkpoint_ref=checkpoint_ref,
        task=task,
        checkpoint_id=paused.checkpoint_id,
        checkpoint_ns=paused.checkpoint_ns or "",
        required_response=response,
    )


def validate_agent_result(record: AgentHandoffRecord, result: AgentResult) -> None:
    """Reject a malformed result without consuming the durable AgentTask."""

    if result.task_id != record.task.task_id:
        raise HostNativeContractError(
            f"AgentResult task_id {result.task_id!r} does not match "
            f"task {record.task.task_id!r}"
        )
    if result.status != "completed":
        return
    assert result.output is not None
    try:
        Draft202012Validator.check_schema(record.task.output_schema)
        Draft202012Validator(record.task.output_schema).validate(result.output)
    except (SchemaError, JsonSchemaValidationError) as exc:
        raise HostNativeContractError(
            f"AgentResult output does not satisfy the task schema: {exc.message}"
        ) from exc
