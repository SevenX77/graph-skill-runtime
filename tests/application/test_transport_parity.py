from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.adapters.mcp import create_server
from graph_skill_runtime.application.config import ConfigResolver
from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.domain.models import (
    CompileRequest,
    CompileResult,
    GoldenEvaluationRequest,
    GoldenEvaluationResult,
    InspectRequest,
    InspectResult,
    ResumeRequest,
    RunInvocation,
    RunRequest,
    RunResult,
    SubmitAgentResultRequest,
)
from graph_skill_runtime.sdk import compile as sdk_compile


class _RecordingEngine:
    def __init__(self) -> None:
        self.compile_requests: list[CompileRequest] = []

    def compile(self, request: CompileRequest) -> CompileResult:
        self.compile_requests.append(request)
        return CompileResult(status="passed", skill_id="shared-service")

    def predict(self, request: RunRequest) -> RunResult:
        return RunResult(status="completed", run_id=request.run_id, mode="predict", request=request)

    def run(self, request: RunRequest) -> RunResult:
        return RunResult(status="completed", run_id=request.run_id, mode="run", request=request)

    def resume(self, request: ResumeRequest, run_request: RunRequest) -> RunResult:
        del run_request
        return RunResult(status="completed", run_id=request.run_id, mode="resume")

    def submit_agent_result(
        self,
        request: SubmitAgentResultRequest,
        run_request: RunRequest,
    ) -> RunResult:
        del request
        return RunResult(
            status="completed",
            run_id=run_request.run_id,
            mode="resume",
            request=run_request,
        )

    def evaluate_golden(self, request: GoldenEvaluationRequest) -> GoldenEvaluationResult:
        return GoldenEvaluationResult(status="passed", baseline_id=request.baseline_id)

    def inspect(self, request: InspectRequest) -> InspectResult:
        return InspectResult(skill_id=Path(request.skill_root).name)


class _MemorySnapshots:
    def __init__(self) -> None:
        self.requests: list[RunRequest] = []

    def save(self, request: RunRequest) -> str:
        self.requests.append(request)
        return f"memory://{request.run_id}"

    def load(self, state_root: Path, run_id: str) -> RunRequest:
        del state_root
        return next(request for request in self.requests if request.run_id == run_id)


def _application(tmp_path: Path) -> tuple[RuntimeApplication, _RecordingEngine, _MemorySnapshots]:
    engine = _RecordingEngine()
    snapshots = _MemorySnapshots()
    application = RuntimeApplication(
        config_resolver=ConfigResolver(user_config_path=tmp_path / "missing.toml"),
        engine=engine,
        snapshot_store=snapshots,
    )
    return application, engine, snapshots


def test_sdk_cli_and_mcp_compile_are_projections_of_one_application_service(
    tmp_path: Path, capsys: object
) -> None:
    application, engine, _ = _application(tmp_path)
    request = CompileRequest(skill_root=str(tmp_path), cache=False)

    sdk_result = sdk_compile(request, application=application)

    assert cli_main(["compile", str(tmp_path), "--no-cache"], application=application) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    cli_payload = json.loads(captured.out)

    server = create_server(application)
    mcp_result = asyncio.run(
        server.call_tool("compile", {"request": request.model_dump(mode="json")})
    )

    assert cli_payload == sdk_result.model_dump(mode="json")
    assert mcp_result.structured_content == sdk_result.model_dump(mode="json")
    assert engine.compile_requests == [request, request, request]


def test_default_host_native_run_delegates_to_engine_and_keeps_request_snapshot(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    application, _, snapshots = _application(tmp_path)

    result = application.run(
        RunInvocation(skill_root=str(skill_root), run_id="host-required")
    )

    assert result.status == "completed"
    assert len(snapshots.requests) == 1
    assert snapshots.requests[0].profile.profile.executor.kind == "host-native"


def test_mcp_exposes_the_same_eight_application_use_cases(tmp_path: Path) -> None:
    application, _, _ = _application(tmp_path)
    tools = {
        tool.name: tool for tool in asyncio.run(create_server(application).list_tools())
    }
    assert set(tools) == {
        "compile",
        "evaluate_golden",
        "inspect",
        "predict",
        "resolve_run",
        "resume",
        "run",
        "submit_agent_result",
    }
    expected_annotations = {
        "compile": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "resolve_run": {"readOnlyHint": True, "openWorldHint": False},
        "predict": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "run": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "resume": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "submit_agent_result": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inspect": {"readOnlyHint": True, "openWorldHint": False},
        "evaluate_golden": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    }
    actual_annotations = {
        name: tool.annotations.model_dump(by_alias=True, exclude_none=True)
        if tool.annotations is not None
        else None
        for name, tool in tools.items()
    }
    assert actual_annotations == expected_annotations


@pytest.mark.parametrize("executor_args", [[], ["--executor", "embedded"]])
def test_cli_rejects_vendor_without_cli_executor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    executor_args: list[str],
) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    application, _, _ = _application(tmp_path)

    exit_code = cli_main(
        ["run", str(skill_root), *executor_args, "--vendor", "claude"],
        application=application,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["code"] == "GSKILL_INVALID_REQUEST"
    assert payload["message"] == "--vendor requires --executor=cli"


def test_cli_projects_all_vendor_runtime_options_into_the_resolved_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    executable = tmp_path / "vendor-cli"
    application, _, _ = _application(tmp_path)

    exit_code = cli_main(
        [
            "config",
            "resolve",
            str(skill_root),
            "--run-id",
            "cli-options",
            "--executor",
            "cli",
            "--vendor",
            "copilot",
            "--agent-profile",
            "reviewer",
            "--model",
            "model-x",
            "--executable",
            str(executable),
            "--timeout-seconds",
            "37.5",
        ],
        application=application,
    )
    payload = json.loads(capsys.readouterr().out)
    executor = payload["profile"]["profile"]["executor"]

    assert exit_code == 0
    assert executor == {
        "schema_version": "gskill.executor.v1",
        "kind": "cli",
        "vendor": "copilot",
        "agent_profile": "reviewer",
        "model_override": "model-x",
        "executable": str(executable),
        "timeout_seconds": 37.5,
    }


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--agent-profile", "reviewer"),
        ("--model", "model-x"),
        ("--executable", "codex-custom"),
        ("--timeout-seconds", "30"),
    ],
)
def test_cli_rejects_each_vendor_option_without_cli_executor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
    value: str,
) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    application, _, _ = _application(tmp_path)

    exit_code = cli_main(
        ["run", str(skill_root), option, value],
        application=application,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["code"] == "GSKILL_INVALID_REQUEST"
    assert payload["message"] == f"{option} requires --executor=cli"


def test_cli_rejects_non_positive_vendor_timeout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    application, _, _ = _application(tmp_path)

    exit_code = cli_main(
        [
            "run",
            str(skill_root),
            "--executor",
            "cli",
            "--vendor",
            "codex",
            "--timeout-seconds",
            "0",
        ],
        application=application,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["code"] == "GSKILL_INVALID_REQUEST"
    assert "timeout_seconds" in payload["message"]
