"""Versioned contracts shared by the SDK, CLI, MCP server, and adapters."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal, Never, Self, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

JsonObject: TypeAlias = dict[str, JsonValue]
Identifier: TypeAlias = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
CallbackEventType: TypeAlias = Literal[
    "agent_completed",
    "agent_dispatched",
    "agent_exit_decision",
    "agent_failed",
    "agent_loop_iteration",
    "agent_required",
    "agent_result_rejected",
    "agent_started",
    "ambiguity_logged",
    "artifact_saved",
    "blackboard_reduce",
    "builtin_subagent_enter",
    "builtin_subagent_exit",
    "builtin_subagent_fallback",
    "compaction",
    "dead_end_pruned",
    "edge_end",
    "edge_start",
    "finish_task_verdict",
    "input_dispatch",
    "input_file_injected",
    "interrupted",
    "llm_call",
    "llm_call_settings",
    "llm_delta",
    "llm_route_decision",
    "loop_detected",
    "nudge",
    "parallel_map_group_ended",
    "parallel_map_group_started",
    "phase_end",
    "phase_start",
    "predict_chain_start",
    "prompt_captured",
    "protocol_violation",
    "resumed",
    "run_ended",
    "run_started",
    "runtime_input_injected",
    "tool_call",
    "tool_call_started",
    "tool_error_handled",
    "tool_history_repaired",
    "working_memory_update",
]

_SECRET_KEY_PARTS = frozenset(
    {
        "api_key",
        "access_token",
        "credential",
        "credentials",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)


def _immutable_collection(*_args: object, **_kwargs: object) -> Never:
    raise TypeError("runtime contract JSON values are immutable")


class _FrozenJsonDict(dict[str, JsonValue]):
    """A JSON-serializable dict whose mutation operations are disabled."""

    __setitem__ = _immutable_collection
    __delitem__ = _immutable_collection
    __ior__ = _immutable_collection
    clear = _immutable_collection
    pop = _immutable_collection
    popitem = _immutable_collection
    setdefault = _immutable_collection
    update = _immutable_collection


class _FrozenJsonList(list[JsonValue]):
    """A JSON-serializable list whose mutation operations are disabled."""

    __setitem__ = _immutable_collection
    __delitem__ = _immutable_collection
    __iadd__ = _immutable_collection
    __imul__ = _immutable_collection
    append = _immutable_collection
    clear = _immutable_collection
    extend = _immutable_collection
    insert = _immutable_collection
    pop = _immutable_collection
    remove = _immutable_collection
    reverse = _immutable_collection
    sort = _immutable_collection


def _freeze_json_collections(value: object) -> object:
    if isinstance(value, dict) and not isinstance(value, _FrozenJsonDict):
        frozen = _FrozenJsonDict()
        for key, child in value.items():
            dict.__setitem__(frozen, key, cast(JsonValue, _freeze_json_collections(child)))
        return frozen
    if isinstance(value, list) and not isinstance(value, _FrozenJsonList):
        frozen_list = _FrozenJsonList()
        for child in value:
            list.append(frozen_list, cast(JsonValue, _freeze_json_collections(child)))
        return frozen_list
    if isinstance(value, tuple):
        frozen_tuple = tuple(_freeze_json_collections(child) for child in value)
        return value if all(left is right for left, right in zip(value, frozen_tuple, strict=True)) else frozen_tuple
    return value


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _assert_no_inline_secrets(value: JsonValue, *, path: str) -> None:
    """Reject structurally identifiable secret values from persistent contracts.

    A runtime cannot infer whether an arbitrary business string is confidential.
    The enforceable boundary is therefore explicit: secret-shaped keys are not
    accepted as literal data, and callers use ``SecretBinding`` instead.
    """

    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(key)
            if normalized in _SECRET_KEY_PARTS or any(
                normalized.endswith(f"_{part}") for part in _SECRET_KEY_PARTS
            ):
                raise ValueError(
                    f"{path}.{key} looks like a secret value; store only a SecretReference"
                )
            _assert_no_inline_secrets(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_inline_secrets(child, path=f"{path}[{index}]")


class ContractModel(BaseModel):
    """Closed, immutable base for every public cross-process contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _deep_freeze_json_values(self) -> Self:
        """Make the snapshot immutable below the Pydantic field boundary too."""

        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            frozen = _freeze_json_collections(value)
            if frozen is not value:
                object.__setattr__(self, field_name, frozen)
        return self


