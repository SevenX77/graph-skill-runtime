from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.adapters.engine import CurrentEngineAdapter
from graph_skill_runtime.adapters.snapshots import LocalRunSnapshotStore
from graph_skill_runtime.application.config import ConfigResolver
from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.domain.models import (
    CompileRequest,
    EmbeddedExecutorConfig,
    GoldenEvaluationRequest,
    InspectRequest,
    RunInvocation,
    RuntimeProfileOverlay,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _logic_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Run the adapter smoke graph for embedded engine verification.
metadata:
  gskill: gskill.graph.v1
---

Use the installed gskill runtime.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: adapter-smoke
description: Embedded adapter smoke graph.
io:
  inputs:
    type: object
    properties:
      text: {type: string}
    required: [text]
  outputs:
    type: object
    properties:
      result: {type: string}
    required: [result]
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "main" / "LOGIC.md",
        """---
name: main
io:
  inputs:
    type: object
    properties:
      text: {type: string}
    required: [text]
  outputs:
    type: object
    properties:
      result: {type: string}
    required: [result]
actions: [run]
validator: false
---
<action>run</action>
""",
    )
    _write(
        root / "phases" / "main" / "actions" / "run.py",
        "def run(inputs):\n    return {'result': inputs['text']}\n",
    )


def test_current_engine_adapter_compiles_and_runs_an_explicit_embedded_logic_skill(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "adapter-smoke-skill"
    _logic_skill(skill_root)
    engine = CurrentEngineAdapter()

    compile_result = engine.compile(CompileRequest(skill_root=str(skill_root), cache=False))

    assert compile_result.status == "passed"
    assert compile_result.skill_id == "adapter-smoke-skill"
    application = RuntimeApplication(
        config_resolver=ConfigResolver(user_config_path=tmp_path / "missing.toml"),
        engine=engine,
        snapshot_store=LocalRunSnapshotStore(),
    )
    run_result = application.run(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="embedded-smoke",
            runtime=RuntimeProfileOverlay(executor=EmbeddedExecutorConfig()),
            inputs={"text": "hello"},
        )
    )

    assert run_result.status == "completed"
    assert run_result.outputs["result"] == "hello"
    assert (skill_root / ".gskill" / "runs" / "embedded-smoke" / "request.json").is_file()


def test_current_engine_adapter_returns_structured_compile_diagnostics(tmp_path: Path) -> None:
    skill_root = tmp_path / "invalid-skill"
    skill_root.mkdir()

    result = CurrentEngineAdapter().compile(
        CompileRequest(skill_root=str(skill_root), cache=False)
    )

    assert result.status == "failed"
    assert result.diagnostics
    assert all(diagnostic.severity == "fatal" for diagnostic in result.diagnostics)


def test_current_engine_inspect_does_not_write_the_compile_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "inspect-only"
    cache_root = tmp_path / "compile-cache"
    _logic_skill(skill_root)
    monkeypatch.setattr(
        "graph_skill_runtime.core.cache.get_cache_dir",
        lambda: cache_root,
    )

    result = CurrentEngineAdapter().inspect(InspectRequest(skill_root=str(skill_root)))

    assert result.skill_id == "inspect-only"
    assert not cache_root.exists()


@pytest.mark.parametrize("failed,stale", [(1, 0), (0, 1)])
def test_current_engine_adapter_fails_golden_result_when_any_case_is_not_passed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed: int,
    stale: int,
) -> None:
    def evaluate_golden_baseline(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return {
            "baseline_id": "baseline",
            "summary": {
                "total_cases": 1,
                "passed": 0,
                "failed": failed,
                "stale": stale,
            },
            "cases": [],
        }

    monkeypatch.setattr(
        "graph_skill_runtime.core.runner.evaluate_golden_baseline",
        evaluate_golden_baseline,
    )

    result = CurrentEngineAdapter().evaluate_golden(
        GoldenEvaluationRequest(
            skill_root=str(tmp_path),
            state_root=str(tmp_path),
            baseline_id="baseline",
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.message == "golden evaluation failed"


def test_current_engine_adapter_passes_golden_result_only_for_a_consistent_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def evaluate_golden_baseline(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return {
            "baseline_id": "baseline",
            "summary": {"total_cases": 2, "passed": 2, "failed": 0, "stale": 0},
            "cases": [],
        }

    monkeypatch.setattr(
        "graph_skill_runtime.core.runner.evaluate_golden_baseline",
        evaluate_golden_baseline,
    )

    result = CurrentEngineAdapter().evaluate_golden(
        GoldenEvaluationRequest(
            skill_root=str(tmp_path),
            state_root=str(tmp_path),
            baseline_id="baseline",
        )
    )

    assert result.status == "passed"
    assert result.error is None


def test_current_engine_adapter_rejects_a_malformed_golden_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def evaluate_golden_baseline(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return {
            "summary": {"total_cases": 2, "passed": 2, "failed": 1, "stale": 0}
        }

    monkeypatch.setattr(
        "graph_skill_runtime.core.runner.evaluate_golden_baseline",
        evaluate_golden_baseline,
    )

    result = CurrentEngineAdapter().evaluate_golden(
        GoldenEvaluationRequest(
            skill_root=str(tmp_path),
            state_root=str(tmp_path),
            baseline_id="baseline",
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert "summary counts are inconsistent" in result.error.message
