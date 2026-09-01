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

Defect 3 (loader.py ``_load_root_skill_manifest``): the root ``SKILL.md``
metadata check runs as a single ``_fatal`` BEFORE the per-graph compile batch,
so one defective Agent Skills field hides every graph-layer defect in the
bundle. Fixing the root metadata then "reveals" the next defect on the NEXT
compile — the same disease as Defect 1, one stage earlier. Root metadata and
graph topology are independent facts, so one compile must report both.
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
        f"---\nname: {name}\ndescription: Exercise aggregated phase diagnostics.\n---\n",
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
    # ``rule_id`` on a CompileIssue, ``code`` on the payload fallback: a fatal
    # that never reached the aggregation seam would otherwise report an empty
    # code and hide WHICH single defect was raised.
    return {
        str(getattr(issue, "rule_id", None) or getattr(issue, "code", ""))
        for issue in _issues(exc)
    }


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


def _write_root_metadata_and_graph_defect(
    parent: Path, *, dir_name: str, skill_frontmatter: str
) -> Path:
    """One bundle carrying an independent root-metadata AND graph-topology defect.

    The graph defect is a phase depending on an undeclared phase, which the
    topology stage reports as a collected diagnostic; it is independent of
    whatever the root ``SKILL.md`` metadata says.
    """
    root = parent / dir_name
    _write(root / "SKILL.md", f"---\n{skill_frontmatter}\n---\n")
    _write(
        root / "graph.yaml",
        "schema_version: gskill.graph.v1\ngraph_id: root\n"
        f"description: Exercise root-plus-graph aggregation.\n{_EMPTY_IO}\n"
        "phases:\n"
        "  - id: main\n"
        "    depends_on: [ghost]\n"
        "    output: true\n",
    )
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"---\nname: main\n{_EMPTY_IO}\n---\n<role>R</role>\n<goal>G</goal>\n",
    )
    return root


def test_invalid_root_metadata_does_not_hide_graph_defects(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """A defective root SKILL.md must not mask the graph layer.

    ``description`` is missing (an Agent Skills metadata defect) and ``main``
    depends on an undeclared phase (a topology defect). One compile must report
    BOTH, so fixing the metadata cannot 'reveal' the topology defect afterwards.
    """
    skill_root = _write_root_metadata_and_graph_defect(
        tmp_path,
        dir_name="j04b-root-meta",
        skill_frontmatter="name: j04b-root-meta",
    )

    codes = _codes(_raises(skill_root, mock_skill_resolver))
    assert "[F-v3-skill-metadata-invalid]" in codes, codes
    assert "[F-v3-graph-depends-unknown]" in codes, codes


def test_root_name_directory_mismatch_does_not_hide_graph_defects(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """Same barrier, second root code: the name/directory mismatch is one
    independent fact and must be reported alongside the topology defect."""
    skill_root = _write_root_metadata_and_graph_defect(
        tmp_path,
        dir_name="j04b-root-name",
        skill_frontmatter="name: not-the-directory\ndescription: Wrong name on purpose.",
    )

    codes = _codes(_raises(skill_root, mock_skill_resolver))
    assert "[F-v3-skill-name-directory-mismatch]" in codes, codes
    assert "[F-v3-graph-depends-unknown]" in codes, codes


def test_root_metadata_defect_alone_still_fails_and_rides_the_issues_seam(
    tmp_path: Path, mock_skill_resolver: SkillResolverProtocol
) -> None:
    """Aggregating the root check must not soften it into a warning.

    With every graph fact healthy, a root name/directory mismatch is still the
    only defect — and it must both fail the compile and appear on
    ``compile_result.issues``, the one seam realtime lint projects. Before
    aggregation this code existed only as a bare payload, invisible to that
    seam.
    """
    skill_root = tmp_path / "j04b-root-only"
    _write(
        skill_root / "SKILL.md",
        "---\nname: not-the-directory\ndescription: Only the root name is wrong.\n---\n",
    )
    _write(
        skill_root / "graph.yaml",
        "schema_version: gskill.graph.v1\ngraph_id: root\n"
        f"description: Only the root name is wrong.\n{_EMPTY_IO}\n"
        "phases:\n"
        "  - id: main\n"
        "    depends_on: [input]\n"
        "    output: true\n",
    )
    _write(
        skill_root / "phases" / "main" / "AGENT.md",
        f"---\nname: main\n{_EMPTY_IO}\n---\n<role>R</role>\n<goal>G</goal>\n",
    )

    exc = _raises(skill_root, mock_skill_resolver)
    issues = getattr(getattr(exc, "compile_result", None), "issues", None)
    assert issues, "the root defect must reach compile_result.issues"
    assert [str(getattr(issue, "rule_id", "")) for issue in issues] == [
        "[F-v3-skill-name-directory-mismatch]"
    ]
    assert exc.payload is not None
    assert exc.payload.code == "[F-v3-skill-name-directory-mismatch]"
