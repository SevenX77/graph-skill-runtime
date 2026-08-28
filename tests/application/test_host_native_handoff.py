from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.agent_handoffs import (
    SqliteAgentHandoffStore,
    canonical_agent_result_hash,
)
from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.adapters.mcp import create_server
from graph_skill_runtime.adapters.snapshots import LocalRunSnapshotStore
from graph_skill_runtime.composition import create_application
from graph_skill_runtime.core.checkpointer import get_checkpointer, reset_checkpointer
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.runner import ExternalPhaseCompletion, resume_skill, run_skill
from graph_skill_runtime.domain.models import (
    AgentResult,
    MemoryCheckpointStoreConfig,
    RunInvocation,
    RuntimeErrorCode,
    RuntimeErrorPayload,
    RuntimeProfileOverlay,
    SqliteCheckpointStoreConfig,
    SubmitAgentResultRequest,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _host_native_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Exercise one durable host-native Agent phase.
---

Run this graph with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: main
description: Prepare, delegate, and finalize one answer.
io:
  inputs:
    type: object
    required: [question]
    properties:
      question: {type: string}
  outputs:
    type: object
    required: [final]
    properties:
      final: {type: string}
phases:
  - id: prepare
    depends_on: [input]
    output: false
  - id: delegate
    depends_on: [prepare]
    output: false
  - id: finalize
    depends_on: [delegate]
    output: true
""",
    )
    _write(
        root / "phases" / "prepare" / "LOGIC.md",
        """---
name: prepare
io:
  inputs:
    type: object
    required: [question]
    properties:
      question: {type: string}
  outputs:
    type: object
    required: [prepared]
    properties:
      prepared: {type: string}
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        root / "phases" / "prepare" / "actions" / "run.py",
        "def run(inputs):\n    return {'prepared': inputs['question'].upper()}\n",
    )
    _write(
        root / "phases" / "delegate" / "AGENT.md",
        """---
name: delegate
io:
  inputs:
    type: object
    required: [prepared]
    properties:
      prepared: {type: string}
  outputs:
    type: object
    required: [answer]
    additionalProperties: false
    properties:
      answer: {type: string}
subagents: []
subgraphs: []
references: []
examples: []
---
<role>
You answer the prepared question.
</role>

<goal>
Return one concise answer.
</goal>

<step id="S1" name="answer">
Answer the prepared question.
</step>

<protocol id="P1">
Return only the declared data.
</protocol>
""",
    )
    _write(
        root / "phases" / "finalize" / "LOGIC.md",
        """---
name: finalize
io:
  inputs:
    type: object
    required: [answer]
    properties:
      answer: {type: string}
  outputs:
    type: object
    required: [final]
    properties:
      final: {type: string}
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        root / "phases" / "finalize" / "actions" / "run.py",
        "def run(inputs):\n    return {'final': inputs['answer'] + '!'}\n",
    )


def _add_second_agent_phase(root: Path) -> None:
    graph_path = root / "graph.yaml"
    graph_path.write_text(
        graph_path.read_text(encoding="utf-8").replace(
            "  - id: finalize\n    depends_on: [delegate]\n    output: true\n",
            "  - id: review\n"
            "    depends_on: [delegate]\n"
            "    output: false\n"
            "  - id: finalize\n"
            "    depends_on: [review]\n"
            "    output: true\n",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _write(
        root / "phases" / "review" / "AGENT.md",
        """---
name: review
io:
  inputs:
    type: object
    required: [answer]
    properties:
      answer: {type: string}
  outputs:
    type: object
    required: [reviewed]
    additionalProperties: false
    properties:
      reviewed: {type: string}
subagents: []
subgraphs: []
references: []
examples: []
---
<role>
You review one answer.
</role>

<goal>
Return the reviewed answer.
</goal>

<step id="S1" name="review">
Review the answer.
</step>

<protocol id="P1">
Return only the declared data.
</protocol>
""",
    )
    _write(
        root / "phases" / "finalize" / "LOGIC.md",
        """---
name: finalize
io:
  inputs:
    type: object
    required: [reviewed]
    properties:
      reviewed: {type: string}
  outputs:
    type: object
    required: [final]
    properties:
      final: {type: string}
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        root / "phases" / "finalize" / "actions" / "run.py",
        "def run(inputs):\n    return {'final': inputs['reviewed'] + '!'}\n",
    )


