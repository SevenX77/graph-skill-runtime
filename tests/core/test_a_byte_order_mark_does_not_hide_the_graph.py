"""A UTF-8 byte-order mark is encoding, not authored content."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.parser import parse_markdown_parts, parse_markdown_parts_best_effort
from graph_skill_runtime.core.topology_projection import load_graph_topology_projection

GRAPH = """schema_version: gskill.graph.v1
graph_id: bom-skill
description: BOM portability fixture.
io:
  inputs: {type: object, properties: {}}
  outputs: {type: object, properties: {}}
phases:
  - id: alpha
    depends_on: [input]
    output: false
  - id: beta
    depends_on: [alpha]
    output: true
"""

SKILL = """---
name: bom-skill
description: BOM portability fixture.
metadata:
  gskill: gskill.graph.v1
---

Use this skill for BOM portability tests.
"""


@pytest.fixture
def skill_with_bom(tmp_path: Path) -> Path:
    """A portable skill directory exactly as a Windows editor may leave it."""

    (tmp_path / "graph.yaml").write_bytes(b"\xef\xbb\xbf" + GRAPH.encode("utf-8"))
    (tmp_path / "SKILL.md").write_bytes(b"\xef\xbb\xbf" + SKILL.encode("utf-8"))
    for phase in ("alpha", "beta"):
        phase_dir = tmp_path / "phases" / phase
        phase_dir.mkdir(parents=True)
        (phase_dir / "LOGIC.md").write_text(
            f"""---
name: {phase}
io:
  inputs: {{type: object, properties: {{}}}}
  outputs: {{type: object, properties: {{}}}}
---
<action>identity</action>
""",
            encoding="utf-8",
        )
    return tmp_path


def test_a_graph_written_by_a_windows_editor_still_has_its_phases(skill_with_bom: Path) -> None:
    projection = load_graph_topology_projection(skill_with_bom)

    assert projection.phases == ["alpha", "beta"]


def test_the_mark_never_reaches_agent_skill_frontmatter(skill_with_bom: Path) -> None:
    frontmatter, body, _ = parse_markdown_parts(skill_with_bom / "SKILL.md")

    assert frontmatter["name"] == "bom-skill"
    assert "\ufeff" not in body


def test_the_tolerant_parser_agrees_with_the_strict_one(skill_with_bom: Path) -> None:
    strict, _, _ = parse_markdown_parts(skill_with_bom / "SKILL.md")
    tolerant, _, _ = parse_markdown_parts_best_effort(skill_with_bom / "SKILL.md")

    assert strict["name"] == tolerant["name"] == "bom-skill"
