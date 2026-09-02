"""The converter refuses a v0.3 field the portable format never adopted.

`batch:` was a v0.3 phase-level field. Portable gSkill v1 expresses the same
intent through `iterate:` with an explicit mode, and the two are not
mechanically interchangeable: `batch.iterator` selects the source list while
`iterate.over` is a field path resolved against the phase's own inputs. The
converter therefore refuses the file and names the field instead of guessing a
rewrite, and it must leave the author's source untouched when it does.

This test owns the converter, so a v0.3 fixture is its subject rather than a
stand-in for engine corpus.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from graph_skill_runtime.migration import MigrationFailure, migrate_studio_skill


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _schema_yaml(properties: dict[str, Any], *, required: list[str] | None = None) -> str:
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    return json.dumps(schema, ensure_ascii=False, indent=4).replace("\n", "\n    ")


def _legacy_logic_skill(
    root: Path,
    *,
    graph_inputs: dict[str, Any],
    graph_outputs: dict[str, Any],
    phase_inputs: dict[str, Any],
    phase_outputs: dict[str, Any],
    action_body: str,
    phase_iterate: str | None = None,
) -> None:
    graph_input_yaml = _schema_yaml(graph_inputs)
    graph_output_yaml = _schema_yaml(graph_outputs)
    phase_input_yaml = _schema_yaml(phase_inputs)
    phase_output_yaml = _schema_yaml(phase_outputs)
    phase_iterate_block = f"{phase_iterate.rstrip()}\n" if phase_iterate else ""

    _write(
        root / "GRAPH.md",
        f"""---
schema_version: "v0.3.0"
name: ws-e1-step4-iterate-red
io:
  inputs:
    {graph_input_yaml}
  outputs:
    {graph_output_yaml}
phases:
  - worker
---
<phase depends_on="input" output>worker</phase>
""",
    )
    _write(
        root / "phases" / "worker" / "LOGIC.md",
        f"""---
io:
  inputs:
    {phase_input_yaml}
  outputs:
    {phase_output_yaml}
actions: [worker]
validator: false
{phase_iterate_block}---
<action>worker</action>
""",
    )
    _write(
        root / "phases" / "worker" / "actions" / "worker.py",
        dedent(action_body).lstrip(),
    )


def test_legacy_batch_field_requires_explicit_author_rewrite_before_migration(
    tmp_path: Path,
) -> None:
    _legacy_logic_skill(
        tmp_path,
        graph_inputs={"items": {"type": "array", "items": {"type": "string"}}},
        graph_outputs={
            "seen": {"type": "array", "items": {"type": "string"}},
            "batch_outputs": {"type": "array"},
        },
        phase_inputs={
            "items": {"type": "array", "items": {"type": "string"}},
            "item": {"type": "string"},
        },
        phase_outputs={
            "seen": {"type": "array", "items": {"type": "string"}},
            "batch_outputs": {"type": "array"},
        },
        phase_iterate="""
batch:
  iterator: items
  item_var: item
  concurrency: 2
""",
        action_body="""
            def worker(inputs):
                return {"seen": inputs["item"]}
        """,
    )

    source_snapshot = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(path for path in tmp_path.rglob("*") if path.is_file())
    }
    destination = tmp_path.parent / "portable-batch-rejected"

    with pytest.raises(MigrationFailure) as exc_info:
        migrate_studio_skill(tmp_path, destination)

    report = exc_info.value.report
    assert report.status == "failed"
    assert report.diagnostics[0].code == "GSKILL_MIGRATION_UNKNOWN_FIELD"
    assert "batch" in report.diagnostics[0].message
    assert "iterate" in report.diagnostics[0].message
    assert not destination.exists()
    assert source_snapshot == {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(path for path in tmp_path.rglob("*") if path.is_file())
    }
