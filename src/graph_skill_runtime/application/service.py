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
    RunRequest,
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
        return self._engine.run(request)

    def resume(self, request: ResumeRequest) -> RunResult:
        loaded = self._load_matching_snapshot(
            state_root=Path(request.state_root),
            run_id=request.run_id,
            skill_root=request.skill_root,
        )
        if isinstance(loaded, RunResult):
            return loaded
        return self._engine.resume(request, loaded)

    def submit_agent_result(self, request: SubmitAgentResultRequest) -> RunResult:
        loaded = self._load_matching_snapshot(
            state_root=Path(request.state_root),
            run_id=request.run_id,
        )
        if isinstance(loaded, RunResult):
            return loaded
        return self._engine.submit_agent_result(request, loaded)

    def evaluate_golden(self, request: GoldenEvaluationRequest) -> GoldenEvaluationResult:
        return self._engine.evaluate_golden(request)

    def inspect(self, request: InspectRequest) -> InspectResult:
        return self._engine.inspect(request)

    def load_run_request(self, state_root: Path, run_id: str) -> ConfigResolution:
        request = self._snapshot_store.load(state_root, run_id)
        return ConfigResolution(profile=request.profile, request=request)

    def _load_matching_snapshot(
        self,
        *,
        state_root: Path,
        run_id: str,
        skill_root: str | None = None,
    ) -> RunRequest | RunResult:
        try:
            request = self._snapshot_store.load(state_root, run_id)
        except ValueError as exc:
            return RunResult(
                status="failed",
                run_id=run_id,
                mode="resume",
                error=RuntimeErrorPayload(
                    code=RuntimeErrorCode.SNAPSHOT_NOT_FOUND,
                    message=str(exc),
                ),
            )
        requested_state_root = state_root.resolve(strict=False)
        snapshot_state_root = Path(request.profile.state_root).resolve(strict=False)
        if requested_state_root != snapshot_state_root:
            return RunResult(
                status="failed",
                run_id=run_id,
                mode="resume",
                request=request,
                error=RuntimeErrorPayload(
                    code=RuntimeErrorCode.INVALID_REQUEST,
                    message="state_root does not match the immutable run snapshot",
                ),
            )
        if skill_root is not None and (
            Path(skill_root).resolve(strict=False)
            != Path(request.profile.skill_root).resolve(strict=False)
        ):
            return RunResult(
                status="failed",
                run_id=run_id,
                mode="resume",
                request=request,
                error=RuntimeErrorPayload(
                    code=RuntimeErrorCode.INVALID_REQUEST,
                    message="skill_root does not match the immutable run snapshot",
                ),
            )
        return request
