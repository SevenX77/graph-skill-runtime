"""MCP v2 adapter; every tool delegates to one RuntimeApplication instance."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.composition import create_application
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
    RunResult,
    SubmitAgentResultRequest,
)


def create_server(application: RuntimeApplication | None = None) -> MCPServer[None]:
    """Create an isolated MCP server; importing the package writes nothing."""

    active_application = application or create_application()
    server: MCPServer[None] = MCPServer(
        name="gskill",
        title="Graph Skill Runtime",
        description="Compile, predict, run, resume, and inspect graph skills",
        version="1",
    )

    @server.tool(
        name="compile",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def compile_tool(request: CompileRequest) -> CompileResult:
        """Compile a graph skill and return all diagnostics from one pass."""

        return active_application.compile(request)

    @server.tool(
        name="resolve_run",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def resolve_run_tool(invocation: RunInvocation) -> ConfigResolution:
        """Resolve four configuration layers into an immutable run request."""

        return active_application.resolve_run(invocation)

    @server.tool(
        name="predict",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def predict_tool(request: PredictRequest) -> RunResult:
        """Predict a run without making real model calls."""

        return active_application.predict(request)

    @server.tool(
        name="run",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    def run_tool(invocation: RunInvocation) -> RunResult:
        """Run a graph skill with the explicitly resolved executor."""

        return active_application.run(invocation)

    @server.tool(
        name="resume",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    def resume_tool(request: ResumeRequest) -> RunResult:
        """Resume a previously persisted graph run."""

        return active_application.resume(request)

    @server.tool(
        name="submit_agent_result",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def submit_agent_result_tool(request: SubmitAgentResultRequest) -> RunResult:
        """Submit one host-native agent result to its durable checkpoint."""

        return active_application.submit_agent_result(request)

    @server.tool(
        name="inspect",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    def inspect_tool(request: InspectRequest) -> InspectResult:
        """Inspect the compiled graph and optional call graph."""

        return active_application.inspect(request)

    @server.tool(
        name="evaluate_golden",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    def evaluate_golden_tool(request: GoldenEvaluationRequest) -> GoldenEvaluationResult:
        """Evaluate a stored golden baseline."""

        return active_application.evaluate_golden(request)

    return server