class ConfigSource(StrEnum):
    """The exact precedence layer that supplied one resolved value."""

    DEFAULT = "default"
    PORTABLE = "portable"
    USER = "user"
    PROJECT = "project"
    PRESET = "preset"
    INVOCATION = "invocation"


class RuntimeErrorCode(StrEnum):
    """Stable application-boundary error codes."""

    CONFIG_INVALID = "GSKILL_CONFIG_INVALID"
    COMPILE_FAILED = "GSKILL_COMPILE_FAILED"
    EXECUTOR_UNAVAILABLE = "GSKILL_EXECUTOR_UNAVAILABLE"
    INTERNAL_ERROR = "GSKILL_INTERNAL_ERROR"
    INVALID_REQUEST = "GSKILL_INVALID_REQUEST"
    NOT_IMPLEMENTED = "GSKILL_NOT_IMPLEMENTED"
    RUN_FAILED = "GSKILL_RUN_FAILED"
    SNAPSHOT_NOT_FOUND = "GSKILL_SNAPSHOT_NOT_FOUND"


class RuntimeErrorPayload(ContractModel):
    """Provider-neutral failure returned identically by all transports."""

    schema_version: Literal["gskill.error.v1"] = "gskill.error.v1"
    kind: Literal["runtime_error"] = "runtime_error"
    code: RuntimeErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
    phase: str | None = None
    source_path: str | None = None
    details: JsonObject = Field(default_factory=dict)


class ValueOrigin(ContractModel):
    """Provenance for one field in a resolved immutable snapshot."""

    schema_version: Literal["gskill.value-origin.v1"] = "gskill.value-origin.v1"
    kind: Literal["value_origin"] = "value_origin"
    field: str = Field(min_length=1)
    source: ConfigSource
    source_path: str | None = None


class PhaseAddress(ContractModel):
    """Stable graph-local address used by config, diagnostics, and traces."""

    schema_version: Literal["gskill.phase-address.v1"] = "gskill.phase-address.v1"
    kind: Literal["phase_address"] = "phase_address"
    graph_id: Identifier
    phase_id: Identifier

    @property
    def value(self) -> str:
        return f"{self.graph_id}/{self.phase_id}"


class SecretReference(ContractModel):
    """A reference to a secret owned by the host, environment, or keychain."""

    schema_version: Literal["gskill.secret-reference.v1"] = "gskill.secret-reference.v1"
    kind: Literal["secret_reference"] = "secret_reference"
    source: Literal["environment", "host", "keychain"]
    name: str = Field(min_length=1, max_length=256)


class SecretBinding(ContractModel):
    """Bind a business input to a secret reference without persisting its value."""

    schema_version: Literal["gskill.secret-binding.v1"] = "gskill.secret-binding.v1"
    kind: Literal["secret_binding"] = "secret_binding"
    input_name: Identifier
    reference: SecretReference


class HostNativeExecutorConfig(ContractModel):
    schema_version: Literal["gskill.executor.v1"] = "gskill.executor.v1"
    kind: Literal["host-native"] = "host-native"


class CliExecutorConfig(ContractModel):
    schema_version: Literal["gskill.executor.v1"] = "gskill.executor.v1"
    kind: Literal["cli"] = "cli"
    vendor: Literal["claude", "codex", "copilot", "cursor", "gemini", "opencode"]
    agent_profile: Identifier | None = Field(
        default=None,
        description="Vendor-native agent selector for Copilot, Gemini, or OpenCode.",
    )
    model_override: str | None = None
    executable: str | None = None
    timeout_seconds: float = Field(default=600.0, gt=0, le=86_400)

    @field_validator("agent_profile", "model_override", "executable")
    @classmethod
    def _optional_text_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("CLI executor text fields cannot be blank")
        if value is not None and any(character in value for character in "\0\r\n"):
            raise ValueError("CLI executor text fields cannot contain control lines")
        return value

    @model_validator(mode="after")
    def _agent_profile_requires_vendor_native_dispatch(self) -> CliExecutorConfig:
        if self.agent_profile is not None and self.vendor not in {
            "copilot",
            "gemini",
            "opencode",
        }:
            raise ValueError(
                "agent_profile is supported only for Copilot, Gemini, or OpenCode"
            )
        return self


