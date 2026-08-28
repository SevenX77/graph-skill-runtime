from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.runner import run_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "examples" / "hello-world"


def test_repository_hello_world_is_a_runnable_portable_gskill(tmp_path: Path) -> None:
    compiled = compile_skill(SKILL_ROOT, cache=False)

    assert compiled.skill_manifest is not None
    assert compiled.skill_manifest.name == "hello-world"
    assert compiled.manifest.graph_id == "main"
    assert [node.phase_name for node in compiled.nodes] == ["greet"]

    result = run_skill(
        SKILL_ROOT,
        workspace_dir=tmp_path / "workspace",
        name="Developer",
    )

    assert result.success is True
    assert result.context["greeting"] == "Hello, Developer! Welcome to Graph Skill Runtime."
