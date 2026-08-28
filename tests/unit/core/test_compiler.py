from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import GraphAgentError, SkillCompilationError, SkillLoadError


def test_skill_compilation_error_formats_structured_context() -> None:
    err = SkillCompilationError(
        "Invalid phase",
        skill_path=Path("GRAPH.md"),
        line=11,
        field_path="phases.0.id",
        suggestion="Provide a non-empty phase id.",
    )

    assert isinstance(err, GraphAgentError)
    assert str(err) == (
        "Invalid phase\n"
        "  at GRAPH.md:11\n"
        "  field: phases.0.id\n"
        "  suggestion: Provide a non-empty phase id."
    )


def test_compile_skill_rejects_a_file_instead_of_a_portable_root(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: portable\n---\n", encoding="utf-8")

    with pytest.raises(SkillLoadError, match="expects a portable gSkill root directory"):
        compile_skill(skill, cache=False, skill_resolver=mock_skill_resolver)