class EmbeddedExecutorConfig(ContractModel):
    schema_version: Literal["gskill.executor.v1"] = "gskill.executor.v1"
    kind: Literal["embedded"] = "embedded"
    provider: Identifier | None = None
    model: str | None = None
    credential: SecretReference | None = None


ExecutorConfig: TypeAlias = Annotated[
    HostNativeExecutorConfig | CliExecutorConfig | EmbeddedExecutorConfig,
    Field(discriminator="kind"),
]


class MemoryCheckpointStoreConfig(ContractModel):
    schema_version: Literal["gskill.checkpoint-store.v1"] = "gskill.checkpoint-store.v1"
    kind: Literal["memory"] = "memory"


class SqliteCheckpointStoreConfig(ContractModel):
    schema_version: Literal["gskill.checkpoint-store.v1"] = "gskill.checkpoint-store.v1"
    kind: Literal["sqlite"] = "sqlite"
    filename: str = Field(default="checkpoints.sqlite3", pattern=r"^[^/\\]+$")


CheckpointStoreConfig: TypeAlias = Annotated[
    MemoryCheckpointStoreConfig | SqliteCheckpointStoreConfig,
    Field(discriminator="kind"),
]


class PermissionPolicy(ContractModel):
    schema_version: Literal["gskill.permission-policy.v1"] = "gskill.permission-policy.v1"
    kind: Literal["permission_policy"] = "permission_policy"
    network: Literal["deny", "host-policy", "allow"] = "host-policy"
    filesystem: Literal["declared-only", "skill-and-state"] = "skill-and-state"


class RuntimeProfileOverlay(ContractModel):
    """Partial machine/runtime choices from one precedence layer."""

    schema_version: Literal["gskill.runtime-profile-overlay.v1"] = (
        "gskill.runtime-profile-overlay.v1"
    )
    kind: Literal["runtime_profile_overlay"] = "runtime_profile_overlay"
    executor: ExecutorConfig | None = None
    checkpoint_store: CheckpointStoreConfig | None = None
    state_dir: str | None = None
    permissions: PermissionPolicy | None = None
    required_capabilities: tuple[Identifier, ...] | None = None
    fallback_executors: tuple[ExecutorConfig, ...] | None = None

    @field_validator("state_dir")
    @classmethod
    def _state_dir_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("state_dir cannot be blank")
        return value


class RuntimeProfile(ContractModel):
    """Complete machine/runtime choices; contains no business run values."""

    schema_version: Literal["gskill.runtime-profile.v1"] = "gskill.runtime-profile.v1"
    kind: Literal["runtime_profile"] = "runtime_profile"
    executor: ExecutorConfig = Field(default_factory=HostNativeExecutorConfig)
    checkpoint_store: CheckpointStoreConfig = Field(default_factory=SqliteCheckpointStoreConfig)
    state_dir: str | None = None
    permissions: PermissionPolicy = Field(default_factory=PermissionPolicy)
    required_capabilities: tuple[Identifier, ...] = ()
    fallback_executors: tuple[ExecutorConfig, ...] = ()

    @model_validator(mode="after")
    def _fallbacks_are_explicit_and_distinct(self) -> RuntimeProfile:
        kinds = [executor.kind for executor in self.fallback_executors]
        if self.executor.kind in kinds:
            raise ValueError("fallback_executors cannot repeat the primary executor")
        if len(kinds) != len(set(kinds)):
            raise ValueError("fallback_executors cannot contain duplicate executor kinds")
        return self


class ResolvedRuntimeProfile(ContractModel):
    """Normalized runtime profile and absolute path snapshot for one run."""

    schema_version: Literal["gskill.resolved-runtime-profile.v1"] = (
        "gskill.resolved-runtime-profile.v1"
    )
    kind: Literal["resolved_runtime_profile"] = "resolved_runtime_profile"
    profile: RuntimeProfile
    skill_root: str = Field(min_length=1)
    state_root: str = Field(min_length=1)
    field_origins: tuple[ValueOrigin, ...]

    @model_validator(mode="after")
    def _paths_are_absolute(self) -> ResolvedRuntimeProfile:
        from pathlib import Path

        for field_name, raw_path in (("skill_root", self.skill_root), ("state_root", self.state_root)):
            if not Path(raw_path).is_absolute():
                raise ValueError(f"{field_name} must be absolute")
        return self


