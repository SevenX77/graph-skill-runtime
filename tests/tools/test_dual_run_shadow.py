from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "dual_run_shadow.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("dual_run_shadow", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.tier1
def test_dual_run_shadow_logic_skill_idempotency(tmp_path: Path) -> None:
    tool = _load_tool()
    skill_root = tmp_path / "skill"
    (skill_root / "phases" / "main" / "actions").mkdir(parents=True)
    (skill_root / "GRAPH.md").write_text(
        """---
schema_version: "v0.3.0"
name: shadow-smoke
io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: string}
  outputs:
    type: object
    required: [answer]
    properties:
      answer: {type: string}
phases: [main]
---
<phase depends_on="input" output>main</phase>
""",
        encoding="utf-8",
    )
    (skill_root / "phases" / "main" / "LOGIC.md").write_text(
        """---
io:
  inputs:
    type: object
    required: [text]
    properties:
      text: {type: string}
  outputs:
    type: object
    required: [answer]
    properties:
      answer: {type: string}
actions: [echo]
validator: false
---
<action>echo</action>
""",
        encoding="utf-8",
    )
    (skill_root / "phases" / "main" / "actions" / "echo.py").write_text(
        "def echo(inputs):\n    return {'answer': inputs['text']}\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "shadow.json"

    exit_code = tool.main(
        [
            str(skill_root),
            "--input-json",
            '{"text":"Ada"}',
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["mode"] == "idempotency"
    assert report["shadow_reference"] == "v21_repeat_run"
    assert report["match"] is True
    assert report["diff"] == {"missing": [], "extra": [], "mismatch": []}
    assert report["outputs"]["run_a"]["data"]["phase_outputs"]["main"] == {"answer": "Ada"}


def test_dual_run_shadow_passes_explicit_resolver_to_compile_and_assemble(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = _load_tool()
    compile_kwargs: dict[str, object] = {}
    assemble_kwargs: dict[str, object] = {}

    def fake_compile_skill(*_args: object, **kwargs: object) -> object:
        compile_kwargs.update(kwargs)
        return object()

    class FakeGraph:
        def invoke(self, _payload: dict[str, object]) -> dict[str, object]:
            return {"data": {}, "flow": {}}

    def fake_assemble_graph(*_args: object, **kwargs: object) -> object:
        assemble_kwargs.update(kwargs)
        return SimpleNamespace(graph=FakeGraph())

    monkeypatch.setattr(tool, "compile_skill", fake_compile_skill)
    monkeypatch.setattr(tool, "assemble_graph", fake_assemble_graph)

    tool._run_v21(tmp_path, {}, run_id="red-test", chat_fixture="none")

    compile_resolver = compile_kwargs.get("skill_resolver")
    assemble_resolver = assemble_kwargs.get("skill_resolver")
    assert compile_resolver is not None
    assert assemble_resolver is not None
    assert type(compile_resolver).__name__ == "LocalWorkspaceResolver"
    assert type(assemble_resolver).__name__ == "LocalWorkspaceResolver"
