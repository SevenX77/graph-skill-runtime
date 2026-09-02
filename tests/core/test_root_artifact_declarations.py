"""Root-only `artifacts:` declarations, compiled from a native portable bundle.

`artifacts` is the one portable gSkill v1 graph field with no corpus of its own:
`tests/core/test_productization_artifact_contracts.py` builds `ArtifactDeclaration`
objects directly, and `tests/core/test_graph_roundtrip_serializer.py` round-trips
the YAML without compiling it, so nothing exercised the two rules the loader
enforces on a real bundle. Those rules are what make the declaration a portable
contract rather than a free-form field: only the root graph may declare
artifacts (spec section 4.1, "`artifacts` | 否，仅 root graph"), and every name
in `fields` must exist in the root graph's `io.outputs.properties` (section 4.5).

Both rules are compile-time facts about a directory on disk, so they are proven
by compiling a directory, not by constructing the model the compiler would have
produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError

_ARTIFACT_BLOCK = """artifacts:
  - artifact_id: report
    stem: report
    fields: [report]
    mode: single
    format: md
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _graph_yaml(graph_id: str, *, artifacts: str = "") -> str:
    return f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Produce one report field.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
phases:
  - id: build
    depends_on: [input]
    output: true
{artifacts}"""


def _logic_phase(graph_root: Path) -> None:
    _write(
        graph_root / "phases" / "build" / "LOGIC.md",
        """---
name: build
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
actions: [build]
validator: false
---
<action>build</action>
""",
    )
    _write(
        graph_root / "phases" / "build" / "actions" / "build.py",
        "def build(inputs):\n    return {'report': 'ok'}\n",
    )


def _root_skill(tmp_path: Path, *, artifacts: str = "") -> Path:
    root = tmp_path / "artifact-declaring"
    _write(
        root / "SKILL.md",
        "---\nname: artifact-declaring\n"
        "description: Compile a bundle that declares one materializable artifact.\n---\n",
    )
    _write(root / "graph.yaml", _graph_yaml("artifact-declaring", artifacts=artifacts))
    _logic_phase(root)
    return root


def _issue_codes(exc: SkillLoadError) -> set[str]:
    return {str(issue.rule_id) for issue in exc.compile_result.issues}


def test_root_graph_carries_its_artifact_declarations_through_compile(tmp_path: Path) -> None:
    compiled = compile_skill(_root_skill(tmp_path, artifacts=_ARTIFACT_BLOCK), cache=False)

    declarations = compiled.manifest.artifacts
    assert len(declarations) == 1
    declaration = declarations[0]
    assert declaration.artifact_id == "report"
    assert declaration.stem == "report"
    assert declaration.fields == ("report",)
    assert declaration.mode == "single"
    assert declaration.format == "md"


def test_a_registry_graph_may_not_declare_artifacts(tmp_path: Path) -> None:
    """A registry graph carries the same schema but not the root-only field."""

    root = tmp_path / "artifact-declaring"
    _write(
        root / "SKILL.md",
        "---\nname: artifact-declaring\n"
        "description: Delegate the summary step to a registry graph.\n---\n",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: artifact-declaring
description: Build a report, then delegate its summary.
io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    required: [summary]
    properties:
      summary:
        type: string
phases:
  - id: build
    depends_on: [input]
    output: false
  - id: delegate
    depends_on: [build]
    output: true
""",
    )
    _logic_phase(root)
    _write(
        root / "phases" / "delegate" / "SUBGRAPH.md",
        """---
name: delegate
graph: child-pipeline
io:
  inputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
  outputs:
    type: object
    required: [summary]
    properties:
      summary:
        type: string
validator: false
---
""",
    )

    child = root / "graphs" / "child-pipeline"
    _write(
        child / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: child-pipeline
description: Summarize one report.
io:
  inputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
  outputs:
    type: object
    required: [summary]
    properties:
      summary:
        type: string
phases:
  - id: summarize
    depends_on: [input]
    output: true
artifacts:
  - artifact_id: summary
    stem: summary
    fields: [summary]
    mode: single
    format: md
""",
    )
    _write(
        child / "phases" / "summarize" / "LOGIC.md",
        """---
name: summarize
io:
  inputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
  outputs:
    type: object
    required: [summary]
    properties:
      summary:
        type: string
actions: [summarize]
validator: false
---
<action>summarize</action>
""",
    )
    _write(
        child / "phases" / "summarize" / "actions" / "summarize.py",
        "def summarize(inputs):\n    return {'summary': inputs['report'][:3]}\n",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    assert "[F-v3-artifact-declaration-invalid]" in _issue_codes(exc_info.value)
    assert "artifacts may be declared only by the root graph" in str(exc_info.value)


def test_an_artifact_may_only_name_declared_root_output_fields(tmp_path: Path) -> None:
    unknown_field = _ARTIFACT_BLOCK.replace("fields: [report]", "fields: [report, summary]")

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(_root_skill(tmp_path, artifacts=unknown_field), cache=False)

    assert "[F-v3-artifact-declaration-invalid]" in _issue_codes(exc_info.value)
    assert "names unknown graph output fields: summary" in str(exc_info.value)
