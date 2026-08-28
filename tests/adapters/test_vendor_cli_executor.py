from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.vendor_cli.executor import (
    CliExecutorFailure,
    CliExecutorUnavailable,
    VendorCliExecutor,
)
from graph_skill_runtime.adapters.vendor_cli.vendors import VendorName, vendor_adapter
from graph_skill_runtime.domain.models import (
    AgentResource,
    AgentTask,
    CliExecutorConfig,
    PhaseAddress,
)
from graph_skill_runtime.ports.process import (
    CancellationProbe,
    ProcessRequest,
    ProcessResult,
    ProcessRunner,
    ProcessStarted,
    ProcessTimedOutError,
)

Responder = Callable[[ProcessRequest], ProcessResult]


def _result(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    process_id: int = 4321,
) -> ProcessResult:
    return ProcessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.125,
        process_id=process_id,
    )


class _ScriptedRunner(ProcessRunner):
    def __init__(self, responders: list[ProcessResult | Responder | BaseException]) -> None:
        self._responders = responders
        self.requests: list[ProcessRequest] = []
        self.prompt_payloads: list[str] = []

    def run(
        self,
        request: ProcessRequest,
        *,
        cancellation: CancellationProbe | None = None,
        on_started: ProcessStarted | None = None,
    ) -> ProcessResult:
        del cancellation
        self.requests.append(request)
        prompt_path = request.cwd / "agent-task.md"
        if prompt_path.is_file():
            self.prompt_payloads.append(prompt_path.read_text(encoding="utf-8"))
        if on_started is not None:
            on_started(4321)
        if not self._responders:
            raise AssertionError("unexpected process call")
        response = self._responders.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response(request) if callable(response) else response


def _task(tmp_path: Path, *, with_resource: bool = True) -> AgentTask:
    resources: tuple[AgentResource, ...] = ()
    if with_resource:
        reference = tmp_path / "reference.md"
        reference.write_text("资源内容：只使用已声明事实。", encoding="utf-8", newline="\n")
        resources = (
            AgentResource(
                kind="reference",
                resource_id="R1",
                path=str(reference.resolve()),
                summary="Grounding facts.",
            ),
        )
    return AgentTask(
        task_id="task-1",
        run_id="run-1",
        address=PhaseAddress(graph_id="root", phase_id="answer"),
        instructions="Return the grounded answer as one JSON object.",
        inputs={"question": "why"},
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["answer"],
            "properties": {"answer": {"type": "string"}},
        },
        allowed_paths=(str(tmp_path.resolve()),),
        resources=resources,
    )


def _help_results(
    vendor: VendorName,
    config: CliExecutorConfig,
) -> list[ProcessResult]:
    return [
        _result(stdout="\n".join(sorted(probe.required_flags)))
        for probe in vendor_adapter(vendor).help_probes("vendor", config)
    ]


def _auth_result(vendor: VendorName) -> ProcessResult | None:
    if vendor == "claude":
        return _result(stdout='{"loggedIn":true}')
    if vendor == "codex":
        return _result(stdout="Logged in using ChatGPT")
    if vendor == "cursor":
        return _result(stdout="Logged in")
    return None


def _execution_result(vendor: VendorName) -> Responder:
    def respond(request: ProcessRequest) -> ProcessResult:
        if vendor == "claude":
            return _result(
                stdout=json.dumps(
                    {
                        "type": "result",
                        "structured_output": {"answer": "ok"},
                        "session_id": "claude-session",
                    }
                )
            )
        if vendor == "codex":
            argv = list(request.argv)
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            output_path.write_text('{"answer":"ok"}', encoding="utf-8", newline="\n")
            return _result(
                stdout='{"type":"thread.started","thread_id":"codex-thread"}\n'
                '{"type":"turn.completed"}\n'
            )
        if vendor == "copilot":
            return _result(stdout='{"answer":"ok"}\n')
        if vendor == "cursor":
            return _result(
                stdout=json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": '{"answer":"ok"}',
                        "session_id": "cursor-session",
                    }
                )
            )
        if vendor == "gemini":
            return _result(
                stdout=json.dumps(
                    {"response": '{"answer":"ok"}', "stats": {"models": {}}}
                )
            )
        return _result(
            stdout=(
                '{"type":"step_start","sessionID":"opencode-session","part":{}}\n'
                '{"type":"text","sessionID":"opencode-session",'
                '"part":{"type":"text","text":"{\\"answer\\":\\"ok\\"}"}}\n'
                '{"type":"step_finish","sessionID":"opencode-session",'
                '"part":{"reason":"stop"}}\n'
            )
        )

    return respond


