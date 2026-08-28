from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from graph_skill_runtime.adapters.engine import CurrentEngineAdapter
from graph_skill_runtime.adapters.vendor_cli.executor import (
    CliExecutorFailure,
    CliExecutorUnavailable,
    DispatchCallback,
    StartedCallback,
    VendorProbe,
)
from graph_skill_runtime.adapters.vendor_cli.runtime import CliRuntimeAdapter
from graph_skill_runtime.composition import create_application
from graph_skill_runtime.domain.models import (
    AgentResult,
    AgentTask,
    CliExecutorConfig,
    RunInvocation,
    RuntimeErrorCode,
    RuntimeProfileOverlay,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _logic_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Prove that pure logic does not require a vendor CLI.
---

Run the graph.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: One deterministic phase.
io:
  inputs:
    type: object
    required: [value]
    properties:
      value: {type: string}
  outputs:
    type: object
    required: [result]
    properties:
      result: {type: string}
phases:
  - id: compute
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "compute" / "LOGIC.md",
        """---
name: compute
io:
  inputs:
    type: object
    required: [value]
    properties:
      value: {type: string}
  outputs:
    type: object
    required: [result]
    properties:
      result: {type: string}
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        root / "phases" / "compute" / "actions" / "run.py",
        "def run(inputs):\n    return {'result': inputs['value'].upper()}\n",
    )


class _FakeExecutor:
    def __init__(
        self,
        outcomes: list[AgentResult | CliExecutorFailure],
        *,
        probe_failure: CliExecutorUnavailable | None = None,
    ) -> None:
        self._outcomes = outcomes
        self._probe_failure = probe_failure
        self.probe_calls = 0
        self.tasks: list[AgentTask] = []

    @property
    def executor_id(self) -> str:
        return "gskill-cli:codex"

    def probe(self) -> VendorProbe:
        self.probe_calls += 1
        if self._probe_failure is not None:
            raise self._probe_failure
        return VendorProbe(
            vendor="codex",
            executable="codex",
            executable_name="codex",
            version="codex-test 1",
            capabilities=frozenset(
                {
                    "cancellation",
                    "declared-resources",
                    "fresh-top-level-session",
                    "structured-output",
                    "timeout",
                }
            ),
            auth_probe="verified",
            session_persistence="disabled",
        )

    def execute(
        self,
        task: AgentTask,
        probe: VendorProbe | None = None,
        *,
        on_dispatched: DispatchCallback | None = None,
        on_started: StartedCallback | None = None,
    ) -> AgentResult:
        assert probe is not None
        self.tasks.append(task)
        if on_dispatched is not None:
            on_dispatched()
        if on_started is not None:
            on_started(2468)
        if not self._outcomes:
            raise AssertionError("unexpected Agent execution")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, CliExecutorFailure):
            raise outcome
        return outcome.model_copy(update={"task_id": task.task_id})


def _application(
    tmp_path: Path,
    factory: Callable[[CliExecutorConfig], _FakeExecutor],
):
    runtime = CliRuntimeAdapter(executor_factory=factory)
    engine = CurrentEngineAdapter(cli_runtime=runtime)
    return create_application(
        user_config_path=tmp_path / "missing-user-config.toml",
        engine=engine,
    )


def _invocation(
    skill_root: Path,
    state_root: Path,
    *,
    run_id: str,
    inputs: dict[str, str],
) -> RunInvocation:
    return RunInvocation(
        skill_root=str(skill_root),
        run_id=run_id,
        runtime=RuntimeProfileOverlay(
            executor=CliExecutorConfig(vendor="codex"),
            state_dir=str(state_root),
        ),
        inputs=inputs,
    )


def _agent_event_types(trace_path: str | None) -> list[str]:
    assert trace_path is not None
    payloads = [
        json.loads(line)
        for line in Path(trace_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        str(payload["event_type"])
        for payload in payloads
        if str(payload.get("event_type", "")).startswith("agent_")
    ]


def _agent_events(trace_path: str | None) -> list[dict[str, object]]:
    assert trace_path is not None
    events: list[dict[str, object]] = []
    for line in Path(trace_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload: dict[str, object] = json.loads(line)
        if str(payload.get("event_type", "")).startswith("agent_"):
            events.append(payload)
    return events


def test_cli_runtime_closes_one_agent_wait_with_causal_events(tmp_path: Path) -> None:
    executor = _FakeExecutor(
        [
            AgentResult(
                task_id="replaced-at-execution",
                status="completed",
                output={"echoed_note": "grounded"},
                executor_id="gskill-cli:codex",
                provenance={"session_id": "fresh-session"},
            )
        ]
    )
    state_root = tmp_path / "state"
    result = _application(tmp_path, lambda config: executor).run(
        _invocation(
            FIXTURES / "demo-echo-agent",
            state_root,
            run_id="cli-success",
            inputs={"note": "ground this"},
        )
    )

    assert result.status == "completed"
    assert result.mode == "run"
    assert result.outputs["echoed_note"] == "grounded"
    assert result.outputs["phase_outputs"] == {
        "echo": {"echoed_note": "grounded"}
    }
    assert executor.probe_calls == 1
    assert len(executor.tasks) == 1
    assert executor.tasks[0].inputs == {"note": "ground this"}
    assert _agent_event_types(result.trace_path) == [
        "agent_required",
        "agent_dispatched",
        "agent_started",
        "agent_completed",
    ]
    events = _agent_events(result.trace_path)
    assert events[1]["attempt_id"] == events[2]["attempt_id"]
    assert events[2]["attempt_id"] == events[3]["attempt_id"]


def test_cli_runtime_rejects_unbridged_agent_capabilities_before_handoff(
    tmp_path: Path,
) -> None:
    executor = _FakeExecutor([])
    state_root = tmp_path / "state"
    result = _application(tmp_path, lambda config: executor).run(
        _invocation(
            FIXTURES / "agent-demo",
            state_root,
            run_id="unsupported-agent",
            inputs={"chapter_content": "One scene."},
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.code is RuntimeErrorCode.EXECUTOR_UNAVAILABLE
    assert result.error.retryable is False
    assert result.error.details["category"] == "task-capability-missing"
    assert executor.probe_calls == 1
    assert executor.tasks == []
    assert not (state_root / "agent-handoffs.sqlite3").exists()


def test_cli_runtime_rejects_an_unavailable_vendor_before_handoff(tmp_path: Path) -> None:
    executor = _FakeExecutor(
        [],
        probe_failure=CliExecutorUnavailable(
            "codex is not authenticated",
            category="authentication-missing",
        ),
    )
    state_root = tmp_path / "state"
    result = _application(tmp_path, lambda config: executor).run(
        _invocation(
            FIXTURES / "demo-echo-agent",
            state_root,
            run_id="probe-failure",
            inputs={"note": "hello"},
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.code is RuntimeErrorCode.EXECUTOR_UNAVAILABLE
    assert result.error.retryable is True
    assert result.error.details["category"] == "authentication-missing"
    assert executor.tasks == []
    assert not (state_root / "agent-handoffs.sqlite3").exists()


def test_cli_failure_preserves_same_durable_task_for_retry(tmp_path: Path) -> None:
    executor = _FakeExecutor(
        [
            CliExecutorFailure(
                "process exited",
                category="nonzero-exit",
                retryable=True,
            ),
            AgentResult(
                task_id="replaced-at-execution",
                status="completed",
                output={"echoed_note": "retried"},
                executor_id="gskill-cli:codex",
            ),
        ]
    )
    state_root = tmp_path / "state"
    invocation = _invocation(
        FIXTURES / "demo-echo-agent",
        state_root,
        run_id="cli-retry",
        inputs={"note": "retry me"},
    )

    first = _application(tmp_path, lambda config: executor).run(invocation)
    assert first.status == "failed"
    assert first.error is not None
    assert first.error.retryable is True
    assert first.error.details["category"] == "nonzero-exit"
    assert first.error.details["task_id"] == executor.tasks[0].task_id
    assert (state_root / "agent-handoffs.sqlite3").is_file()

    second = _application(tmp_path, lambda config: executor).run(invocation)
    assert second.status == "completed"
    assert second.outputs["echoed_note"] == "retried"
    assert len(executor.tasks) == 2
    assert executor.tasks[1] == executor.tasks[0]
    assert _agent_event_types(second.trace_path) == [
        "agent_required",
        "agent_dispatched",
        "agent_started",
        "agent_failed",
        "agent_dispatched",
        "agent_started",
        "agent_completed",
    ]


def test_cli_profile_runs_pure_logic_without_constructing_a_vendor_executor(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "logic-skill"
    _logic_skill(skill_root)

    def forbidden_factory(config: CliExecutorConfig) -> _FakeExecutor:
        raise AssertionError(f"pure logic must not construct {config.vendor}")

    result = _application(tmp_path, forbidden_factory).run(
        _invocation(
            skill_root,
            tmp_path / "state",
            run_id="cli-pure-logic",
            inputs={"value": "quiet"},
        )
    )

    assert result.status == "completed", result.model_dump_json(indent=2)
    assert result.outputs["result"] == "QUIET"