class InputBinding(ContractModel):
    schema_version: Literal["gskill.input-binding.v1"] = "gskill.input-binding.v1"
    kind: Literal["input_binding"] = "input_binding"
    address: PhaseAddress
    field: Identifier
    value: JsonValue

    @model_validator(mode="after")
    def _literal_is_not_a_secret(self) -> InputBinding:
        _assert_no_inline_secrets(self.value, path=f"bindings.{self.address.value}.{self.field}")
        return self


class NodeOverride(ContractModel):
    schema_version: Literal["gskill.node-override.v1"] = "gskill.node-override.v1"
    kind: Literal["node_override"] = "node_override"
    address: PhaseAddress
    timeout_seconds: float | None = Field(default=None, gt=0)
    custom_params: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def _params_do_not_persist_secrets(self) -> NodeOverride:
        _assert_no_inline_secrets(self.custom_params, path=f"node_overrides.{self.address.value}")
        return self


class CompareCandidate(ContractModel):
    schema_version: Literal["gskill.compare-candidate.v1"] = "gskill.compare-candidate.v1"
    kind: Literal["compare_candidate"] = "compare_candidate"
    address: PhaseAddress
    candidate_id: Identifier
    model_override: str | None = None


class ArtifactRequest(ContractModel):
    schema_version: Literal["gskill.artifact-request.v1"] = "gskill.artifact-request.v1"
    kind: Literal["artifact_request"] = "artifact_request"
    artifact_id: Identifier
    destination: str | None = None


class RunPreset(ContractModel):
    """Reusable, non-secret business defaults selected by name."""

    schema_version: Literal["gskill.run-preset.v1"] = "gskill.run-preset.v1"
    kind: Literal["run_preset"] = "run_preset"
    preset_id: Identifier
    inputs: JsonObject = Field(default_factory=dict)
    secret_inputs: tuple[SecretBinding, ...] = ()
    bindings: tuple[InputBinding, ...] = ()
    breakpoints: tuple[PhaseAddress, ...] = ()
    node_overrides: tuple[NodeOverride, ...] = ()
    compare_candidates: tuple[CompareCandidate, ...] = ()
    artifact_requests: tuple[ArtifactRequest, ...] = ()

    @model_validator(mode="after")
    def _preset_does_not_persist_inline_secrets(self) -> RunPreset:
        _assert_no_inline_secrets(self.inputs, path=f"presets.{self.preset_id}.inputs")
        return self


class RunInvocation(ContractModel):
    """Caller-supplied values before precedence resolution."""

    schema_version: Literal["gskill.run-invocation.v1"] = "gskill.run-invocation.v1"
    kind: Literal["run_invocation"] = "run_invocation"
    skill_root: str = Field(min_length=1)
    run_id: str | None = None
    preset_id: Identifier | None = None
    runtime: RuntimeProfileOverlay = Field(default_factory=RuntimeProfileOverlay)
    inputs: JsonObject | None = None
    secret_inputs: tuple[SecretBinding, ...] | None = None
    bindings: tuple[InputBinding, ...] | None = None
    breakpoints: tuple[PhaseAddress, ...] | None = None
    node_overrides: tuple[NodeOverride, ...] | None = None
    compare_candidates: tuple[CompareCandidate, ...] | None = None
    artifact_requests: tuple[ArtifactRequest, ...] | None = None

    @model_validator(mode="after")
    def _invocation_does_not_inline_secrets(self) -> RunInvocation:
        if self.inputs is not None:
            _assert_no_inline_secrets(self.inputs, path="invocation.inputs")
        return self


