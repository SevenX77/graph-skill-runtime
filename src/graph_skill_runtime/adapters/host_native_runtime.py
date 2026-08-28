"""Runtime adapter for cooperative host-native Agent execution."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from pydantic import JsonValue

from graph_skill_runtime.adapters.agent_handoffs import (
    AgentHandoffRecord,
    SqliteAgentHandoffStore,
    canonical_agent_result_hash,
)
from graph_skill_runtime.adapters.host_native import (
    HostNativeContractError,
    build_agent_handoff,
    host_native_agent_phases,
    validate_agent_result,
)
from graph_skill_runtime.adapters.result_mapping import failed_run, run_result
from graph_skill_runtime.callbacks.emit import append_run_event_once
from graph_skill_runtime.callbacks.events import (
    AgentCompletedEvent,
    AgentFailedEvent,
    AgentRequiredEvent,
    AgentResultRejectedEvent,
)
from graph_skill_runtime.core.checkpointer import get_checkpointer
from graph_skill_runtime.core.loader import CompiledSkill
from graph_skill_runtime.core.result import RunResult as CoreRunResult
from graph_skill_runtime.domain.models import (
    AgentResult,
    ResumeRequest,
    RunRequest,
    RunResult,
    RuntimeErrorCode,
    SqliteCheckpointStoreConfig,
    SubmitAgentResultRequest,
)


class _RunCallable(Protocol):
    def __call__(
        self,
        skill_path: str | Path,
        *,
        workspace_dir: Path,
        thread_id: str,
        **inputs: JsonValue,
    ) -> CoreRunResult: ...


class _HostNativeRunCallable(Protocol):
    def __call__(
        self,
        skill_path: str | Path,
        *,
        workspace_dir: Path,
        thread_id: str,
        cleanup_checkpoints_on_finish: bool,
        checkpointer_spec: object,
        pause_before: frozenset[str],
        **inputs: JsonValue,
    ) -> CoreRunResult: ...


def _sqlite_checkpointer(request: RunRequest) -> object:
    config = request.profile.profile.checkpoint_store
    if not isinstance(config, SqliteCheckpointStoreConfig):
        raise HostNativeContractError(
            "host-native Agent handoff requires a durable SQLite checkpoint store"
        )
    state_root = Path(request.profile.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    return get_checkpointer(state_root / config.filename, backend="sqlite")


def _handoff_store(request: RunRequest) -> SqliteAgentHandoffStore:
    return SqliteAgentHandoffStore(
        Path(request.profile.state_root) / "agent-handoffs.sqlite3"
    )


def _trace_directory(request: RunRequest) -> Path:
    return Path(request.profile.state_root) / "runs" / request.run_id


def _validate_record_owner(
    record: AgentHandoffRecord,
    *,
    run_id: str,
    run_request: RunRequest,
) -> None:
    if record.task.run_id != run_id:
        raise HostNativeContractError("checkpoint_ref belongs to a different run")
    if record.required_response.request != run_request:
        raise HostNativeContractError(
            "checkpoint_ref belongs to a different immutable run request"
        )


def _emit_agent_required(request: RunRequest, record: AgentHandoffRecord) -> None:
    event_id = f"agent-required:{record.task.task_id}"
    append_run_event_once(
        _trace_directory(request),
        AgentRequiredEvent(
            handoff_event_id=event_id,
            run_id=request.run_id,
            task_id=record.task.task_id,
            graph_id=record.task.address.graph_id,
            phase_name=record.task.address.phase_id,
            checkpoint_ref=record.checkpoint_ref,
        ),
        event_id=event_id,
    )


def _emit_agent_terminal(
    request: RunRequest,
    record: AgentHandoffRecord,
    result: AgentResult,
    result_hash: str,
) -> None:
    event_id = f"agent-result:{record.task.task_id}:{result_hash}"
    event: AgentCompletedEvent | AgentFailedEvent
    if result.status == "completed":
        event = AgentCompletedEvent(
            handoff_event_id=event_id,
            run_id=request.run_id,
            task_id=result.task_id,
            phase_name=record.task.address.phase_id,
            executor_id=result.executor_id,
            provenance=dict(result.provenance),
        )
    else:
        assert result.error is not None
        event = AgentFailedEvent(
            handoff_event_id=event_id,
            run_id=request.run_id,
            task_id=result.task_id,
            phase_name=record.task.address.phase_id,
            executor_id=result.executor_id,
            status=result.status,
            error_code=result.error.code,
            error_message=result.error.message,
        )
    append_run_event_once(
        _trace_directory(request),
        event,
        event_id=event_id,
    )


def _emit_agent_rejected(
    request: RunRequest,
    submission: SubmitAgentResultRequest,
    reason: str,
    *,
    record: AgentHandoffRecord | None,
) -> None:
    result_hash = canonical_agent_result_hash(submission.result)
    event_id = f"agent-rejected:{submission.checkpoint_ref}:{result_hash}"
    append_run_event_once(
        _trace_directory(request),
        AgentResultRejectedEvent(
            handoff_event_id=event_id,
            run_id=request.run_id,
            submitted_task_id=submission.result.task_id,
            expected_task_id=record.task.task_id if record is not None else None,
            phase_name=(record.task.address.phase_id if record is not None else None),
            checkpoint_ref=submission.checkpoint_ref,
            reason=reason,
        ),
        event_id=event_id,
    )


class HostNativeRuntimeAdapter:
    """Own the durable AgentTask/AgentResult lifecycle, not graph compilation."""

    def run(self, request: RunRequest, compiled: CompiledSkill) -> RunResult:
        from graph_skill_runtime.core.runner import recover_paused_skill, run_skill

        try:
            phases = host_native_agent_phases(compiled)
            if not phases:
                run_call = cast(_RunCallable, run_skill)
                result = run_call(
                    request.profile.skill_root,
                    workspace_dir=Path(request.profile.state_root),
                    thread_id=request.run_id,
                    **request.inputs,
                )
                return run_result(result, request=request, mode="run")
            checkpointer = _sqlite_checkpointer(request)
            store = _handoff_store(request)
            recovered = store.recover_run(request.run_id)
            if recovered is not None:
                if recovered.request != request:
                    raise HostNativeContractError(
                        "run id already owns a different host-native request"
                    )
                if recovered.agent_required is not None:
                    _emit_agent_required(
                        request,
                        store.load(recovered.agent_required.checkpoint_ref),
                    )
                return recovered
            paused = recover_paused_skill(
                compiled,
                workspace_dir=Path(request.profile.state_root),
                run_id=request.run_id,
                checkpointer=checkpointer,
                pause_before=frozenset(phases),
            )
            if paused is not None:
                handoff = build_agent_handoff(
                    request,
                    compiled,
                    phases,
                    paused,
                    mode="run",
                )
                store.put_required(handoff)
                _emit_agent_required(request, handoff)
                return handoff.required_response
            host_run_call = cast(_HostNativeRunCallable, run_skill)
            result = host_run_call(
                request.profile.skill_root,
                workspace_dir=Path(request.profile.state_root),
                thread_id=request.run_id,
                cleanup_checkpoints_on_finish=False,
                checkpointer_spec=checkpointer,
                pause_before=frozenset(phases),
                **request.inputs,
            )
            if result.paused_at is None:
                return run_result(result, request=request, mode="run")
            handoff = build_agent_handoff(
                request,
                compiled,
                phases,
                result,
                mode="run",
            )
            store.put_required(handoff)
            _emit_agent_required(request, handoff)
            return handoff.required_response
        except Exception as exc:
            return failed_run(
                request,
                mode="run",
                code=(
                    RuntimeErrorCode.INVALID_REQUEST
                    if isinstance(exc, HostNativeContractError)
                    else RuntimeErrorCode.RUN_FAILED
                ),
                message=str(exc),
                details={"executor_kind": "host-native"},
            )

    def resume(self, request: ResumeRequest, run_request: RunRequest) -> RunResult:
        if request.checkpoint_ref is not None:
            try:
                record = _handoff_store(run_request).load(request.checkpoint_ref)
            except ValueError as exc:
                return failed_run(
                    run_request,
                    mode="resume",
                    code=RuntimeErrorCode.INVALID_REQUEST,
                    message=str(exc),
                    details={"checkpoint_ref": request.checkpoint_ref},
                )
            try:
                _validate_record_owner(
                    record,
                    run_id=request.run_id,
                    run_request=run_request,
                )
            except HostNativeContractError as exc:
                return failed_run(
                    run_request,
                    mode="resume",
                    code=RuntimeErrorCode.INVALID_REQUEST,
                    message=str(exc),
                    details={"checkpoint_ref": request.checkpoint_ref},
                )
            return record.response or record.required_response
        return failed_run(
            run_request,
            mode="resume",
            code=RuntimeErrorCode.NOT_IMPLEMENTED,
            message="resume without a host-native checkpoint_ref is not implemented yet",
        )

    def submit_agent_result(
        self,
        request: SubmitAgentResultRequest,
        run_request: RunRequest,
    ) -> RunResult:
        from graph_skill_runtime.core.compiler import compile_skill
        from graph_skill_runtime.core.runner import ExternalPhaseCompletion, resume_skill

        record: AgentHandoffRecord | None = None
        try:
            compiled = compile_skill(run_request.profile.skill_root)
            phases = host_native_agent_phases(compiled)
            store = _handoff_store(run_request)
            record = store.load(request.checkpoint_ref)
            _validate_record_owner(
                record,
                run_id=request.run_id,
                run_request=run_request,
            )
            validate_agent_result(record, request.result)
            result_hash = canonical_agent_result_hash(request.result)

            def continue_run(
                active_record: AgentHandoffRecord,
                durable_result_hash: str,
            ) -> tuple[RunResult, AgentHandoffRecord | None]:
                agent_result = request.result
                _emit_agent_terminal(
                    run_request,
                    active_record,
                    agent_result,
                    durable_result_hash,
                )
                if agent_result.status != "completed":
                    assert agent_result.error is not None
                    return (
                        RunResult(
                            status="failed",
                            run_id=run_request.run_id,
                            mode="resume",
                            request=run_request,
                            outputs=active_record.required_response.outputs,
                            error=agent_result.error,
                        ),
                        None,
                    )
                assert agent_result.output is not None
                core_result = resume_skill(
                    run_request.profile.skill_root,
                    workspace_dir=Path(run_request.profile.state_root),
                    run_id=run_request.run_id,
                    checkpoint_id=active_record.checkpoint_id,
                    checkpoint_ns=active_record.checkpoint_ns,
                    checkpointer=_sqlite_checkpointer(run_request),
                    pause_before=frozenset(phases),
                    external_phase_completion=ExternalPhaseCompletion(
                        task_id=agent_result.task_id,
                        phase_id=active_record.task.address.phase_id,
                        result_hash=durable_result_hash,
                        output=dict(agent_result.output),
                    ),
                )
                if core_result.paused_at is not None:
                    next_handoff = build_agent_handoff(
                        run_request,
                        compiled,
                        phases,
                        core_result,
                        mode="resume",
                    )
                    return next_handoff.required_response, next_handoff
                return run_result(core_result, request=run_request, mode="resume"), None

            response = store.submit(
                request.checkpoint_ref,
                request.result,
                result_hash,
                continue_run,
            )
            # Re-emit after the durable transition as well. The deterministic
            # event id makes the ordinary path a no-op, while an exact retry
            # repairs a trace write lost after the handoff transaction committed.
            _emit_agent_terminal(
                run_request,
                record,
                request.result,
                result_hash,
            )
            if response.agent_required is not None:
                next_record = store.load(response.agent_required.checkpoint_ref)
                _emit_agent_required(run_request, next_record)
            return response
        except Exception as exc:
            if isinstance(exc, (HostNativeContractError, ValueError)):
                _emit_agent_rejected(
                    run_request,
                    request,
                    str(exc),
                    record=record,
                )
            return failed_run(
                run_request,
                mode="resume",
                code=RuntimeErrorCode.INVALID_REQUEST,
                message=str(exc),
                details={"checkpoint_ref": request.checkpoint_ref},
            )