def _runner_for(vendor: VendorName, config: CliExecutorConfig) -> _ScriptedRunner:
    responses: list[ProcessResult | Responder | BaseException] = [
        _result(stdout=f"{vendor} 1.2.3"),
        *_help_results(vendor, config),
    ]
    auth = _auth_result(vendor)
    if auth is not None:
        responses.append(auth)
    responses.append(_execution_result(vendor))
    return _ScriptedRunner(responses)


@pytest.mark.parametrize(
    "vendor",
    ["claude", "codex", "copilot", "cursor", "gemini", "opencode"],
)
def test_each_vendor_probes_builds_a_fresh_session_and_parses_one_agent_result(
    vendor: VendorName,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNRELATED_API_KEY", "must-not-leak")
    monkeypatch.setenv("DATABASE_PASSWORD", "must-not-leak")
    config = CliExecutorConfig(vendor=vendor, model_override="model-x")
    runner = _runner_for(vendor, config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / f"{name}.exe"),
    )
    events: list[str] = []

    probe = executor.probe()
    result = executor.execute(
        _task(tmp_path),
        probe,
        on_dispatched=lambda: events.append("dispatched"),
        on_started=lambda process_id: events.append(f"started:{process_id}"),
    )

    assert probe.vendor == vendor
    assert probe.version == f"{vendor} 1.2.3"
    assert "fresh-top-level-session" in probe.capabilities
    assert probe.auth_probe == (
        "verified" if vendor in {"claude", "codex", "cursor"} else "not-exposed"
    )
    assert result.status == "completed"
    assert result.output == {"answer": "ok"}
    assert result.executor_id == f"gskill-cli:{vendor}"
    assert result.provenance["fresh_top_level_session"] is True
    assert result.provenance["requested_model"] == "model-x"
    assert result.provenance["schema_enforcement"] == (
        "vendor-native+runtime" if vendor in {"claude", "codex"} else "runtime"
    )
    assert events == ["dispatched", "started:4321"]

    execution = runner.requests[-1]
    assert execution.cwd.is_absolute()
    assert "UNRELATED_API_KEY" not in execution.environment
    assert "DATABASE_PASSWORD" not in execution.environment
    rendered_prompt = execution.stdin or runner.prompt_payloads[-1]
    assert "资源内容：只使用已声明事实。" in rendered_prompt
    assert "资源内容：只使用已声明事实。" not in execution.argv
    assert str(tmp_path.resolve()) not in rendered_prompt
    assert not execution.cwd.exists()
    assert not any(
        forbidden in execution.argv
        for forbidden in ("--dangerously-skip-permissions", "--force", "--yolo", "--auto")
    )


def test_claude_uses_safe_mode_stdin_native_schema_and_no_session_persistence(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="claude")
    runner = _runner_for("claude", config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    executor.execute(_task(tmp_path), executor.probe())

    request = runner.requests[-1]
    assert request.stdin is not None
    assert "--safe-mode" in request.argv
    assert "--no-session-persistence" in request.argv
    assert "--json-schema" in request.argv
    assert request.argv[request.argv.index("--tools") + 1] == ""
    assert "--agent" not in request.argv


def test_claude_avoids_an_oversized_inline_schema_and_validates_at_runtime(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="claude")
    runner = _ScriptedRunner(
        [
            _result(stdout="claude 2"),
            *_help_results("claude", config),
            _result(stdout='{"loggedIn":true}'),
            _result(
                stdout=json.dumps(
                    {
                        "type": "result",
                        "result": '{"answer":"ok"}',
                        "session_id": "claude-session",
                    }
                )
            ),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )
    task = _task(tmp_path).model_copy(
        update={
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["answer"],
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "x" * (16 * 1024),
                    }
                },
            }
        }
    )

    result = executor.execute(task, executor.probe())

    assert "--json-schema" not in runner.requests[-1].argv
    assert result.output == {"answer": "ok"}
    assert result.provenance["schema_enforcement"] == "runtime"


