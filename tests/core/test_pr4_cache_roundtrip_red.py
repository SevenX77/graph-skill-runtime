from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.skill_resolver_protocol import SkillResolutionError


class DictSkillResolver:
    def __init__(self, roots: dict[str, Path]) -> None:
        self.roots = roots

    def resolve_skill(self, skill_id: str) -> Path:
        try:
            return self.roots[skill_id]
        except KeyError as exc:
            raise SkillResolutionError(skill_id, "not registered") from exc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_graph(root: Path, *, name: str, phase: str = "main") -> None:
    _write(
        root / "SKILL.md",
        f"""---
name: {name}
description: Exercise cache round-trip fidelity.
---
""",
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Exercise cache round-trip fidelity.
io:
  inputs:
    type: object
    properties:
      text:
        type: string
  outputs:
    type: object
    properties: {{}}
phases:
  - id: {phase}
    depends_on: [input]
    output: true
""",
    )


def _write_child_skill(root: Path) -> None:
    _write_graph(root, name="child-cache-roundtrip", phase="child")
    _write(
        root / "phases" / "child" / "AGENT.md",
        """---
name: child
io:
  inputs:
    type: object
    properties:
      text:
        type: string
    required: [text]
  outputs:
    type: object
    properties: {}
---
<role>Child</role>
<goal>Handle delegated work.</goal>
""",
    )


def _write_parent_skill(root: Path) -> None:
    _write_graph(root, name="parent-cache-roundtrip", phase="main")
    _write(
        root / "phases" / "main" / "AGENT.md",
        """---
name: main
subagents:
  - name: child_expert
    target_skill: demo-child
    description: Resolve child by skill id.
io:
  inputs:
    type: object
    properties:
      text:
        type: string
  outputs:
    type: object
    properties: {}
---
<role>Parent</role>
<goal>Delegate work.</goal>
""",
    )


def test_pr4_cache_hit_preserves_subagents_tools_and_phase_tokens(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parent = tmp_path / "parent-cache-roundtrip"
    child = tmp_path / "child-cache-roundtrip"
    _write_parent_skill(parent)
    _write_child_skill(child)
    resolver = DictSkillResolver({"demo-child": child})

    monkeypatch.setattr("graph_skill_runtime.core.cache.get_cache_dir", lambda: tmp_path / "cache")

    cold = compile_skill(parent, cache=True, skill_resolver=resolver)
    hit = compile_skill(parent, cache=True, skill_resolver=resolver)

    assert cold.subagents_by_phase["main"]
    assert hit.subagents_by_phase == cold.subagents_by_phase

    tool_names = {tool.name for tool in hit.tools.for_phase("main")}
    assert "call_subagent_child_expert" in tool_names

    assert hit.phase_tokens == cold.phase_tokens
    token = hit.phase_tokens["main"]
    assert token.attrs == {"depends_on": "input", "output": "true"}
    assert token.line_start > 0
