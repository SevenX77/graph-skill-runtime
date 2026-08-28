"""Adapter from the new application contract to the extracted engine core."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

from graph_skill_runtime.core.compiler import CompileIssue as CoreCompileIssue
from graph_skill_runtime.core.compiler import CompileResult as CoreCompileResult
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import GraphAgentError
from graph_skill_runtime.core.loader import CompiledSkill
from graph_skill_runtime.core.manifest import AgentNodeAST, SubgraphNodeAST
from graph_skill_runtime.core.result import RunResult as CoreRunResult
from graph_skill_runtime.domain.models import (
    CompileDiagnostic,
    CompileRequest,
    CompileResult,
    GoldenEvaluationRequest,
    GoldenEvaluationResult,
    InspectRequest,
    InspectResult,
    JsonObject,
    ResumeRequest,
    RunRequest,
    RunResult,
    RuntimeErrorCode,
    RuntimeErrorPayload,
)

_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)


class _PredictCallable(Protocol):
    def __call__(
        self,
        skill_path: str | Path,
        *,
        workspace_dir: Path,
        thread_id: str,
        **inputs: JsonValue,
    ) -> CoreRunResult: ...


class _RunCallable(Protocol):
    def __call__(
        self,
        skill_path: str | Path,
        *,
        workspace_dir: Path,
        thread_id: str,
        **inputs: JsonValue,
    ) -> CoreRunResult: ...


def _json_object(value: object) -> JsonObject:
    try:
        return _JSON_OBJECT_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError(f"engine returned a non-JSON object: {exc}") from exc


def _diagnostic(issue: CoreCompileIssue) -> CompileDiagnostic:
    severity: Literal["fatal", "warning", "info"]
    if issue.severity == "WARNING":
        severity = "warning"
    elif issue.severity == "INFO":
        severity = "info"
    else:
        severity = "fatal"
    return CompileDiagnostic(
        code=issue.rule_id,
        severity=severity,
        message=issue.message,
        source_path=issue.source_path,
        line=issue.line,
        field_path=issue.field_path,
        conflicting_phase=issue.conflicting_phase,
    )


def _core_compile_result(value: object) -> CoreCompileResult | None:
    return value if isinstance(value, CoreCompileResult) else None


def _compile_failure(exc: Exception) -> CompileResult:
    core_result = _core_compile_result(getattr(exc, "compile_result", None))
    if core_result is not None:
        diagnostics = tuple(_diagnostic(issue) for issue in core_result.issues)
    else:
        code = RuntimeErrorCode.COMPILE_FAILED.value
        source_path: str | None = None
        field_path: str | None = None
        if isinstance(exc, GraphAgentError) and exc.payload is not None:
            code = exc.payload.code
            source_path = exc.payload.source_path
            field_path = exc.payload.field_path
        diagnostics = (
            CompileDiagnostic(
                code=code,
                severity="fatal",
                message=str(exc),
                source_path=source_path,
                field_path=field_path,
            ),
        )
    if not any(item.severity == "fatal" for item in diagnostics):
        diagnostics += (
            CompileDiagnostic(
                code=RuntimeErrorCode.COMPILE_FAILED.value,
                severity="fatal",
                message=str(exc),
            ),
        )
    return CompileResult(status="failed", diagnostics=diagnostics)


def _runtime_error(result: CoreRunResult) -> RuntimeErrorPayload:
    if result.error is not None:
        return RuntimeErrorPayload(
            code=RuntimeErrorCode.RUN_FAILED,
            message=result.error.message,
            phase=result.error.phase_id,
            source_path=result.error.source_path,
            details={
                "engine_code": result.error.code,
                "engine_details": _json_object(result.error.details),
            },
        )
    return RuntimeErrorPayload(
        code=RuntimeErrorCode.RUN_FAILED,
        message="the engine did not complete the run",
    )


def _run_result(
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
        outputs=_json_object(result.context),
        trace_path=str(result.trace_path) if result.trace_path is not None else None,
        error=_runtime_error(result) if status == "failed" else None,
    )


def _skill_id(compiled: CompiledSkill) -> str:
    if compiled.skill_manifest is not None:
        return compiled.skill_manifest.name
    return compiled.skill_root.name


def _invalid_artifact_request(request: RunRequest, compiled: CompiledSkill) -> RunResult | None:
    requested_ids = [item.artifact_id for item in request.artifact_requests]
    if len(requested_ids) != len(set(requested_ids)):
        return RunResult(
            status="failed",
            run_id=request.run_id,
            mode="run",
            request=request,
            error=RuntimeErrorPayload(
                code=RuntimeErrorCode.INVALID_REQUEST,
                message="artifact_requests must not repeat an artifact_id",
            ),
        )
    declared_ids = {item.artifact_id for item in compiled.manifest.artifacts}
    unknown = sorted(set(requested_ids) - declared_ids)
    if not unknown:
        return None
    return RunResult(
        status="failed",
        run_id=request.run_id,
        mode="run",
        request=request,
        error=RuntimeErrorPayload(
            code=RuntimeErrorCode.INVALID_REQUEST,
            message="artifact request references undeclared artifact ids: " + ", ".join(unknown),
            details={"unknown_artifact_ids": cast(JsonValue, unknown)},
        ),
    )


def _compiled_for_run(request: RunRequest) -> CompiledSkill | RunResult:
    try:
        compiled: CompiledSkill = compile_skill(request.profile.skill_root)
    except Exception as exc:
        failed = _compile_failure(exc)
        return RunResult(
            status="failed",
            run_id=request.run_id,
            mode="run",
            request=request,
            error=RuntimeErrorPayload(
                code=RuntimeErrorCode.COMPILE_FAILED,
                message="portable gSkill compilation failed",
            ),
            diagnostics=failed.diagnostics,
        )
    invalid = _invalid_artifact_request(request, compiled)
    return invalid or compiled


class CurrentEngineAdapter:
    """Keep the characterized engine behind the new stable application Port."""

    def compile(self, request: CompileRequest) -> CompileResult:
        try:
            compiled = compile_skill(request.skill_root, cache=request.cache)
        except Exception as exc:
            return _compile_failure(exc)
        core_result = _core_compile_result(getattr(compiled, "compile_result", None))
        diagnostics = (
            tuple(_diagnostic(issue) for issue in core_result.issues)
            if core_result is not None
            else ()
        )
        return CompileResult(
            status="passed",
            skill_id=_skill_id(compiled),
            diagnostics=diagnostics,
        )

    def predict(self, request: RunRequest) -> RunResult:
        from graph_skill_runtime.core.runner import predict_skill

        checked = _compiled_for_run(request)
        if isinstance(checked, RunResult):
            return checked.model_copy(update={"mode": "predict"})
        predict_call = cast(_PredictCallable, predict_skill)
        result = predict_call(
            request.profile.skill_root,
            workspace_dir=Path(request.profile.state_root),
            thread_id=request.run_id,
            **request.inputs,
        )
        return _run_result(result, request=request, mode="predict")

    def run(self, request: RunRequest) -> RunResult:
        from graph_skill_runtime.core.runner import run_skill

        checked = _compiled_for_run(request)
        if isinstance(checked, RunResult):
            return checked
        run_call = cast(_RunCallable, run_skill)
        result = run_call(
            request.profile.skill_root,
            workspace_dir=Path(request.profile.state_root),
            thread_id=request.run_id,
            **request.inputs,
        )
        return _run_result(result, request=request, mode="run")

    def resume(self, request: ResumeRequest) -> RunResult:
        return RunResult(
            status="failed",
            run_id=request.run_id,
            mode="resume",
            error=RuntimeErrorPayload(
                code=RuntimeErrorCode.NOT_IMPLEMENTED,
                message="typed durable resume with host-native handoff belongs to Phase 3",
                details={"checkpoint_ref": request.checkpoint_ref},
            ),
        )

    def evaluate_golden(self, request: GoldenEvaluationRequest) -> GoldenEvaluationResult:
        from graph_skill_runtime.core.runner import evaluate_golden_baseline

        try:
            result = evaluate_golden_baseline(
                request.skill_root,
                workspace_dir=Path(request.state_root).resolve(strict=True),
                baseline_id=request.baseline_id,
            )
            details = _json_object(result)
        except Exception as exc:
            return GoldenEvaluationResult(
                status="failed",
                baseline_id=request.baseline_id,
                error=RuntimeErrorPayload(
                    code=RuntimeErrorCode.RUN_FAILED,
                    message=str(exc),
                ),
            )
        passed_value: JsonValue | None = details.get("passed")
        passed = bool(passed_value) if passed_value is not None else True
        return GoldenEvaluationResult(
            status="passed" if passed else "failed",
            baseline_id=request.baseline_id,
            details=details,
            error=None
            if passed
            else RuntimeErrorPayload(
                code=RuntimeErrorCode.RUN_FAILED,
                message="golden evaluation failed",
            ),
        )

    def inspect(self, request: InspectRequest) -> InspectResult:
        try:
            compiled: CompiledSkill = compile_skill(request.skill_root)
        except Exception as exc:
            failed = _compile_failure(exc)
            return InspectResult(diagnostics=failed.diagnostics)
        call_edges: set[tuple[str, str]] = set()
        for graph_id, graph in compiled.graph_registry.items():
            for node in graph.nodes:
                if isinstance(node.ast, SubgraphNodeAST):
                    call_edges.add((graph_id, node.ast.graph))
                elif isinstance(node.ast, AgentNodeAST):
                    call_edges.update((graph_id, item.graph) for item in node.ast.subgraphs)
        return InspectResult(
            skill_id=_skill_id(compiled),
            graphs=tuple(sorted(compiled.graph_registry)),
            call_edges=tuple(sorted(call_edges)) if request.include_call_graph else (),
        )