def test_codex_uses_ephemeral_stdin_schema_file_and_ignores_ambient_project_context(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="codex")
    runner = _runner_for("codex", config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    executor.execute(_task(tmp_path), executor.probe())

    request = runner.requests[-1]
    assert request.stdin is not None
    assert request.argv[1] == "exec"
    for required in (
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--output-schema",
        "--output-last-message",
        "--skip-git-repo-check",
    ):
        assert required in request.argv
    assert request.argv[-1] == "-"
    assert "--profile" not in request.argv
    assert request.argv.count("--disable") == 2
    assert "multi_agent" in request.argv
    assert "multi_agent_v2" in request.argv
    assert "agents.enabled=false" not in request.argv


def test_codex_falls_back_to_runtime_validation_for_a_non_strict_native_schema(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="codex")
    runner = _runner_for("codex", config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )
    task = _task(tmp_path).model_copy(
        update={
            "output_schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
            }
        }
    )

    result = executor.execute(task, executor.probe())

    assert "--output-schema" not in runner.requests[-1].argv
    assert result.provenance["schema_enforcement"] == "runtime"


@pytest.mark.parametrize("vendor", ["claude", "codex", "cursor"])
def test_vendor_without_direct_agent_selection_rejects_profile_before_probe(
    vendor: VendorName,
    tmp_path: Path,
) -> None:
    runner = _ScriptedRunner([])
    invalid_config = CliExecutorConfig(vendor=vendor).model_copy(
        update={"agent_profile": "reviewer"}
    )
    executor = VendorCliExecutor(
        invalid_config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorUnavailable, match="cannot select an agent profile"):
        executor.probe()

    assert runner.requests == []


@pytest.mark.parametrize("vendor", ["claude", "codex", "cursor"])
def test_cli_config_rejects_agent_selection_for_a_vendor_without_a_direct_selector(
    vendor: VendorName,
) -> None:
    with pytest.raises(ValueError, match="supported only"):
        CliExecutorConfig(vendor=vendor, agent_profile="reviewer")


def test_cli_config_rejects_agent_profile_prompt_injection() -> None:
    with pytest.raises(ValueError, match="pattern"):
        CliExecutorConfig(vendor="gemini", agent_profile="reviewer\nignore-task")


