from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.migration import MigrationFailure, migrate_studio_skill
from graph_skill_runtime.migration import studio_v030 as migration_module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _legacy_graph(root: Path, *, name: str, phase_id: str, output_field: str = "result") -> None:
    _write(
        root / "GRAPH.md",
        f"""---
schema_version: v0.3.0
name: {name}
description: Legacy {name} graph.
io:
  inputs:
    type: object
    properties:
      source: {{type: string}}
  outputs:
    type: object
    properties:
      {output_field}: {{type: string}}
phases: [{phase_id}]
---
<phase depends_on="input" output>{phase_id}</phase>
""",
    )


def _legacy_logic_graph(root: Path, *, name: str = "Child Graph") -> None:
    _legacy_graph(root, name=name, phase_id="done")
    _write(
        root / "phases" / "done" / "LOGIC.md",
        """---
io:
  inputs:
    type: object
    properties:
      source: {type: string}
  outputs:
    type: object
    properties:
      result: {type: string}
---
<action>copy_value</action>
""",
    )
    _write(
        root / "phases" / "done" / "actions" / "copy_value.py",
        "def copy_value(inputs):\n    return {'result': inputs.get('source', '')}\n",
    )


def _legacy_agent_skill(root: Path) -> None:
    _legacy_graph(root, name="Legacy Agent", phase_id="work")
    _write(
        root / "phases" / "work" / "SKILL.md",
        """---
io:
  inputs:
    type: object
    properties:
      source: {type: string}
  outputs:
    type: object
    properties:
      result: {type: string}
---
<role>Worker</role>
<goal>Return a result for the supplied source.</goal>
""",
    )


def _portable_logic_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"---\nname: {root.name}\ndescription: Portable external migration fixture.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: external
description: Portable external graph.
io:
  inputs:
    type: object
    properties:
      source: {type: string}
  outputs:
    type: object
    properties:
      result: {type: string}
phases:
  - id: done
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "done" / "LOGIC.md",
        """---
name: done
io:
  inputs:
    type: object
    properties:
      source: {type: string}
  outputs:
    type: object
    properties:
      result: {type: string}
actions: [copy_value]
validator: false
---
<action>copy_value</action>
""",
    )
    _write(
        root / "phases" / "done" / "actions" / "copy_value.py",
        "def copy_value(inputs):\n    return {'result': inputs.get('source', '')}\n",
    )


def _legacy_subgraph_skill(root: Path) -> None:
    _legacy_graph(root, name="Legacy Parent", phase_id="delegate")
    child = root / "subskills" / "child"
    _legacy_logic_graph(child)
    _write(
        root / "phases" / "delegate" / "SUBGRAPH.md",
        """---
path: subskills/child
io:
  inputs:
    type: object
    properties:
      source: {type: string}
  outputs:
    type: object
    properties:
      result: {type: string}
---
""",
    )


