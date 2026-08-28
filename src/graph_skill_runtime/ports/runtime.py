"""Ports at the application boundary.

Protocols contain only public, provider-neutral contracts.  LangGraph,
provider SDKs, host sessions, and filesystem implementation details belong in
adapters that implement these protocols.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from graph_skill_runtime.domain.models import (
    AgentResult,
    AgentTask,
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
    RuntimeEvent,
    SubmitAgentResultRequest,
)


class AgentExecutor(Protocol):
    """Execute one agent task without owning graph checkpoint state."""

    @property
    def executor_id(self) -> str: ...

    def execute(self, task: AgentTask) -> AgentResult: ...


class CheckpointStore(Protocol):
    """Durably own graph state generations."""

    def save(self, run_id: str, generation: int, state: JsonObject) -> str: ...

    def load(self, checkpoint_ref: str) -> JsonObject: ...


class ArtifactStore(Protocol):
    """Materialize declared bytes and return a stable artifact reference."""

    def write(self, run_id: str, artifact_id: str, content: bytes) -> str: ...


class EventSink(Protocol):
    """Receive ordered runtime events."""

    def emit(self, event: RuntimeEvent) -> None: ...


class SkillSource(Protocol):
    """Read portable skill files without prescribing their storage backend."""

    def read_text(self, skill_root: Path, relative_path: str) -> str: ...


class RunSnapshotStore(Protocol):
    """Persist the exact immutable request before execution begins."""

    def save(self, request: RunRequest) -> str: ...

    def load(self, state_root: Path, run_id: str) -> RunRequest: ...


class RuntimeEngine(Protocol):
    """Current engine capabilities behind the application service."""

    def compile(self, request: CompileRequest) -> CompileResult: ...

    def predict(self, request: RunRequest) -> RunResult: ...

    def run(self, request: RunRequest) -> RunResult: ...

    def resume(self, request: ResumeRequest, run_request: RunRequest) -> RunResult: ...

    def submit_agent_result(
        self,
        request: SubmitAgentResultRequest,
        run_request: RunRequest,
    ) -> RunResult: ...

    def evaluate_golden(self, request: GoldenEvaluationRequest) -> GoldenEvaluationResult: ...

    def inspect(self, request: InspectRequest) -> InspectResult: ...