class RunRequest(ContractModel):
    """Replayable execution snapshot produced once by the config resolver."""

    schema_version: Literal["gskill.run-request.v1"] = "gskill.run-request.v1"
    kind: Literal["run_request"] = "run_request"
    run_id: str = Field(min_length=1)
    preset_id: Identifier | None = None
    profile: ResolvedRuntimeProfile
    inputs: JsonObject = Field(default_factory=dict)
    secret_inputs: tuple[SecretBinding, ...] = ()
    bindings: tuple[InputBinding, ...] = ()
    breakpoints: tuple[PhaseAddress, ...] = ()
    node_overrides: tuple[NodeOverride, ...] = ()
    compare_candidates: tuple[CompareCandidate, ...] = ()
    artifact_requests: tuple[ArtifactRequest, ...] = ()
    value_origins: tuple[ValueOrigin, ...] = ()


class ConfigResolution(ContractModel):
    schema_version: Literal["gskill.config-resolution.v1"] = "gskill.config-resolution.v1"
    kind: Literal["config_resolution"] = "config_resolution"
    profile: ResolvedRuntimeProfile
    request: RunRequest


class CompileRequest(ContractModel):
    schema_version: Literal["gskill.compile-request.v1"] = "gskill.compile-request.v1"
    kind: Literal["compile_request"] = "compile_request"
    skill_root: str = Field(min_length=1)
    cache: bool = True


class CompileDiagnostic(ContractModel):
    schema_version: Literal["gskill.compile-diagnostic.v1"] = "gskill.compile-diagnostic.v1"
    kind: Literal["compile_diagnostic"] = "compile_diagnostic"
    code: str = Field(min_length=1)
    severity: Literal["fatal", "warning", "info"]
    message: str = Field(min_length=1)
    source_path: str | None = None
    line: int | None = Field(default=None, ge=1)
    field_path: str | None = None
    graph_id: str | None = None
    phase_id: str | None = None
    conflicting_phase: str | None = None


class CompileResult(ContractModel):
    schema_version: Literal["gskill.compile-result.v1"] = "gskill.compile-result.v1"
    kind: Literal["compile_result"] = "compile_result"
    status: Literal["passed", "failed"]
    skill_id: str | None = None
    diagnostics: tuple[CompileDiagnostic, ...] = ()

    @model_validator(mode="after")
    def _status_matches_diagnostics(self) -> CompileResult:
        has_fatal = any(item.severity == "fatal" for item in self.diagnostics)
        if (self.status == "failed") != has_fatal:
            raise ValueError("compile status must match the presence of fatal diagnostics")
        return self

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class PredictRequest(ContractModel):
    schema_version: Literal["gskill.predict-request.v1"] = "gskill.predict-request.v1"
    kind: Literal["predict_request"] = "predict_request"
    invocation: RunInvocation
    strategy: Literal["heuristic"] = "heuristic"


class AgentResource(ContractModel):
    """One declared file resource required by an Agent phase."""

    schema_version: Literal["gskill.agent-resource.v1"] = "gskill.agent-resource.v1"
    kind: Literal["reference", "example"]
    resource_id: Identifier
    path: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class AgentTask(ContractModel):
    schema_version: Literal["gskill.agent-task.v1"] = "gskill.agent-task.v1"
    kind: Literal["agent_task"] = "agent_task"
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    address: PhaseAddress
    instructions: str = Field(min_length=1)
    inputs: JsonObject
    output_schema: JsonObject
    allowed_tools: tuple[Identifier, ...] = ()
    allowed_paths: tuple[str, ...] = ()
    resources: tuple[AgentResource, ...] = ()
    network: Literal["deny", "host-policy", "allow"] = "host-policy"
    deadline: str | None = None
    required_capabilities: tuple[Identifier, ...] = ()


class AgentRequired(ContractModel):
    schema_version: Literal["gskill.agent-required.v1"] = "gskill.agent-required.v1"
    kind: Literal["agent_required"] = "agent_required"
    task: AgentTask
    checkpoint_ref: str = Field(min_length=1)
    submit_methods: tuple[Literal["mcp", "cli"], ...] = ("mcp", "cli")