def test_host_native_task_survives_process_boundary_and_resumes_same_run(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-skill"
    _host_native_skill(skill_root)
    first_application = create_application(user_config_path=tmp_path / "missing.toml")

    required = first_application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="native-closure",
            inputs={"question": "why"},
        )
    )

    assert required.status == "agent_required"
    assert required.agent_required is not None
    assert required.agent_required.task.address.value == "main/delegate"
    assert required.agent_required.task.inputs == {"prepared": "WHY"}
    assert required.agent_required.task.output_schema["required"] == ["answer"]
    assert required.agent_required.task.allowed_paths == (
        str(skill_root.resolve()),
        str((skill_root / ".gskill").resolve()),
    )

    task = required.agent_required.task
    state_root = required.request.profile.state_root if required.request is not None else ""
    trace_path = Path(state_root) / "runs" / required.run_id / "trace.jsonl"
    trace_path.write_text("", encoding="utf-8", newline="\n")
    reset_checkpointer()
    recovered_required = create_application(
        user_config_path=tmp_path / "missing.toml"
    ).run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="native-closure",
            inputs={"question": "why"},
        )
    )
    assert recovered_required == required
    assert "agent_required" in trace_path.read_text(encoding="utf-8")

    submission = SubmitAgentResultRequest(
        run_id=required.run_id,
        state_root=state_root,
        checkpoint_ref=required.agent_required.checkpoint_ref,
        result=AgentResult(
            task_id=task.task_id,
            status="completed",
            output={"answer": "because"},
            executor_id="test-host/native-subagent",
            provenance={"session": "fresh"},
        ),
    )

    reset_checkpointer()
    second_application = create_application(user_config_path=tmp_path / "missing.toml")
    completed = second_application.submit_agent_result(submission)

    assert completed.status == "completed"
    assert completed.run_id == "native-closure"
    assert completed.outputs["final"] == "because!"
    assert completed.request == required.request

    persisted_events = [
        line
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("event_type") != "agent_completed"
    ]
    trace_path.write_text(
        "\n".join(persisted_events) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    reset_checkpointer()
    duplicate_application = create_application(user_config_path=tmp_path / "missing.toml")
    assert duplicate_application.submit_agent_result(submission) == completed
    conflicting = duplicate_application.submit_agent_result(
        submission.model_copy(
            update={
                "result": submission.result.model_copy(
                    update={"output": {"answer": "different"}}
                )
            }
        )
    )
    assert conflicting.status == "failed"
    assert conflicting.error is not None
    assert "different result" in conflicting.error.message
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    handoff_events = [
        event for event in events if str(event.get("event_type", "")).startswith("agent_")
    ]
    assert [event["event_type"] for event in handoff_events] == [
        "agent_required",
        "agent_completed",
        "agent_result_rejected",
    ]


def test_sequential_agent_phases_create_one_durable_task_at_a_time(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "sequential-host-native"
    _host_native_skill(skill_root)
    _add_second_agent_phase(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")

    first = application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="sequential-agents",
            inputs={"question": "q"},
        )
    )
    assert first.agent_required is not None
    assert first.request is not None
    assert first.agent_required.task.address.value == "main/delegate"

    second = application.submit_agent_result(
        SubmitAgentResultRequest(
            run_id=first.run_id,
            state_root=first.request.profile.state_root,
            checkpoint_ref=first.agent_required.checkpoint_ref,
            result=AgentResult(
                task_id=first.agent_required.task.task_id,
                status="completed",
                output={"answer": "draft"},
                executor_id="test-host/native-subagent",
            ),
        )
    )
    assert second.status == "agent_required", second.model_dump_json(indent=2)
    assert second.agent_required is not None
    assert second.agent_required.task.address.value == "main/review"
    assert second.agent_required.task.inputs == {"answer": "draft"}

    completed = application.submit_agent_result(
        SubmitAgentResultRequest(
            run_id=second.run_id,
            state_root=first.request.profile.state_root,
            checkpoint_ref=second.agent_required.checkpoint_ref,
            result=AgentResult(
                task_id=second.agent_required.task.task_id,
                status="completed",
                output={"reviewed": "approved"},
                executor_id="test-host/native-subagent",
            ),
        )
    )
    assert completed.status == "completed"
    assert completed.outputs["final"] == "approved!"


def test_invalid_agent_output_does_not_consume_the_task(tmp_path: Path) -> None:
    skill_root = tmp_path / "host-native-retry"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")
    required = application.run(
        RunInvocation(skill_root=str(skill_root), run_id="invalid-then-valid", inputs={"question": "q"})
    )
    assert required.agent_required is not None
    assert required.request is not None
    task = required.agent_required.task

    invalid = application.submit_agent_result(
        SubmitAgentResultRequest(
            run_id=required.run_id,
            state_root=required.request.profile.state_root,
            checkpoint_ref=required.agent_required.checkpoint_ref,
            result=AgentResult(
                task_id=task.task_id,
                status="completed",
                output={"wrong": "shape"},
                executor_id="test-host/native-subagent",
            ),
        )
    )

    assert invalid.status == "failed"
    assert invalid.error is not None
    assert invalid.error.code == "GSKILL_INVALID_REQUEST"

    corrected = application.submit_agent_result(
        SubmitAgentResultRequest(
            run_id=required.run_id,
            state_root=required.request.profile.state_root,
            checkpoint_ref=required.agent_required.checkpoint_ref,
            result=AgentResult(
                task_id=task.task_id,
                status="completed",
                output={"answer": "fixed"},
                executor_id="test-host/native-subagent",
            ),
        )
    )
    assert corrected.status == "completed"
    assert corrected.outputs["final"] == "fixed!"


def test_cancelled_agent_result_fails_the_run_without_executing_the_phase(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-cancelled"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")
    required = application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="cancelled-agent",
            inputs={"question": "q"},
        )
    )
    assert required.agent_required is not None
    assert required.request is not None
    submission = SubmitAgentResultRequest(
        run_id=required.run_id,
        state_root=required.request.profile.state_root,
        checkpoint_ref=required.agent_required.checkpoint_ref,
        result=AgentResult(
            task_id=required.agent_required.task.task_id,
            status="cancelled",
            error=RuntimeErrorPayload(
                code=RuntimeErrorCode.RUN_FAILED,
                message="host cancelled the native child",
            ),
            executor_id="test-host/native-subagent",
        ),
    )

    cancelled = application.submit_agent_result(submission)

    assert cancelled.status == "failed"
    assert cancelled.error is not None
    assert cancelled.error.message == "host cancelled the native child"
    assert application.submit_agent_result(submission) == cancelled
    trace_path = (
        Path(required.request.profile.state_root)
        / "runs"
        / required.run_id
        / "trace.jsonl"
    )
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    failed_events = [event for event in events if event.get("event_type") == "agent_failed"]
    assert len(failed_events) == 1
    assert failed_events[0]["status"] == "cancelled"


