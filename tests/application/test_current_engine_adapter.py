from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.adapters.engine import CurrentEngineAdapter
from graph_skill_runtime.adapters.snapshots import LocalRunSnapshotStore
from graph_skill_runtime.application.config import ConfigResolver
from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.domain.models import (
    CompileRequest,
    EmbeddedExecutorConfig,
    RunInvocation,
    RuntimeProfileOverlay,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _logic_skill(root: Path) -> None:
    _write(
        root / "GRAPH.md",
        """---
schema_version: "v0.3.0"
name: adapter-smoke
phases: [main]
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
---
<phase depends_on="input" output>main</phase>
""",
    )
    _write(
        root / "phases" / "main" / "LOGIC.md",
        """---
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
    skill_root = tmp_path / "skill"
    _logic_skill(skill_root)
    engine = CurrentEngineAdapter()

    compile_result = engine.compile(CompileRequest(skill_root=str(skill_root), cache=False))

    assert compile_result.status == "passed"
    assert compile_result.skill_id == "adapter-smoke"
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