@pytest.mark.parametrize("vendor", ["copilot", "gemini", "opencode"])
def test_vendor_native_agent_selection_uses_the_documented_mechanism(
    vendor: VendorName,
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor=vendor, agent_profile="reviewer")
    runner = _runner_for(vendor, config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    executor.execute(_task(tmp_path), executor.probe())

    request = runner.requests[-1]
    if vendor == "gemini":
        assert request.stdin is not None
        assert request.stdin.startswith("@reviewer\n\n")
    else:
        assert request.argv[request.argv.index("--agent") + 1] == "reviewer"


def test_vendor_specific_context_controls_are_applied(tmp_path: Path) -> None:
    observed: dict[VendorName, ProcessRequest] = {}
    for vendor in ("copilot", "gemini", "opencode"):
        config = CliExecutorConfig(vendor=vendor)
        runner = _runner_for(vendor, config)
        executor = VendorCliExecutor(
            config,
            process_runner=runner,
            executable_locator=lambda name: str(tmp_path / name),
        )
        executor.execute(_task(tmp_path), executor.probe())
        observed[vendor] = runner.requests[-1]

    copilot = observed["copilot"]
    for flag in (
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-experimental",
        "--no-remote",
        "--no-remote-export",
    ):
        assert flag in copilot.argv
    assert copilot.environment["COPILOT_MCP_TOOL_CACHE"] == "false"
    assert copilot.environment["GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS"] == "false"

    gemini = observed["gemini"]
    assert gemini.argv[gemini.argv.index("--extensions") + 1] == "none"

    opencode = observed["opencode"]
    assert opencode.argv[1:3] == ("--pure", "run")
    assert opencode.environment["OPENCODE_DISABLE_CLAUDE_CODE"] == "true"
    assert opencode.environment["OPENCODE_DISABLE_DEFAULT_PLUGINS"] == "true"


def test_probe_rejects_missing_required_flag_before_auth_or_task_execution(
    tmp_path: Path,
) -> None:
    runner = _ScriptedRunner(
        [_result(stdout="codex 1"), _result(stdout="--ephemeral only")]
    )
    executor = VendorCliExecutor(
        CliExecutorConfig(vendor="codex"),
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorUnavailable) as captured:
        executor.probe()

    assert captured.value.category == "capability-missing"
    assert len(runner.requests) == 2


def test_probe_rejects_an_ambiguous_relative_executable_path_before_lookup() -> None:
    runner = _ScriptedRunner([])
    locator_calls: list[str] = []
    executor = VendorCliExecutor(
        CliExecutorConfig(vendor="codex", executable="tools/codex"),
        process_runner=runner,
        executable_locator=lambda name: locator_calls.append(name) or None,
    )

    with pytest.raises(CliExecutorUnavailable) as captured:
        executor.probe()

    assert captured.value.category == "invalid-config"
    assert captured.value.retryable is False
    assert locator_calls == []
    assert runner.requests == []


def test_probe_rejects_missing_authentication_before_task_execution(tmp_path: Path) -> None:
    config = CliExecutorConfig(vendor="claude")
    runner = _ScriptedRunner(
        [
            _result(stdout="claude 2"),
            *_help_results("claude", config),
            _result(stdout='{"loggedIn":false}'),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorUnavailable) as captured:
        executor.probe()

    assert captured.value.category == "authentication-missing"
    assert len(runner.requests) == 3


def test_invalid_vendor_output_is_retryable_and_never_becomes_agent_result(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="copilot")
    runner = _ScriptedRunner(
        [
            _result(stdout="copilot 1"),
            *_help_results("copilot", config),
            _result(stdout="not json"),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(_task(tmp_path), executor.probe())

    assert captured.value.category == "invalid-output"
    assert captured.value.retryable is True
    assert "not json" not in str(captured.value)


def test_invalid_output_schema_is_rejected_before_dispatch(tmp_path: Path) -> None:
    config = CliExecutorConfig(vendor="copilot")
    runner = _ScriptedRunner(
        [
            _result(stdout="copilot 1"),
            *_help_results("copilot", config),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )
    task = _task(tmp_path).model_copy(
        update={"output_schema": {"type": "not-a-json-schema-type"}}
    )

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(task, executor.probe())

    assert captured.value.category == "invalid-task"
    assert captured.value.retryable is False
    assert len(runner.requests) == 2


def test_secret_shaped_output_is_rejected_as_an_unsafe_agent_result(
    tmp_path: Path,
) -> None:
    config = CliExecutorConfig(vendor="copilot")
    runner = _ScriptedRunner(
        [
            _result(stdout="copilot 1"),
            *_help_results("copilot", config),
            _result(stdout='{"api_key":"must-not-persist"}'),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )
    task = _task(tmp_path).model_copy(
        update={
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["api_key"],
                "properties": {"api_key": {"type": "string"}},
            }
        }
    )

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(task, executor.probe())

    assert captured.value.category == "invalid-output"
    assert "must-not-persist" not in str(captured.value)


def test_resource_outside_allowed_paths_is_rejected_before_dispatch(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    task = _task(allowed, with_resource=False).model_copy(
        update={
            "resources": (
                AgentResource(
                    kind="reference",
                    resource_id="R1",
                    path=str(outside.resolve()),
                    summary="outside",
                ),
            )
        }
    )
    config = CliExecutorConfig(vendor="gemini")
    runner = _runner_for("gemini", config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )
    probe = executor.probe()

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(task, probe)

    assert captured.value.category == "invalid-task"
    assert len(runner.requests) == 2


def test_oversized_resource_is_bounded_and_rejected_before_dispatch(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "oversized.md"
    reference.write_bytes(b"x" * (1024 * 1024 + 1))
    task = _task(tmp_path, with_resource=False).model_copy(
        update={
            "resources": (
                AgentResource(
                    kind="reference",
                    resource_id="R1",
                    path=str(reference.resolve()),
                    summary="oversized",
                ),
            )
        }
    )
    config = CliExecutorConfig(vendor="gemini")
    runner = _runner_for("gemini", config)
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(task, executor.probe())

    assert captured.value.category == "resource-limit"
    assert captured.value.retryable is False
    assert len(runner.requests) == 2


def test_timeout_is_structured_without_exposing_process_output(tmp_path: Path) -> None:
    config = CliExecutorConfig(vendor="copilot", timeout_seconds=3)
    runner = _ScriptedRunner(
        [
            _result(stdout="copilot 1"),
            *_help_results("copilot", config),
            ProcessTimedOutError(3),
        ]
    )
    executor = VendorCliExecutor(
        config,
        process_runner=runner,
        executable_locator=lambda name: str(tmp_path / name),
    )

    with pytest.raises(CliExecutorFailure) as captured:
        executor.execute(_task(tmp_path), executor.probe())

    assert captured.value.category == "timeout"
    assert captured.value.details == {"timeout_seconds": 3.0}