def test_agent_result_rejects_a_checkpoint_for_a_tampered_run_snapshot(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-snapshot-owner"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")
    required = application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="snapshot-owner",
            inputs={"question": "original"},
        )
    )
    assert required.agent_required is not None
    assert required.request is not None

    snapshot_path = (
        Path(required.request.profile.state_root)
        / "runs"
        / required.run_id
        / "request.json"
    )
    snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_data["inputs"]["question"] = "tampered"
    snapshot_path.write_text(
        json.dumps(snapshot_data),
        encoding="utf-8",
        newline="\n",
    )

    rejected = application.submit_agent_result(
        SubmitAgentResultRequest(
            run_id=required.run_id,
            state_root=required.request.profile.state_root,
            checkpoint_ref=required.agent_required.checkpoint_ref,
            result=AgentResult(
                task_id=required.agent_required.task.task_id,
                status="completed",
                output={"answer": "must not run"},
                executor_id="test-host/native-subagent",
            ),
        )
    )

    assert rejected.status == "failed"
    assert rejected.error is not None
    assert rejected.error.code == "GSKILL_INVALID_REQUEST"
    assert "different immutable run request" in rejected.error.message


def test_retry_recovers_when_graph_committed_before_handoff_response(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-crash-window"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")
    required = application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="crash-window",
            inputs={"question": "q"},
        )
    )
    assert required.agent_required is not None
    assert required.request is not None
    task = required.agent_required.task
    result = AgentResult(
        task_id=task.task_id,
        status="completed",
        output={"answer": "durable"},
        executor_id="test-host/native-subagent",
    )
    snapshot = LocalRunSnapshotStore().load(
        Path(required.request.profile.state_root),
        required.run_id,
    )
    checkpoint_config = snapshot.profile.profile.checkpoint_store
    assert isinstance(checkpoint_config, SqliteCheckpointStoreConfig)
    state_root = Path(snapshot.profile.state_root)
    record = SqliteAgentHandoffStore(
        state_root / "agent-handoffs.sqlite3"
    ).load(required.agent_required.checkpoint_ref)
    phases = {
        node.phase_name
        for node in compile_skill(skill_root).nodes
        if node.phase_name == task.address.phase_id
    }
    checkpointer = get_checkpointer(
        state_root / checkpoint_config.filename,
        backend="sqlite",
    )

    graph_committed = resume_skill(
        skill_root,
        workspace_dir=state_root,
        run_id=required.run_id,
        checkpoint_id=record.checkpoint_id,
        checkpoint_ns=record.checkpoint_ns,
        checkpointer=checkpointer,
        pause_before=frozenset(phases),
        external_phase_completion=ExternalPhaseCompletion(
            task_id=task.task_id,
            phase_id=task.address.phase_id,
            result_hash=canonical_agent_result_hash(result),
            output=dict(result.output or {}),
        ),
    )
    assert graph_committed.success is True
    assert graph_committed.context["final"] == "durable!"

    # Simulate the process dying here: the graph checkpoint is durable, while
    # the handoff row still has neither result nor response.
    reset_checkpointer()
    retried = create_application(
        user_config_path=tmp_path / "missing.toml"
    ).submit_agent_result(
        SubmitAgentResultRequest(
            run_id=required.run_id,
            state_root=str(state_root),
            checkpoint_ref=required.agent_required.checkpoint_ref,
            result=result,
        )
    )

    assert retried.status == "completed"
    assert retried.outputs["final"] == "durable!"


