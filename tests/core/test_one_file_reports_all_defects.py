"""RED tests for J-04.B: two engine compile-diagnostic defects on ONE file.

Defect 1 (loader.py ``build_phase_document``, agent branch): body-structure
diagnostics (missing ``<goal>``) and frontmatter schema diagnostics
(``max_iterations`` out of range) come from two sequential steps inside the
SAME call — ``_parse_agent_body(...)`` runs first and raises before
``AgentNodeAST.model_validate(...)`` ever gets a chance to run, so a phase
file carrying BOTH defects only ever reports the body one. Fixing the body
defect reveals the frontmatter one only on the NEXT compile — exactly the PM
complaint recorded in
``docs/studio/mvp1/02_capabilities/compile-lint/mvp1-alignment.md`` F6
("编译总是只弹个别错误,不完整……将role补上,goal的报错才出现").

Defect 2 (manifest.py ``_validate_max_iterations``): the range-check ``raise``
sits INSIDE the ``try`` block that guards ``int(value)``, so the validator's
own ``except (ValueError, TypeError)`` swallows it and re-raises the
wrong-cause message ("must be an integer") for an input that IS a valid
integer — just out of the 1..50 range.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader
from graph_skill_runtime.core.skill_resolver_protocol import SkillResolverProtocol

_EMPTY_IO = """io:
  inputs:
    type: object
    properties: {}
  outputs:
    type: object
    properties: {}"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_graph_root(root: Path, *, name: str) -> None:
    _write(
        root / "SKILL.md",
        f"---\nname: {name}\ndescription: Exercise aggregated phase diagnostics.\nmetadata:\n  gskill: gskill.graph.v1\n---\n",
    )
    _write(
        root / "graph.yaml",
        f"schema_version: gskill.graph.v1\ngraph_id: root\n"
        f"description: Exercise aggregated phase diagnostics.\n{_EMPTY_IO}\n"
        "phases:\n"
        "  - id: main\n"
        "    depends_on: [input]\n"
        "    output: true\n",
    )


def _write_solo_agent_skill(
    parent: Path, *, agent_frontmatter: str, agent_body: str
) -> Path:
    root = parent / "j04b"
    _write_graph_root(root, name="j04b")
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"---\nname: main\n{agent_frontmatter}\n{_EMPTY_IO}\n---\n{agent_body}",
    )
    return root


def _raises(root: Path, resolver: SkillResolverProtocol) -> SkillLoadError:
    with pytest.raises(SkillLoadError) as excinfo:
        SkillLoader().compile_skill(root, skill_resolver=resolver)
    return excinfo.value


def _issues(exc: SkillLoadError) -> list[object]:
    compile_result = getattr(exc, "compile_result", None)
    issues = getattr(compile_result, "issues", None)
    if isinstance(issues, list) and issues:
        return list(issues)
    return [exc.payload] if exc.payload is not None else []


def _codes(exc: SkillLoadError) -> set[str]:
    return {str(getattr(issue, "rule_id", "")) for issue in _issues(exc)}


def _messages(exc: SkillLoadError) -> str:
    return " | ".join(str(getattr(issue, "message", "")) for issue in _issues(exc))


def test_agent_body_defect_and_frontmatter_defect_report_together(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """One compile of an AGENT.md missing <goal> AND max_iterations: -1 must
    surface BOTH defects in the same pass, not just the body one first."""
    skill_root = _write_solo_agent_skill(
        tmp_path,
        agent_frontmatter="max_iterations: -1",
        agent_body="<role>R</role>\n",  # <goal> deliberately missing
    )

    codes = _codes(_raises(skill_root, mock_skill_resolver))
    assert "[F-v3-agent-goal-missing]" in codes, codes
    assert "[F-v3-agent-max-iterations-invalid]" in codes, codes


def test_logic_body_defect_and_frontmatter_defect_report_together(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """Same disease, logic phase: an empty <action> body tag must not mask an
    independent frontmatter schema defect (unknown field) in the same file."""
    skill_root = tmp_path / "j04b-logic"
    _write_graph_root(skill_root, name="j04b-logic")
    _write(
        skill_root / "phases" / "main" / "LOGIC.md",
        f"---\nname: main\ntotally_unknown_field: 1\n{_EMPTY_IO}\n---\n<action></action>\n",
    )

    codes = _codes(_raises(skill_root, mock_skill_resolver))
    assert "[F-v3-logic-actions-empty]" in codes, codes
    assert "[F-v3-logic-schema-unknown-field]" in codes, codes


def test_max_iterations_out_of_range_message_names_the_range(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """-1 is a valid integer, just out of range: the message must say so
    instead of claiming it is not an integer at all."""
    skill_root = _write_solo_agent_skill(
        tmp_path,
        agent_frontmatter="max_iterations: -1",
        agent_body="<role>R</role>\n<goal>G</goal>\n",
    )

    exc = _raises(skill_root, mock_skill_resolver)
    assert "[F-v3-agent-max-iterations-invalid]" in _codes(exc), _codes(exc)
    messages = _messages(exc)
    assert "between 1 and 50" in messages, messages
    assert "must be an integer" not in messages, messages
