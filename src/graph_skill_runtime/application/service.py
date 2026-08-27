"""Single application-service exit used by Python, CLI, and MCP adapters."""

from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.application.config import ConfigResolver
from graph_skill_runtime.domain.models import (
    CompileRequest,
    CompileResult,
    ConfigResolution,
    GoldenEvaluationRequest,
    GoldenEvaluationResult,
    InspectRequest,
    InspectResult,
    PredictRequest,
    ResumeRequest,
    RunInvocation,
    RunPreset,
    RunResult,
    RuntimeErrorCode,
    RuntimeErrorPayload,
    RuntimeProfileOverlay,
    SubmitAgentResultRequest,
)
from graph_skill_runtime.ports.runtime import RunSnapshotStore, RuntimeEngine


class RuntimeApplication:
    """Own runtime use-case ordering without depending on a transport."""

    def __init__(
        self,
        *,
        config_resolver: ConfigResolver,
        engine: RuntimeEngine,
        snapshot_store: RunSnapshotStore,
    ) -> None:
        self._config_resolver = config_resolver
        self._engine = engine
        self._snapshot_store = snapshot_store

    def compile(self, request: CompileRequest) -> CompileResult:
        return self._engine.compile(request)

    def resolve_run(
        self,
        invocation: RunInvocation,
        *,
        portable_runtime: RuntimeProfileOverlay | None = None,
        portable_defaults: RunPreset | None = None,
    ) -> ConfigResolution:
        return self._config_resolver.resolve(
            invocation,
            portable_runtime=portable_runtime,
            portable_defaults=portable_defaults,
        )

    def predict(self, request: PredictRequest) -> RunResult:
        resolution = self.resolve_run(request.invocation)
        self._snapshot_store.save(resolution.request)
        return self._engine.predict(resolution.request)

    def run(self, invocation: RunInvocation) -> RunResult:
        resolution = self.resolve_run(invocation)
        request = resolution.request
        self._snapshot_store.save(request)
        executor_kind = request.profile.profile.executor.kind
        if executor_kind != "embedded":
            phase = "host-native adapter" if executor_kind == "host-native" else "CLI adapter"
            return RunResult(
                status="failed",
                run_id=request.run_id,
                mode="run",
                request=request,
                error=RuntimeErrorPayload(
                    code=RuntimeErrorCode.EXECUTOR_UNAVAILABLE,
                    message=f"{phase} is not implemented in Phase 1",
                    retryable=False,
                    details={"executor_kind": executor_kind},
                ),
            )
        return self._engine.run(request)

    def resume(self, request: ResumeRequest) -> RunResult:
        return self._engine.resume(request)

    def submit_agent_result(self, request: SubmitAgentResultRequest) -> RunResult:
        return RunResult(
            status="failed",
            run_id=request.run_id,
            mode="resume",
            error=RuntimeErrorPayload(
                code=RuntimeErrorCode.NOT_IMPLEMENTED,
                message="host-native result submission belongs to Phase 3",
                retryable=False,
                details={"checkpoint_ref": request.checkpoint_ref},
            ),
        )

    def evaluate_golden(self, request: GoldenEvaluationRequest) -> GoldenEvaluationResult:
        return self._engine.evaluate_golden(request)

    def inspect(self, request: InspectRequest) -> InspectResult:
        return self._engine.inspect(request)

    def load_run_request(self, state_root: Path, run_id: str) -> ConfigResolution:
        request = self._snapshot_store.load(state_root, run_id)
        return ConfigResolution(profile=request.profile, request=request)
