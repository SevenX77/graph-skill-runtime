from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from graph_skill_runtime.callbacks.base import Callback
from graph_skill_runtime.callbacks.events import (
    BuiltinSubagentEnterEvent,
    BuiltinSubagentExitEvent,
    BuiltinSubagentFallbackEvent,
)
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import GraphAgentFatalError
from graph_skill_runtime.core.graph_assembler import assemble_graph


class CollectorCallback(Callback):
    def __init__(self) -> None:
        self.events: list[Any] = []

    def on_event(self, event: Any) -> None:
        self.events.append(event)


def _load_workflow(root: Path, *, callbacks: list[Any], skill_resolver: object) -> Any:
    """Compile the skill and assemble it, handing back the runnable graph."""
    compiled = compile_skill(root, skill_resolver=skill_resolver)
    return assemble_graph(
        compiled,
        chat_model=None,
        callbacks=callbacks,
        skill_resolver=skill_resolver,
    ).graph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _agent_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        """---
name: pr-e-reference-reader
description: One agent phase that reads a skill-root reference.
---
Compile and run this graph skill with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: pr-e-reference-reader
description: One agent phase that reads a skill-root reference.
llm_role: analyst
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "main" / "AGENT.md",
        """---
name: main
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
references:
  - id: Guide
    path: references/guide.md
    summary: Guide reference
---
<role>
Reader.
</role>
<goal>
Use @reference:Guide.
</goal>
""",
    )
    _write(root / "references" / "guide.md", "SENTINEL_RAW_REFERENCE " * 80)


def _event_types(events: list[Any]) -> list[str]:
    return [str(getattr(event, "event_type", "")) for event in events]


def test_e2_reference_reader_success_emits_enter_then_exit_from_loader_callbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    class SuccessfulReaderRuntime:
        def __init__(self, **kwargs: Any) -> None:
            self.phase_id = kwargs["phase_id"]
            self.references = kwargs["references"]

        def run(self) -> dict[str, str]:
            return {"markdown": "## refined\n\nshort refined knowledge"}

    monkeypatch.setattr(
        "graph_skill_runtime.core.graph_assembler.ReferenceReaderRuntime",
        SuccessfulReaderRuntime,
    )
    skill_root = tmp_path / "pr-e-reference-reader"
    _agent_skill(skill_root)
    collector = CollectorCallback()

    _load_workflow(skill_root, callbacks=[collector], skill_resolver=mock_skill_resolver)

    assert _event_types(collector.events) == [
        "builtin_subagent_enter",
        "builtin_subagent_exit",
    ]
    enter, exit_event = collector.events
    assert isinstance(enter, BuiltinSubagentEnterEvent)
    assert isinstance(exit_event, BuiltinSubagentExitEvent)
    assert enter.run_id is None
    assert exit_event.run_id is None
    assert enter.phase_name == "main"
    assert exit_event.phase_name == "main"
    assert enter.builtin_name == "reference_reader"
    assert exit_event.builtin_name == "reference_reader"
    assert "SENTINEL_RAW_REFERENCE" not in exit_event.model_dump_json()


@pytest.mark.parametrize(
    ("mode", "expected_reason"),
    [
        ("timeout", "remote_timeout"),
        ("remote_error", "remote_error"),
        ("missing_config", "config_missing"),
        ("invalid_output", "invalid_output"),
        ("local_io_error", "local_io_error"),
    ],
)
def test_e2_e3_reference_reader_fallback_emits_slim_payload_for_each_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_skill_resolver: object,
    mode: str,
    expected_reason: str,
) -> None:
    class FailingReaderRuntime:
        def __init__(self, **kwargs: Any) -> None:
            del kwargs

        def run(self) -> dict[str, str]:
            if mode == "timeout":
                raise TimeoutError("reader timed out")
            if mode == "remote_error":
                raise RuntimeError("remote model unavailable")
            if mode == "missing_config":
                raise GraphAgentFatalError("[F-v3-reference-reader-failed] missing config")
            if mode == "local_io_error":
                raise OSError("local fallback read failed")
            return {"unexpected": "shape"}  # invalid_output

    monkeypatch.setattr(
        "graph_skill_runtime.core.graph_assembler.ReferenceReaderRuntime",
        FailingReaderRuntime,
    )
    skill_root = tmp_path / "pr-e-reference-reader"
    _agent_skill(skill_root)
    collector = CollectorCallback()

    _load_workflow(skill_root, callbacks=[collector], skill_resolver=mock_skill_resolver)

    assert _event_types(collector.events) == [
        "builtin_subagent_enter",
        "builtin_subagent_fallback",
    ]
    enter, fallback = collector.events
    assert isinstance(enter, BuiltinSubagentEnterEvent)
    assert isinstance(fallback, BuiltinSubagentFallbackEvent)
    assert fallback.run_id is None
    assert fallback.phase_name == "main"
    assert fallback.builtin_name == "reference_reader"
    assert fallback.fallback_reason == expected_reason
    assert fallback.fallback_strategy
    assert fallback.excerpt_token_limit == 3000
    assert fallback.warning
    serialized = fallback.model_dump_json()
    assert "warning_message" not in serialized
    assert "SENTINEL_RAW_REFERENCE" not in serialized
    assert "系统无法完成知识精炼" not in serialized