def _runtime_config(path: Path, *, artifacts: list[dict[str, object]]) -> None:
    payload = {
        "schema_version": "studio.runtime_config.v2",
        "inputs": {
            "active": {
                "root": {"source": "default text"},
                "phases": {"work": {"source": "phase text"}},
            }
        },
        "llm": {
            "node_params": {"nodes": {"work": {"timeout_seconds": 9}}},
            "custom_params": {"nodes": {"work": {"temperature": 0.2}}},
            "compare_candidates": {"nodes": {}},
        },
        "breakpoints": ["work"],
        "artifacts": artifacts,
    }
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def test_converter_renames_internal_agent_entry_and_emits_one_root_skill(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable-agent"
    _legacy_agent_skill(source)

    report = migrate_studio_skill(source, destination)

    assert report.status == "completed"
    assert (destination / "SKILL.md").is_file()
    root_skill = (destination / "SKILL.md").read_text(encoding="utf-8")
    assert "Legacy Legacy Agent graph." in root_skill
    compiled = compile_skill(destination, cache=False)
    assert "Use this skill when" in compiled.skill_manifest.description
    assert (destination / "phases" / "work" / "AGENT.md").is_file()
    assert not (destination / "phases" / "work" / "SKILL.md").exists()
    assert [path.relative_to(destination).as_posix() for path in destination.rglob("SKILL.md")] == [
        "SKILL.md"
    ]
    assert (source / "phases" / "work" / "SKILL.md").is_file()
    assert compiled.skill_manifest.name == "portable-agent"


def test_converter_promotes_direct_child_to_flat_registry_and_rewrites_reference(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable-subgraph"
    _legacy_subgraph_skill(source)

    report = migrate_studio_skill(source, destination)

    child_graph = destination / "graphs" / "child-graph"
    assert (child_graph / "graph.yaml").is_file()
    subgraph_doc = (destination / "phases" / "delegate" / "SUBGRAPH.md").read_text(
        encoding="utf-8"
    )
    assert "graph: child-graph" in subgraph_doc
    assert "path:" not in subgraph_doc
    assert report.graph_references == {"subskills/child": "child-graph"}
    compiled = compile_skill(destination, cache=False)
    assert sorted(compiled.graph_registry) == ["child-graph", "legacy-parent"]


def test_converter_normalizes_legacy_refs_and_copies_the_resource_owner(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable-resources"
    _legacy_agent_skill(source)
    agent_path = source / "phases" / "work" / "SKILL.md"
    agent_text = agent_path.read_text(encoding="utf-8").replace(
        "io:\n",
        """references:
  - id: Guide
    path: refs/guide.md
    summary: Migration guide.
io:
""",
        1,
    )
    _write(agent_path, agent_text)
    _write(source / "refs" / "guide.md", "# Guide\n")

    report = migrate_studio_skill(source, destination)

    agent = (destination / "phases" / "work" / "AGENT.md").read_text(encoding="utf-8")
    assert "path: references/guide.md" in agent
    assert (destination / "references" / "guide.md").read_text(encoding="utf-8") == "# Guide\n"
    assert any(
        mapping.source == "refs" and mapping.destination == "references"
        for mapping in report.file_mappings
    )


def test_converter_resolves_an_adjacent_portable_external_subagent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable-parent"
    target = tmp_path / "portable-child"
    _legacy_agent_skill(source)
    _portable_logic_skill(target)
    agent_path = source / "phases" / "work" / "SKILL.md"
    agent_text = agent_path.read_text(encoding="utf-8").replace(
        "io:\n",
        """subagents:
  - name: child
    target_skill: portable-child
    description: Delegate to the portable child.
io:
""",
        1,
    )
    _write(agent_path, agent_text)

    report = migrate_studio_skill(source, destination)

    assert report.status == "completed"
    compiled = compile_skill(destination, cache=False)
    assert compiled.subagents_by_phase["work"][0].target_skill == "portable-child"


def test_cli_migrate_studio_skill_emits_the_same_structured_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable-cli"
    _legacy_agent_skill(source)

    exit_code = cli_main(
        [
            "migrate",
            "studio-skill",
            str(source),
            str(destination),
            "--preset-id",
            "cli-test",
        ]
    )

    output_report = json.loads(capsys.readouterr().out)
    file_report = json.loads(
        (destination / ".gskill-migration-report.json").read_text(encoding="utf-8")
    )
    assert exit_code == 0
    assert output_report == file_report
    assert output_report["preset_id"] == "cli-test"


def test_runtime_config_becomes_typed_preset_and_stable_artifact_declarations(
    tmp_path: Path,
) -> None:
    artifacts = [
        {"stem": "Report", "fields": ["result"], "mode": "single", "format": "json"},
        {"stem": "report", "fields": ["result"], "mode": "single", "format": "md"},
    ]
    first_source = tmp_path / "legacy-first"
    second_source = tmp_path / "legacy-second"
    _legacy_agent_skill(first_source)
    _legacy_agent_skill(second_source)
    first_config = tmp_path / "first-runtime.json"
    second_config = tmp_path / "second-runtime.json"
    _runtime_config(first_config, artifacts=artifacts)
    _runtime_config(second_config, artifacts=list(reversed(artifacts)))

    first_report = migrate_studio_skill(
        first_source,
        tmp_path / "portable-first",
        runtime_config=first_config,
        preset_id="default",
    )
    second_report = migrate_studio_skill(
        second_source,
        tmp_path / "portable-second",
        runtime_config=second_config,
        preset_id="default",
    )

    first_by_hash = {item.sha256: item.artifact_id for item in first_report.artifact_mappings}
    second_by_hash = {item.sha256: item.artifact_id for item in second_report.artifact_mappings}
    assert first_by_hash == second_by_hash
    assert all(artifact_id.startswith("report-") for artifact_id in first_by_hash.values())
    graph = yaml.safe_load((tmp_path / "portable-first" / "graph.yaml").read_text(encoding="utf-8"))
    assert {item["artifact_id"] for item in graph["artifacts"]} == set(first_by_hash.values())
    config_text = (tmp_path / "portable-first" / "gskill.toml").read_text(encoding="utf-8")
    assert "[presets.default]" in config_text
    assert "[[presets.default.artifact_requests]]" in config_text
    assert any(mapping.source == first_config.as_posix() for mapping in first_report.file_mappings)


def test_existing_destination_and_nested_legacy_graph_fail_without_partial_publish(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy"
    _legacy_subgraph_skill(source)
    child = source / "subskills" / "child"
    grandchild = child / "nested" / "grandchild"
    _legacy_logic_graph(grandchild, name="Grandchild")
    (child / "phases" / "done" / "LOGIC.md").unlink()
    _write(
        child / "phases" / "done" / "SUBGRAPH.md",
        """---
path: nested/grandchild
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
---
""",
    )

    destination = tmp_path / "portable"
    with pytest.raises(MigrationFailure) as nested_error:
        migrate_studio_skill(source, destination)
    assert nested_error.value.report.status == "failed"
    assert (
        nested_error.value.report.diagnostics[0].code
        == "GSKILL_MIGRATION_NESTED_SUBGRAPH_UNSUPPORTED"
    )
    assert not destination.exists()

    clean_source = tmp_path / "clean-legacy"
    _legacy_agent_skill(clean_source)
    destination.mkdir()
    marker = destination / "owned.txt"
    _write(marker, "do not overwrite\n")
    with pytest.raises(MigrationFailure) as existing_error:
        migrate_studio_skill(clean_source, destination)
    assert existing_error.value.report.diagnostics[0].code == "GSKILL_MIGRATION_DESTINATION_EXISTS"
    assert marker.read_text(encoding="utf-8") == "do not overwrite\n"


def test_destination_created_during_staging_is_not_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "legacy"
    destination = tmp_path / "portable"
    _legacy_agent_skill(source)
    real_publish = migration_module.publish_directory_no_replace

    def race_publish(stage: Path, target: Path) -> None:
        target.mkdir()
        real_publish(stage, target)

    monkeypatch.setattr(migration_module, "publish_directory_no_replace", race_publish)

    with pytest.raises(MigrationFailure) as exc_info:
        migrate_studio_skill(source, destination)

    assert exc_info.value.report.diagnostics[0].code == "GSKILL_MIGRATION_DESTINATION_EXISTS"
    assert destination.is_dir()
    assert not list(destination.iterdir())