class AgentResult(ContractModel):
    schema_version: Literal["gskill.agent-result.v1"] = "gskill.agent-result.v1"
    kind: Literal["agent_result"] = "agent_result"
    task_id: str = Field(min_length=1)
    status: Literal["completed", "failed", "cancelled"]
    output: JsonObject | None = None
    error: RuntimeErrorPayload | None = None
    executor_id: str = Field(min_length=1)
    provenance: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def _terminal_payload_matches_status(self) -> AgentResult:
        if self.status == "completed" and self.output is None:
            raise ValueError("a completed AgentResult requires output")
        if self.status != "completed" and self.error is None:
            raise ValueError("a non-completed AgentResult requires error")
        if self.output is not None:
            _assert_no_inline_secrets(self.output, path="agent_result.output")
        _assert_no_inline_secrets(self.provenance, path="agent_result.provenance")
        return self


class SubmitAgentResultRequest(ContractModel):
    schema_version: Literal["gskill.submit-agent-result-request.v1"] = (
        "gskill.submit-agent-result-request.v1"
    )
    kind: Literal["submit_agent_result_request"] = "submit_agent_result_request"
    run_id: str = Field(min_length=1)
    state_root: str = Field(min_length=1)
    checkpoint_ref: str = Field(min_length=1)
    result: AgentResult


class ResumeRequest(ContractModel):
    schema_version: Literal["gskill.resume-request.v1"] = "gskill.resume-request.v1"
    kind: Literal["resume_request"] = "resume_request"
    run_id: str = Field(min_length=1)
    skill_root: str = Field(min_length=1)
    state_root: str = Field(min_length=1)
    checkpoint_ref: str | None = None
    human_response: JsonObject | None = None


class RunResult(ContractModel):
    schema_version: Literal["gskill.run-result.v1"] = "gskill.run-result.v1"
    kind: Literal["run_result"] = "run_result"
    status: Literal["completed", "failed", "paused", "agent_required"]
    run_id: str = Field(min_length=1)
    mode: Literal["run", "predict", "resume"]
    request: RunRequest | None = None
    outputs: JsonObject = Field(default_factory=dict)
    trace_path: str | None = None
    error: RuntimeErrorPayload | None = None
    agent_required: AgentRequired | None = None
    diagnostics: tuple[CompileDiagnostic, ...] = ()

    @model_validator(mode="after")
    def _payload_matches_status(self) -> RunResult:
        if self.status == "failed" and self.error is None:
            raise ValueError("a failed RunResult requires error")
        if self.status == "agent_required" and self.agent_required is None:
            raise ValueError("agent_required status requires an AgentRequired payload")
        if self.status != "agent_required" and self.agent_required is not None:
            raise ValueError("AgentRequired payload is only valid for agent_required status")
        return self


class RuntimeEvent(ContractModel):
    """Versioned transport envelope around a concrete observable event."""

    schema_version: Literal["gskill.runtime-event.v1"] = "gskill.runtime-event.v1"
    kind: Literal["runtime_event"] = "runtime_event"
    event_type: CallbackEventType
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    timestamp: str = Field(min_length=1)
    payload: JsonObject = Field(default_factory=dict)


class GoldenEvaluationRequest(ContractModel):
    schema_version: Literal["gskill.golden-request.v1"] = "gskill.golden-request.v1"
    kind: Literal["golden_evaluation_request"] = "golden_evaluation_request"
    skill_root: str = Field(min_length=1)
    state_root: str = Field(min_length=1)
    baseline_id: Identifier


class GoldenEvaluationResult(ContractModel):
    schema_version: Literal["gskill.golden-result.v1"] = "gskill.golden-result.v1"
    kind: Literal["golden_evaluation_result"] = "golden_evaluation_result"
    status: Literal["passed", "failed"]
    baseline_id: Identifier
    details: JsonObject = Field(default_factory=dict)
    error: RuntimeErrorPayload | None = None


class InspectRequest(ContractModel):
    schema_version: Literal["gskill.inspect-request.v1"] = "gskill.inspect-request.v1"
    kind: Literal["inspect_request"] = "inspect_request"
    skill_root: str = Field(min_length=1)
    include_call_graph: bool = False


class InspectResult(ContractModel):
    schema_version: Literal["gskill.inspect-result.v1"] = "gskill.inspect-result.v1"
    kind: Literal["inspect_result"] = "inspect_result"
    skill_id: str | None = None
    graphs: tuple[str, ...] = ()
    call_edges: tuple[tuple[str, str], ...] = ()
    diagnostics: tuple[CompileDiagnostic, ...] = ()