def test_run_recovers_when_graph_paused_before_handoff_row_was_written(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-task-crash-window"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")
    invocation = RunInvocation(
        skill_root=str(skill_root),
        run_id="task-crash-window",
        inputs={"question": "q"},
    )
    request = application.resolve_run(invocation).request
    LocalRunSnapshotStore().save(request)
    checkpoint_config = request.profile.profile.checkpoint_store
    assert isinstance(checkpoint_config, SqliteCheckpointStoreConfig)
    state_root = Path(request.profile.state_root)
    checkpointer = get_checkpointer(
        state_root / checkpoint_config.filename,
        backend="sqlite",
    )

    paused = run_skill(
        skill_root,
        workspace_dir=state_root,
        thread_id=request.run_id,
        cleanup_checkpoints_on_finish=False,
        checkpointer_spec=checkpointer,
        pause_before=frozenset({"delegate"}),
        question="q",
    )
    assert paused.paused_at is not None

    # Simulate termination before SqliteAgentHandoffStore.put_required().
    reset_checkpointer()
    recovered = create_application(
        user_config_path=tmp_path / "missing.toml"
    ).run(invocation)

    assert recovered.status == "agent_required", recovered.model_dump_json(indent=2)
    assert recovered.agent_required is not None
    assert recovered.agent_required.task.address.value == "main/delegate"
    trace_path = state_root / "runs" / request.run_id / "trace.jsonl"
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    prepare_starts = [
        event
        for event in events
        if event.get("event_type") == "phase_start"
        and event.get("phase_name") == "prepare"
    ]
    assert len(prepare_starts) == 1


