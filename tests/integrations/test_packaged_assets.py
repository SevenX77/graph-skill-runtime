from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets

ASSET_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "graph_skill_runtime"
    / "integrations"
    / "assets"
    / "moirai"
)


def _copy_assets(tmp_path: Path) -> Path:
    copied = tmp_path / "moirai"
    shutil.copytree(ASSET_ROOT, copied)
    return copied


def test_packaged_moirai_bundle_is_closed_utf8_and_complete() -> None:
    assets = PackagedMoiraiAssets()

    assert assets.integration_id == "moirai"
    assert assets.asset_version == "1.0.0"
    assert assets.role_ids() == ("moirai", "clotho", "lachesis", "atropos")
    assert assets.skill_ids() == (
        "moirai",
        "moirai-brainstorming",
        "moirai-domain-analysis",
        "moirai-graph-design",
        "moirai-agent-prompt-design",
        "moirai-compile-repair",
        "moirai-eval-judgement",
        "moirai-web-research",
    )
    assert len(assets.knowledge_files()) == 15
    assert all(assets.role_body(role_id).strip() for role_id in assets.role_ids())
    assert all(assets.skill_file(skill_id).startswith(b"---\n") for skill_id in assets.skill_ids())
    assert not any(path.name.casefold() == "graph.yaml" for path in ASSET_ROOT.rglob("*"))


def test_catalog_rejects_any_unmanifested_business_graph(tmp_path: Path) -> None:
    copied = _copy_assets(tmp_path)
    (copied / "graph.yaml").write_text("schema_version: gskill.graph.v1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected=graph.yaml"):
        PackagedMoiraiAssets(copied)


def test_catalog_rejects_skill_metadata_that_does_not_match_its_directory(
    tmp_path: Path,
) -> None:
    copied = _copy_assets(tmp_path)
    skill = copied / "skills" / "moirai" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace("name: moirai", "name: wrong-name", 1),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="must equal asset id"):
        PackagedMoiraiAssets(copied)


def test_catalog_rejects_duplicate_manifest_keys(tmp_path: Path) -> None:
    copied = _copy_assets(tmp_path)
    manifest = copied / "integration.json"
    original = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        original.replace(
            '"integration_id": "moirai",',
            '"integration_id": "wrong",\n  "integration_id": "moirai",',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="duplicate JSON key: integration_id"):
        PackagedMoiraiAssets(copied)
