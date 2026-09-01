"""llm_role layering: graph-level default + per-node use_graph_llm_role switch.

Design source: docs/skill-spec/01-PORTABLE-GSKILL-V1.md.
``llm_role`` is the whole-graph default role; AGENT.md ``llm_role`` overrides
it; ``use_graph_llm_role: true`` inverts the priority so the graph default
wins while the node's own value stays untouched in the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from graph_skill_runtime.core.graph_assembler import _AgentSystemPrompt, _resolve_phase_chat_model
from graph_skill_runtime.core.loader import SkillLoader
from graph_skill_runtime.core.manifest import (
    AgentNodeAST,
    GraphManifest,
    PhaseIOSchema,
    effective_llm_role,
)

# io is a required AgentNodeAST field; effective-role tests build the node directly
# and don't exercise io, so they use a minimal valid schema.
_MINIMAL_IO = PhaseIOSchema(
    inputs={"type": "object", "properties": {}},
    outputs={"type": "object", "properties": {}},
)


def _write_minimal_agent_skill(
    parent: Path,
    *,
    graph_extra: str = "",
    skill_extra: str = "",
) -> Path:
    root = parent / "llm-role-layering-test"
    (root / "phases" / "seg").mkdir(parents=True)
    graph_extra_block = f"{graph_extra}\n" if graph_extra else ""
    skill_extra_block = f"{skill_extra}\n" if skill_extra else ""
    (root / "SKILL.md").write_text(
        """---
name: llm-role-layering-test
description: Exercise graph and agent LLM role selection.
---
""",
        encoding="utf-8",
    )
    (root / "graph.yaml").write_text(
        f"""schema_version: gskill.graph.v1
graph_id: root
description: Exercise graph and agent LLM role selection.
{graph_extra_block}io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties:
      answer:
        type: string
phases:
  - id: seg
    depends_on: [input]
    output: true
""",
        encoding="utf-8",
    )
    (root / "phases" / "seg" / "AGENT.md").write_text(
        f"""---
name: seg
{skill_extra_block}io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties:
      answer:
        type: string