def test_host_native_agent_requires_a_durable_checkpoint_store(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "host-native-memory-rejected"
    _host_native_skill(skill_root)

    result = create_application(
        user_config_path=tmp_path / "missing.toml"
    ).run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="memory-rejected",
            inputs={"question": "q"},
            runtime=RuntimeProfileOverlay(
                checkpoint_store=MemoryCheckpointStoreConfig()
            ),
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.code == "GSKILL_INVALID_REQUEST"
    assert "durable SQLite" in result.error.message


def test_parallel_agent_wait_point_fails_instead_of_falling_back_to_embedded(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "parallel-agent-rejected"
    _host_native_skill(skill_root)
    graph_path = skill_root / "graph.yaml"
    graph_text = graph_path.read_text(encoding="utf-8")
    graph_path.write_text(
        graph_text.replace(
            "  - id: finalize\n    depends_on: [delegate]\n    output: true\n",
            "  - id: side\n"
            "    depends_on: [prepare]\n"
            "    output: false\n"
            "  - id: finalize\n"
            "    depends_on: [delegate]\n"
            "    output: true\n",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _write(
        skill_root / "phases" / "side" / "LOGIC.md",
        """---
name: side
io:
  inputs:
    type: object
    required: [prepared]
    properties:
      prepared: {type: string}
  outputs:
    type: object
    required: [side]
    properties:
      side: {type: string}
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        skill_root / "phases" / "side" / "actions" / "run.py",
        "def run(inputs):\n    return {'side': inputs['prepared']}\n",
    )

    result = create_application(
        user_config_path=tmp_path / "missing.toml"
    ).run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="parallel-rejected",
            inputs={"question": "q"},
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.code == "GSKILL_INVALID_REQUEST"
    assert "parallel with" in result.error.message


def test_agent_result_cannot_persist_secret_shaped_output_or_provenance() -> None:
    with pytest.raises(ValueError, match="SecretReference"):
        AgentResult(
            task_id="task-1",
            status="completed",
            output={"access_token": "secret"},
            executor_id="host/native",
        )
    with pytest.raises(ValueError, match="SecretReference"):
        AgentResult(
            task_id="task-1",
            status="completed",
            output={"answer": "safe"},
            executor_id="host/native",
            provenance={"api_key": "secret"},
        )


def test_cli_treats_agent_required_as_a_successful_two_step_protocol(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_root = tmp_path / "cli-host-native"
    state_root = tmp_path / "cli-state"
    _host_native_skill(skill_root)
    application = create_application(user_config_path=tmp_path / "missing.toml")

    run_exit = cli_main(
        [
            "run",
            str(skill_root),
            "--run-id",
            "cli-two-step",
            "--state-dir",
            str(state_root),
            "--inputs-json",
            '{"question":"q"}',
        ],
        application=application,
    )
    required = json.loads(capsys.readouterr().out)

    assert run_exit == 0
    assert required["status"] == "agent_required"
    task = required["agent_required"]["task"]
    result = AgentResult(
        task_id=task["task_id"],
        status="completed",
        output={"answer": "cli"},
        executor_id="host/native",
    )
    submit_exit = cli_main(
        [
            "submit",
            "cli-two-step",
            "--state-root",
            str(state_root),
            "--checkpoint-ref",
            required["agent_required"]["checkpoint_ref"],
            "--result-json",
            result.model_dump_json(),
        ],
        application=application,
    )
    completed = json.loads(capsys.readouterr().out)

    assert submit_exit == 0
    assert completed["status"] == "completed"
    assert completed["outputs"]["final"] == "cli!"


def test_mcp_projects_the_same_host_native_submit_protocol(tmp_path: Path) -> None:
    skill_root = tmp_path / "mcp-host-native"
    state_root = tmp_path / "mcp-state"
    _host_native_skill(skill_root)
    server = create_server(
        create_application(user_config_path=tmp_path / "missing.toml")
    )
    invocation = RunInvocation(
        skill_root=str(skill_root),
        run_id="mcp-two-step",
        runtime=RuntimeProfileOverlay(state_dir=str(state_root)),
        inputs={"question": "q"},
    )

    required_call = asyncio.run(
        server.call_tool(
            "run",
            {"invocation": invocation.model_dump(mode="json")},
        )
    )
    required = required_call.structured_content
    assert required is not None
    assert required["status"] == "agent_required"
    task = required["agent_required"]["task"]
    submission = SubmitAgentResultRequest(
        run_id="mcp-two-step",
        state_root=str(state_root),
        checkpoint_ref=required["agent_required"]["checkpoint_ref"],
        result=AgentResult(
            task_id=task["task_id"],
            status="completed",
            output={"answer": "mcp"},
            executor_id="host/native",
        ),
    )

    completed_call = asyncio.run(
        server.call_tool(
            "submit_agent_result",
            {"request": submission.model_dump(mode="json")},
        )
    )
    completed = completed_call.structured_content
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["outputs"]["final"] == "mcp!"
