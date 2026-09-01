from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.authoring.scaffold import create_gskill
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.gskill_version import GSKILL_SCHEMA_VERSION


def test_create_gskill_publishes_one_valid_marker_bound_bundle(tmp_path: Path) -> None:
    result = create_gskill(
        "review-story",
        parent=tmp_path,
        description="Review a story against explicit evidence.",
    )

    root = tmp_path / "review-story"
    compiled = compile_skill(root, cache=False)

    assert result.skill_root == str(root)
    assert result.gskill_version == GSKILL_SCHEMA_VERSION
    assert result.files == ("SKILL.md", "graph.yaml", "phases/main/AGENT.md")
    assert compiled.skill_manifest is not None
    assert compiled.skill_manifest.metadata == {"gskill": GSKILL_SCHEMA_VERSION}
    assert compiled.manifest.schema_version == GSKILL_SCHEMA_VERSION
    assert "gSkill for Graph Skill Runtime" in (root / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_create_gskill_refuses_to_adopt_an_existing_destination(tmp_path: Path) -> None:
    existing = tmp_path / "owned-skill"
    existing.mkdir()
    sentinel = existing / "owned.txt"
    sentinel.write_text("keep\n", encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="will not be adopted"):
        create_gskill(
            "owned-skill",
            parent=tmp_path,
            description="Must not replace existing content.",
        )

    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert tuple(existing.iterdir()) == (sentinel,)


@pytest.mark.parametrize("name", ["Uppercase", "two--hyphens", "path/name", "-edge"])
def test_create_gskill_rejects_names_outside_agent_skills_identity(
    tmp_path: Path,
    name: str,
) -> None:
    with pytest.raises(ValueError, match="NAME must contain"):
        create_gskill(name, parent=tmp_path, description="Invalid name fixture.")


def test_create_cli_returns_the_same_structured_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main(
        [
            "create",
            "cli-created",
            "--path",
            str(tmp_path),
            "--description",
            "Create a portable workflow through the installed CLI.",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "created"
    assert payload["gskill_version"] == GSKILL_SCHEMA_VERSION
    assert compile_skill(tmp_path / "cli-created", cache=False).manifest.graph_id == "main"
