"""Synchronous graph runtime for direct vendor CLI Agent phases."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol, cast

from pydantic import JsonValue

from graph_skill_runtime.adapters.host_native import (
    HostNativeContractError,
    host_native_agent_phases,
)
from graph_skill_runtime.adapters.host_native_runtime import HostNativeRuntimeAdapter
from graph_skill_runtime.adapters.vendor_cli.executor import (
    CliExecutorFailure,
    CliExecutorUnavailable,
    DispatchCallback,
    StartedCallback,
    VendorCliExecutor,
    VendorProbe,
)
from graph_skill_runtime.callbacks.emit import append_run_event_once
from graph_skill_runtime.callbacks.events import (
    AgentDispatchedEvent,
    AgentFailedEvent,
    AgentStartedEvent,
)
from graph_skill_runtime.core.loader import CompiledSkill, PhaseDocument
from graph_skill_runtime.core.manifest import AgentNodeAST
from graph_skill_runtime.domain.models import (
    AgentResult,
    AgentTask,
    CliExecutorConfig,
    JsonObject,
    RunRequest,
    RunResult,
    RuntimeErrorCode,
    RuntimeErrorPayload,
    SubmitAgentResultRequest,
)


class _CliExecutor(Protocol):
    @property
    def executor_id(self) -> str: ...

    def probe(self) -> VendorProbe: ...

    def execute(
        self,
        task: AgentTask,
        probe: VendorProbe | None = None,
        *,
        on_dispatched: DispatchCallback | None = None,
        on_started: StartedCallback | None = None,
    ) -> AgentResult: ...


class CliExecutorFactory(Protocol):
    def __call__(self, config: CliExecutorConfig) -> _CliExecutor: ...


def _default_executor(config: CliExecutorConfig) -> _CliExecutor:
    return VendorCliExecutor(config)


def _trace_directory(request: RunRequest) -> Path:
    return Path(request.profile.state_root) / "runs" / request.run_id


def _unsupported_phase_capabilities(
    phases: dict[str, PhaseDocument],
) -> dict[str, list[str]]:
    unsupported: dict[str, list[str]] = {}
    for phase_id, phase in phases.items():
        node = cast(AgentNodeAST, phase.ast)
        capabilities = [
            *(f"tool:{name}" for name in node.tools),
            *(f"subagent:{item.name}" for item in node.subagents),
            *(f"subgraph:{item.name}" for item in node.subgraphs),
            *(f"context:{name}" for name in node.context_access),
        ]
        if capabilities:
            unsupported[phase_id] = capabilities
    return unsupported


def _validate_support(
    request: RunRequest,
    phases: dict[str, PhaseDocument],
    probe: VendorProbe,
) -> None:
    unsupported = _unsupported_phase_capabilities(phases)
    if unsupported:
        raise CliExecutorUnavailable(
            "direct CLI execution does not yet bridge portable Agent tools, "
            "subagents, subgraphs, or framework context tools",
            category="task-capability-missing",
            retryable=False,
            details={"unsupported": cast(JsonValue, unsupported)},
        )
    required = set(request.profile.profile.required_capabilities)
    missing = sorted(required - probe.capabilities)
    if missing:
        raise CliExecutorUnavailable(
            "vendor CLI does not satisfy the runtime profile's required capabilities",
            category="capability-missing",
            details={"missing_capabilities": cast(JsonValue, missing)},
        )


def _failure_result(
    request: RunRequest,
    *,
    code: RuntimeErrorCode,
    message: str,
    category: str,
    vendor: str,
    retryable: bool,
    details: JsonObject | None = None,
    pending: RunResult | None = None,
) -> RunResult:
    merged: JsonObject = {
        "category": category,
        "executor_kind": "cli",
        "vendor": vendor,
        **(details or {}),
    }
    outputs: JsonObject = {}
    trace_path: str | None = None
    if pending is not None:
        outputs = pending.outputs
        trace_path = pending.trace_path
        if pending.agent_required is not None:
            merged["checkpoint_ref"] = pending.agent_required.checkpoint_ref
            merged["task_id"] = pending.agent_required.task.task_id
    return RunResult(
        status="failed",
        run_id=request.run_id,
        mode="run",
        request=request,
        outputs=outputs,
        trace_path=trace_path,
        error=RuntimeErrorPayload(
            code=code,
            message=message,
            retryable=retryable,
            details=merged,
        ),
    )


def _emit_dispatched(
    request: RunRequest,
    task: AgentTask,
    executor: _CliExecutor,
    probe: VendorProbe,
    attempt_id: str,
) -> None:
    event_id = f"cli-attempt:{attempt_id}:dispatched"
    append_run_event_once(
        _trace_directory(request),
        AgentDispatchedEvent(
            handoff_event_id=event_id,
            attempt_id=attempt_id,
            run_id=request.run_id,
            task_id=task.task_id,
            phase_name=task.address.phase_id,
            executor_id=executor.executor_id,
            vendor=probe.vendor,
            fresh_top_level_session=True,
        ),
        event_id=event_id,
    )


def _emit_started(
    request: RunRequest,
    task: AgentTask,
    executor: _CliExecutor,
    probe: VendorProbe,
    attempt_id: str,
    process_id: int,
) -> None:
    event_id = f"cli-attempt:{attempt_id}:started"
    append_run_event_once(
        _trace_directory(request),
        AgentStartedEvent(
            handoff_event_id=event_id,
            attempt_id=attempt_id,
            run_id=request.run_id,
            task_id=task.task_id,
            phase_name=task.address.phase_id,
            executor_id=executor.executor_id,
            vendor=probe.vendor,
            process_id=process_id,
        ),
        event_id=event_id,
    )


def _emit_attempt_failed(
    request: RunRequest,
    task: AgentTask,
    executor: _CliExecutor,
    attempt_id: str,
    failure: CliExecutorFailure | CliExecutorUnavailable,
) -> None:
    event_id = f"cli-attempt:{attempt_id}:failed"
    append_run_event_once(
        _trace_directory(request),
        AgentFailedEvent(
            handoff_event_id=event_id,
            attempt_id=attempt_id,
            run_id=request.run_id,
            task_id=task.task_id,
            phase_name=task.address.phase_id,
            executor_id=executor.executor_id,
            status="failed",
            error_code=failure.category,
            error_message=str(failure),
            retryable=failure.retryable,
            task_terminal=False,
        ),
        event_id=event_id,
    )


class _AttemptEvents:
    def __init__(
        self,
        request: RunRequest,
        task: AgentTask,
        executor: _CliExecutor,
        probe: VendorProbe,
    ) -> None:
        self._request = request
        self._task = task
        self._executor = executor
        self._probe = probe
        self.attempt_id = str(uuid.uuid4())
        self.dispatched_happened = False

    def on_dispatched(self) -> None:
        _emit_dispatched(
            self._request,
            self._task,
            self._executor,
            self._probe,
            self.attempt_id,
        )
        self.dispatched_happened = True

    def on_started(self, process_id: int) -> None:
        _emit_started(
            self._request,
            self._task,
            self._executor,
            self._probe,
            self.attempt_id,
            process_id,
        )

    def on_failed(self, failure: CliExecutorFailure | CliExecutorUnavailable) -> None:
        if self.dispatched_happened:
            _emit_attempt_failed(
                self._request,
                self._task,
                self._executor,
                self.attempt_id,
                failure,
            )


def _execute_agent_loop(
    request: RunRequest,
    configured: CliExecutorConfig,
    phases: dict[str, PhaseDocument],
    executor: _CliExecutor,
    probe: VendorProbe,
    host_runtime: HostNativeRuntimeAdapter,
    pending: RunResult,
) -> RunResult:
    completed_tasks = 0
    while pending.status == "agent_required":
        if completed_tasks >= len(phases):
            return _failure_result(
                request,
                code=RuntimeErrorCode.RUN_FAILED,
                message="CLI Agent phase loop exceeded the compiled phase count",
                category="protocol-loop",
                vendor=configured.vendor,
                retryable=False,
                pending=pending,
            )
        required = pending.agent_required
        assert required is not None
        task = required.task
        events = _AttemptEvents(request, task, executor, probe)
        try:
            agent_result = executor.execute(
                task,
                probe,
                on_dispatched=events.on_dispatched,
                on_started=events.on_started,
            )
        except (CliExecutorFailure, CliExecutorUnavailable) as exc:
            events.on_failed(exc)
            return _failure_result(
                request,
                code=(
                    RuntimeErrorCode.EXECUTOR_UNAVAILABLE
                    if isinstance(exc, CliExecutorUnavailable)
                    else RuntimeErrorCode.RUN_FAILED
                ),
                message=str(exc),
                category=exc.category,
                vendor=configured.vendor,
                retryable=(
                    exc.retryable if isinstance(exc, CliExecutorFailure) else True
                ),
                details=exc.details,
                pending=pending,
            )
        pending = host_runtime.submit_agent_result(
            SubmitAgentResultRequest(
                run_id=request.run_id,
                state_root=request.profile.state_root,
                checkpoint_ref=required.checkpoint_ref,
                result=agent_result,
            ),
            request,
            attempt_id=events.attempt_id,
        )
        completed_tasks += 1
    return pending.model_copy(update={"mode": "run"})


class CliRuntimeAdapter:
    """Execute every durable Agent wait through a probed fresh CLI process."""

    def __init__(
        self,
        *,
        executor_factory: CliExecutorFactory = _default_executor,
    ) -> None:
        self._executor_factory = executor_factory

    def run(self, request: RunRequest, compiled: CompiledSkill) -> RunResult:
        configured = request.profile.profile.executor
        if not isinstance(configured, CliExecutorConfig):
            return _failure_result(
                request,
                code=RuntimeErrorCode.INVALID_REQUEST,
                message="CliRuntimeAdapter requires CliExecutorConfig",
                category="invalid-config",
                vendor="unknown",
                retryable=False,
            )
        try:
            phases = host_native_agent_phases(compiled)
        except HostNativeContractError as exc:
            return _failure_result(
                request,
                code=RuntimeErrorCode.INVALID_REQUEST,
                message=str(exc),
                category="unsupported-topology",
                vendor=configured.vendor,
                retryable=False,
            )
        host_runtime = HostNativeRuntimeAdapter()
        if not phases:
            return host_runtime.run(request, compiled)
        executor = self._executor_factory(configured)
        try:
            probe = executor.probe()
            _validate_support(request, phases, probe)
        except CliExecutorUnavailable as exc:
            return _failure_result(
                request,
                code=RuntimeErrorCode.EXECUTOR_UNAVAILABLE,
                message=str(exc),
                category=exc.category,
                vendor=configured.vendor,
                retryable=exc.retryable,
                details=exc.details,
            )
        except CliExecutorFailure as exc:
            return _failure_result(
                request,
                code=RuntimeErrorCode.RUN_FAILED,
                message=str(exc),
                category=exc.category,
                vendor=configured.vendor,
                retryable=exc.retryable,
                details=exc.details,
            )

        return _execute_agent_loop(
            request,
            configured,
            phases,
            executor,
            probe,
            host_runtime,
            host_runtime.run(request, compiled),
        )
