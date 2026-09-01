from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core import cache as cache_module
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError

_EMPTY_OBJECT = """type: object
    properties: {}"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _skill_entry(root: Path) -> None:
    _write(
        root / "SKILL.md",
        f"---\nname: {root.name}\ndescription: Portable bundle contract fixture.\n"
        "metadata:\n  gskill: gskill.graph.v1\n---\n",
    )


def _graph(root: Path, *, graph_id: str, phase_id: str, output: bool = True) -> None:
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Contract graph {graph_id}.
io:
  inputs:
    {_EMPTY_OBJECT}
  outputs:
    {_EMPTY_OBJECT}
phases:
  - id: {phase_id}
    depends_on: [input]
    output: {str(output).lower()}
""",
    )


def _logic(root: Path, phase_id: str) -> None:
    _write(
        root / "phases" / phase_id / "LOGIC.md",
        f"""---
name: {phase_id}
io:
  inputs:
    {_EMPTY_OBJECT}
  outputs:
    {_EMPTY_OBJECT}
---
<action>identity</action>
""",
    )
    _write(
        root / "phases" / phase_id / "actions" / "identity.py",
        "def identity(inputs):\n    return {}\n",
    )


def _subgraph(root: Path, phase_id: str, target: str) -> None:
    _write(
        root / "phases" / phase_id / "SUBGRAPH.md",
        f"""---
name: {phase_id}
graph: {target}
io:
  inputs:
    {_EMPTY_OBJECT}
  outputs:
    {_EMPTY_OBJECT}
---
""",
    )


def _one_logic_skill(root: Path) -> None:
    _skill_entry(root)
    _graph(root, graph_id="root", phase_id="done")
    _logic(root, "done")


def _issues(exc: SkillLoadError) -> list[object]:
    return list(exc.compile_result.issues)


def test_missing_root_entry_and_graph_are_reported_in_one_compile(tmp_path: Path) -> None:
    root = tmp_path / "empty-skill"
    root.mkdir()

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    assert [(item.rule_id, item.source_path) for item in _issues(exc_info.value)] == [
        ("[F-v3-skill-entry-missing]", "SKILL.md"),
        ("[F-v3-graph-root-missing]", "graph.yaml"),
    ]


def test_nested_skill_entry_is_rejected_while_root_entry_remains_the_only_discovery_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portable-skill"
    _one_logic_skill(root)
    _write(
        root / "graphs" / "child" / "SKILL.md",
        "---\nname: child\ndescription: Nested entries are forbidden.\n---\n",
    )

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    issues = _issues(exc_info.value)
    assert [item.rule_id for item in issues] == ["[F-v3-skill-entry-nested]"]
    assert issues[0].source_path == "graphs/child/SKILL.md"


def test_graph_call_cycle_is_rejected_before_assembly(tmp_path: Path) -> None:
    root = tmp_path / "portable-skill"
    _skill_entry(root)
    _graph(root, graph_id="root", phase_id="to-a")
    _subgraph(root, "to-a", "graph-a")
    graph_a = root / "graphs" / "graph-a"
    _graph(graph_a, graph_id="graph-a", phase_id="to-b")
    _subgraph(graph_a, "to-b", "graph-b")
    graph_b = root / "graphs" / "graph-b"
    _graph(graph_b, graph_id="graph-b", phase_id="to-a")
    _subgraph(graph_b, "to-a", "graph-a")

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    cycle_issues = [
        item for item in _issues(exc_info.value) if item.rule_id == "[F-v3-graph-call-cycle]"
    ]
    assert len(cycle_issues) == 1
    assert "graph-a -> graph-b -> graph-a" in cycle_issues[0].message


def test_failed_registry_graph_does_not_make_valid_references_look_unknown(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portable-skill"
    _skill_entry(root)
    _graph(root, graph_id="root", phase_id="delegate")
    _subgraph(root, "delegate", "child")
    (root / "graphs" / "child" / "phases" / "done").mkdir(parents=True)

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    rule_ids = [item.rule_id for item in _issues(exc_info.value)]
    assert "[F-v3-graph-root-missing]" in rule_ids
    assert "[F-v3-graph-reference-unknown]" not in rule_ids


def test_graph_registry_rejects_non_directories_and_nested_registries(
    tmp_path: Path,
) -> None:
    root = tmp_path / "portable-skill"
    _one_logic_skill(root)
    _write(root / "graphs" / "README.md", "not a graph directory\n")
    (root / "graphs" / "child" / "graphs").mkdir(parents=True)

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(root, cache=False)

    issues = _issues(exc_info.value)
    registry_paths = {
        item.source_path
        for item in issues
        if item.rule_id == "[F-v3-graph-registry-invalid]"
    }
    assert registry_paths == {"graphs/README.md", "graphs/child/graphs"}


def test_cache_round_trip_rehydrates_the_complete_flat_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "portable-skill"
    _skill_entry(root)
    _graph(root, graph_id="root", phase_id="delegate")
    _subgraph(root, "delegate", "child")
    child = root / "graphs" / "child"
    _graph(child, graph_id="child", phase_id="done")
    _logic(child, "done")
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(cache_module, "get_cache_dir", lambda: cache_dir)

    first = compile_skill(root, cache=True)
    second = compile_skill(root, cache=True)

    assert sorted(first.graph_registry) == ["child", "root"]
    assert sorted(second.graph_registry) == ["child", "root"]
    assert second.graph_registry["child"].graph_root == child.resolve()
    assert list(cache_dir.glob("*.json"))
