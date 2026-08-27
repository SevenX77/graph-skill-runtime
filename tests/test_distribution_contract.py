from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_provider_clients_are_explicit_embedded_dependencies_not_base_runtime() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    base_names = {requirement.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0] for requirement in project["dependencies"]}
    embedded_names = {
        requirement.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0]
        for requirement in project["optional-dependencies"]["embedded"]
    }

    assert {"langchain-openai", "openai", "python-dotenv"}.isdisjoint(base_names)
    assert embedded_names == {"langchain-openai", "openai", "python-dotenv"}


def test_distribution_import_and_console_names_are_one_hard_cut() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["name"] == "graph-skill-runtime"
    assert project["scripts"] == {"gskill": "graph_skill_runtime.adapters.cli:main"}
    assert not (REPO_ROOT / "src" / "graph_agent").exists()


def test_wheel_configuration_excludes_examples_and_stale_package_metadata() -> None:
    configuration = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = configuration["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel["exclude"] == ["src/graph_skill_runtime/examples/**"]
    assert not (REPO_ROOT / "src" / "graph_skill_runtime" / "requirements.txt").exists()
    assert not (REPO_ROOT / "src" / "graph_skill_runtime" / "CHANGELOG.md").exists()


def test_import_and_version_probe_do_not_write_host_configuration(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()
    config.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "APPDATA": str(config),
            "HOME": str(home),
            "LOCALAPPDATA": str(config),
            "PYTHONDONTWRITEBYTECODE": "1",
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(config),
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import graph_skill_runtime; "
            "from graph_skill_runtime.adapters.cli import main; "
            "raise SystemExit(main(['--version']))",
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().startswith("gskill ")
    assert not any(home.rglob("*"))
    assert not any(config.rglob("*"))


def test_release_workflow_separates_build_from_oidc_publish() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]

    assert workflow["on"] == {"release": {"types": ["published"]}}
    assert jobs["publish-to-pypi"]["needs"] == "build-distributions"
    assert jobs["publish-to-pypi"]["permissions"] == {"id-token": "write"}
    assert jobs["publish-to-pypi"]["environment"]["name"] == "pypi"
    publish_steps = jobs["publish-to-pypi"]["steps"]
    assert publish_steps[-1]["uses"].startswith("pypa/gh-action-pypi-publish@")
    assert "password" not in publish_steps[-1].get("with", {})