---
<role>Segmenter</role>
<goal>Answer.</goal>
""",
        encoding="utf-8",
    )
    return root


class _RecordingResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve(self, role_name: str, **kwargs: Any) -> object:
        self.calls.append(role_name)
        return object()


def _agent_ast(compiled_skill: Any, phase_id: str) -> AgentNodeAST:
    for node in compiled_skill.nodes:
        if node.phase_name == phase_id:
            ast = node.ast
            assert isinstance(ast, AgentNodeAST)
            return ast
    raise AssertionError(f"phase {phase_id!r} not found")


# --- compile-level: the fields exist and round-trip through the loader ---


def test_graph_manifest_accepts_graph_level_llm_role(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = _write_minimal_agent_skill(tmp_path, graph_extra="llm_role: fast")
    compiled = SkillLoader().compile_skill(skill_root, skill_resolver=mock_skill_resolver)
    assert compiled.manifest.llm_role == "fast"


def test_graph_manifest_llm_role_defaults_to_none(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    # The graph-level field is optional and defaults to None. Since 2026-08-31
    # the phase then has to name its own role — "no role anywhere" no longer
    # compiles — so a phase-level role is what leaves the graph default absent.
    skill_root = _write_minimal_agent_skill(tmp_path, skill_extra="llm_role: analyst")
    compiled = SkillLoader().compile_skill(skill_root, skill_resolver=mock_skill_resolver)
    assert compiled.manifest.llm_role is None


def test_agent_node_accepts_use_graph_llm_role(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = _write_minimal_agent_skill(
        tmp_path,
        graph_extra="llm_role: fast",
        skill_extra="llm_role: analyst\nuse_graph_llm_role: true",
    )
    compiled = SkillLoader().compile_skill(skill_root, skill_resolver=mock_skill_resolver)
    ast = _agent_ast(compiled, "seg")
    assert ast.use_graph_llm_role is True
    # The node's own value is preserved untouched next to the switch.
    assert ast.llm_role == "analyst"


def test_agent_node_use_graph_llm_role_defaults_to_false(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = _write_minimal_agent_skill(tmp_path, skill_extra="llm_role: analyst")
    compiled = SkillLoader().compile_skill(skill_root, skill_resolver=mock_skill_resolver)
    assert _agent_ast(compiled, "seg").use_graph_llm_role is False


# --- the effective-role chain (pure) ---


def test_effective_role_switch_on_graph_wins() -> None:
    ast = AgentNodeAST(
        mode="agent",
        name="seg",
        role="r",
        goal="g",
        llm_role="analyst",
        use_graph_llm_role=True,
        io=_MINIMAL_IO,
    )
    assert effective_llm_role(ast, "fast") == "fast"


def test_effective_role_switch_on_without_graph_default_resolves_nothing() -> None:
    # The sharp edge of the switch: `use_graph_llm_role: true` makes the graph
    # default win WITHOUT erasing the node's own value, so with no graph default
    # the phase resolves nothing even though its frontmatter names a role.
    ast = AgentNodeAST(
        mode="agent",
        name="seg",
        role="r",
        goal="g",
        llm_role="analyst",
        use_graph_llm_role=True,
        io=_MINIMAL_IO,
    )
    assert effective_llm_role(ast, None) is None


def test_effective_role_switch_off_node_wins() -> None:
    ast = AgentNodeAST(
        mode="agent", name="seg", role="r", goal="g", llm_role="analyst", io=_MINIMAL_IO
    )
    assert effective_llm_role(ast, "fast") == "analyst"


def test_effective_role_switch_off_without_node_inherits_graph() -> None:
    ast = AgentNodeAST(mode="agent", name="seg", role="r", goal="g", io=_MINIMAL_IO)
    assert effective_llm_role(ast, "fast") == "fast"


def test_effective_role_both_unset_resolves_nothing() -> None:
    # User ruling 2026-08-31: the default role is EMPTY and a role must be set
    # explicitly. The runtime invents no conventional fallback name — a name it
    # invents exists in no host's role table, so a skill relying on it compiled
    # green and then died at run time with no available route.
    ast = AgentNodeAST(mode="agent", name="seg", role="r", goal="g", io=_MINIMAL_IO)
    assert effective_llm_role(ast, None) is None


def test_no_module_level_fallback_role_constant_exists() -> None:
    # Locks the ruling against a reintroduced constant: the previous defect was
    # not the value "graph_skill_runtime" specifically, it was having one at all.
    import graph_skill_runtime.core.manifest as manifest_module

    assert not hasattr(manifest_module, "DEFAULT_LLM_ROLE")


# --- the resolver receives the effective role, not the raw node value ---


def test_resolver_receives_effective_role() -> None:
    resolver = _RecordingResolver()
    model = _resolve_phase_chat_model(
        "seg",
        "fast",
        chat_model=None,
        model_resolver=resolver,
        llm_provider=None,
        callbacks=(),
        system_prompt=_AgentSystemPrompt(
            text="", template_source="t", template_text="", source_path=None, variables={}
        ),
    )
    assert model is not None
    assert resolver.calls == ["fast"]


def test_phase_with_no_effective_role_is_refused_at_assembly() -> None:
    # Bare-SDK backstop for the 2026-08-31 ruling. Every seam below this call
    # declares the role in its contract (the predict stub records it, the
    # provider resolves models by it, events are labelled with it), so a phase
    # that resolves no role cannot honestly reach any of them. In practice
    # nothing arrives here, because compile rejects such a phase
    # unconditionally as [F-v3-agent-llm-role-missing]; this covers a caller
    # that assembles a hand-built AST without going through the compiler.
    import pytest

    resolver = _RecordingResolver()
    with pytest.raises(ValueError, match="resolves no LLM role"):
        _resolve_phase_chat_model(
            "seg",
            None,
            chat_model=None,
            model_resolver=resolver,
            llm_provider=None,
            callbacks=(),
            system_prompt=_AgentSystemPrompt(
                text="", template_source="t", template_text="", source_path=None, variables={}
            ),
        )
    assert resolver.calls == []


# --- graph manifest still rejects genuinely unknown fields ---


def test_graph_manifest_still_rejects_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GraphManifest.model_validate(
            {
                "schema_version": "gskill.graph.v1",
                "graph_id": "root",
                "description": "Reject an unknown graph field.",
                "made_up_field": 1,
                "io": {
                    "inputs": {"type": "object", "properties": {}},
                    "outputs": {"type": "object", "properties": {}},
                },
                "phases": [{"id": "seg", "depends_on": ["input"], "output": True}],
            }
        )
