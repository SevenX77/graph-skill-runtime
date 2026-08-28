from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.migration.atomic_publish import publish_directory_no_replace


def test_publish_directory_is_atomic_when_destination_is_absent(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    destination = tmp_path / "published"
    stage.mkdir()
    (stage / "payload.txt").write_text("ready\n", encoding="utf-8")

    publish_directory_no_replace(stage, destination)

    assert not stage.exists()
    assert (destination / "payload.txt").read_text(encoding="utf-8") == "ready\n"


def test_publish_directory_never_replaces_an_empty_destination(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    destination = tmp_path / "published"
    stage.mkdir()
    destination.mkdir()
    (stage / "payload.txt").write_text("ready\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        publish_directory_no_replace(stage, destination)

    assert stage.is_dir()
    assert destination.is_dir()
    assert not list(destination.iterdir())
