"""The v1 typed facade replaces the extracted engine's legacy top-level ABI."""

from __future__ import annotations

import inspect
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel

import graph_skill_runtime
from graph_skill_runtime import (
    AgentExecutor,
    ArtifactStore,
    CheckpointStore,
    EventSink,
    RunSnapshotStore,
    RuntimeEngine,
    SkillSource,
)
from graph_skill_runtime.callbacks import events as callback_events

EXPECTED_PUBLIC_SYMBOLS = {
    "AgentExecutor",
    "AgentRequired",
    "AgentResource",
    "AgentResult",
    "AgentTask",
    "ArtifactRequest",
    "ArtifactStore",
    "CheckpointStore",
    "CliExecutorConfig",
    "CompareCandidate",
    "CompileDiagnostic",
    "CompileRequest",
    "CompileResult",
    "ConfigResolution",
    "ConfigResolver",
    "ConfigSource",
    "ConfigurationError",
    "EmbeddedExecutorConfig",
    "EventSink",
    "GoldenEvaluationRequest",
    "GoldenEvaluationResult",
    "HostNativeExecutorConfig",
    "HostDetection",
    "HostDetectionResult",
    "InputBinding",
    "IntegrationAction",
    "IntegrationChange",
    "IntegrationConflict",
    "IntegrationInstaller",
    "IntegrationOperation",
    "IntegrationPlan",
    "IntegrationRequest",
    "IntegrationResourceKind",
    "IntegrationResult",
    "IntegrationScope",
    "IntegrationTarget",
    "InspectRequest",
    "InspectResult",
    "MemoryCheckpointStoreConfig",
    "NodeOverride",
    "PermissionPolicy",
    "PhaseAddress",
    "PredictRequest",
    "ResolvedRuntimeProfile",
    "ResumeRequest",
    "RunInvocation",
    "RunPreset",
    "RunRequest",
    "RunResult",
    "RunSnapshotStore",
    "RuntimeApplication",
    "RuntimeEngine",
    "RuntimeErrorCode",
    "RuntimeErrorPayload",
    "RuntimeEvent",
    "RuntimeProfile",
    "RuntimeProfileOverlay",
    "SecretBinding",
    "SecretReference",
    "SkillSource",
    "SqliteCheckpointStoreConfig",
    "SubmitAgentResultRequest",
    "ValueOrigin",
    "compile",
    "create_application",
    "detect_integration_hosts",
    "evaluate_golden",
    "inspect",
    "install_integration",
    "plan_integration_install",
    "plan_integration_uninstall",
    "predict",
    "resolve_run",
    "resume",
    "run",
    "submit_agent_result",
    "uninstall_integration",
}

LEGACY_TOP_LEVEL_SYMBOLS = {
    "assemble_graph",
    "BlackboardState",
    "compile_artifact",
    "compile_skill",
    "CompiledSkill",
    "CompiledStateGraph",
    "evaluate_golden_baseline",
    "GraphAgentError",
    "GraphCompileError",
    "GraphExecutionError",
    "LocalWorkspaceResolver",
    "PathDiff",
    "PhaseRecord",
    "predict_artifact",
    "predict_skill",
    "ResourceNotFoundError",
    "resume_skill",
    "run_artifact",
    "run_skill",
    "serialize_skill",
    "SkillManifest",
}

PUBLIC_PORTS = (
    AgentExecutor,
    ArtifactStore,
    CheckpointStore,
    EventSink,
    RunSnapshotStore,
    RuntimeEngine,
    SkillSource,
)


def _contains_any(annotation: object) -> bool:
    if annotation is Any:
        return True
    return any(_contains_any(argument) for argument in get_args(annotation))


def test_top_level_all_remains_the_declared_symbol_surface() -> None:
    assert set(graph_skill_runtime.__all__) == EXPECTED_PUBLIC_SYMBOLS
    assert len(graph_skill_runtime.__all__) == len(EXPECTED_PUBLIC_SYMBOLS)


def test_legacy_top_level_symbols_are_absent_after_the_hard_cut() -> None:
    assert LEGACY_TOP_LEVEL_SYMBOLS.isdisjoint(graph_skill_runtime.__all__)
    assert all(not hasattr(graph_skill_runtime, name) for name in LEGACY_TOP_LEVEL_SYMBOLS)


def test_public_contract_models_are_closed_frozen_and_versioned() -> None:
    model_types = {
        value
        for name in graph_skill_runtime.__all__
        if isinstance((value := getattr(graph_skill_runtime, name)), type)
        and issubclass(value, BaseModel)
    }
    assert model_types
    for model_type in model_types:
        assert model_type.model_config.get("extra") == "forbid", model_type.__name__
        assert model_type.model_config.get("frozen") is True, model_type.__name__
        assert "schema_version" in model_type.model_fields, model_type.__name__
        assert "kind" in model_type.model_fields, model_type.__name__


def test_runtime_event_type_catalog_matches_every_internal_callback_variant() -> None:
    public_event_types = set(
        get_args(graph_skill_runtime.RuntimeEvent.model_fields["event_type"].annotation)
    )
    internal_event_types = {
        event_model.model_fields["event_type"].default
        for symbol in callback_events.__all__
        if isinstance((event_model := getattr(callback_events, symbol, None)), type)
        and issubclass(event_model, BaseModel)
        and "event_type" in event_model.model_fields
    }

    assert public_event_types == internal_event_types


def test_public_functions_do_not_expose_unconstrained_any() -> None:
    for name in (
        "compile",
        "detect_integration_hosts",
        "evaluate_golden",
        "inspect",
        "install_integration",
        "plan_integration_install",
        "plan_integration_uninstall",
        "predict",
        "resolve_run",
        "resume",
        "run",
        "submit_agent_result",
        "uninstall_integration",
    ):
        hints = get_type_hints(getattr(graph_skill_runtime, name))
        assert hints
        assert all(not _contains_any(annotation) for annotation in hints.values()), name


def test_public_ports_do_not_expose_unconstrained_any() -> None:
    for port in PUBLIC_PORTS:
        assert get_origin(port) is None
        for method_name, method in inspect.getmembers(port, inspect.isfunction):
            if method_name.startswith("_"):
                continue
            hints = get_type_hints(method)
            assert hints, f"{port.__name__}.{method_name}"
            assert all(not _contains_any(annotation) for annotation in hints.values()), (
                f"{port.__name__}.{method_name}"
            )


def test_runtime_profile_cannot_represent_business_run_fields() -> None:
    runtime_fields = set(graph_skill_runtime.RuntimeProfile.model_fields)
    assert runtime_fields.isdisjoint(
        {
            "inputs",
            "bindings",
            "breakpoints",
            "node_overrides",
            "compare_candidates",
            "artifact_requests",
        }
    )
