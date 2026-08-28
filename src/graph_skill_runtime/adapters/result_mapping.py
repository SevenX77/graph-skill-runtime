"""Map characterized core results onto the stable application contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import TypeAdapter, ValidationError

from graph_skill_runtime.core.result import RunResult as CoreRunResult
from graph_skill_runtime.domain.models import (
    JsonObject,
    RunRequest,
    RunResult,
    RuntimeErrorCode,
    RuntimeErrorPayload,
)

_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)


def json_object(value: object) -> JsonObject:
    try:
        return _JSON_OBJECT_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError(f"engine returned a non-JSON object: {exc}") from exc


def runtime_error(result: CoreRunResult) -> RuntimeErrorPayload:
    if result.error is not None:
        return RuntimeErrorPayload(
            code=RuntimeErrorCode.RUN_FAILED,
            message=result.error.message,
            phase=result.error.phase_id,
            source_path=result.error.source_path,
            details={
                "engine_code": result.error.code,
                "engine_details": json_object(result.error.details),
            },
        )
    return RuntimeErrorPayload(
        code=RuntimeErrorCode.RUN_FAILED,
        message="the engine did not complete the run",
    )


def run_result(
    result: CoreRunResult,
    *,
    request: RunRequest,
    mode: Literal["run", "predict", "resume"],
) -> RunResult:
    status: Literal["completed", "failed", "paused", "agent_required"]
    if result.paused_at is not None:
        status = "paused"
    elif result.success:
        status = "completed"
    else:
        status = "failed"
    return RunResult(
        status=status,
        run_id=result.run_id,
        mode=mode,
        request=request,
        outputs=json_object(result.context),
        trace_path=str(result.trace_path) if result.trace_path is not None else None,
        error=runtime_error(result) if status == "failed" else None,
    )


def failed_run(
    request: RunRequest,
    *,
    mode: Literal["run", "resume"],
    code: RuntimeErrorCode,
    message: str,
    details: JsonObject | None = None,
) -> RunResult:
    return RunResult(
        status="failed",
        run_id=request.run_id,
        mode=mode,
        request=request,
        error=RuntimeErrorPayload(
            code=code,
            message=message,
            details=details or {},
        ),
    )
