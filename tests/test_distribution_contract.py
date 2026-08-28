from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MOIRAI_PREFIX = "graph_skill_runtime/integrations/assets/moirai/"
MOIRAI_MANIFEST = MOIRAI_PREFIX + "integration.json"
WHEEL_BASE_MEMBERS = {
    "graph_skill_runtime/__init__.py",
    "graph_skill_runtime/migration/atomic_publish.py",
    "graph_skill_runtime/migration/studio_v030.py",
    "graph_skill_runtime/py.typed",
    "graph_skill_runtime/skills/builtin/md-patch/SKILL.md",
}


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


def test_business_examples_live_outside_the_wheel_package() -> None:
    configuration = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = configuration["tool"]["hatch"]["build"]["targets"]["wheel"]
    package_examples = REPO_ROOT / "src" / "graph_skill_runtime" / "examples"

    assert wheel == {"packages": ["src/graph_skill_runtime"]}
    assert (REPO_ROOT / "examples" / "hello-world" / "SKILL.md").is_file()
    assert not any(candidate.is_file() for candidate in package_examples.rglob("*"))
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
            "from graph_skill_runtime.adapters.mcp import create_server; "
            "from graph_skill_runtime.adapters.cli import main; "
            "from graph_skill_runtime.integrations.installer import IntegrationInstaller; "
            "IntegrationInstaller().detect_hosts(); "
            "create_server(); "
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


def test_wheel_validator_requires_the_closed_manifest_derived_moirai_inventory(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "candidate.whl"
    manifest = json.loads(
        (
            REPO_ROOT
            / "src"
            / "graph_skill_runtime"
            / "integrations"
            / "assets"
            / "moirai"
            / "integration.json"
        ).read_text(encoding="utf-8")
    )
    required_assets = {
        MOIRAI_MANIFEST,
        *(MOIRAI_PREFIX + f"roles/{role['id']}.md" for role in manifest["roles"]),
        *(MOIRAI_PREFIX + f"skills/{skill['id']}/SKILL.md" for skill in manifest["skills"]),
        *(MOIRAI_PREFIX + f"knowledge/{name}" for name in manifest["knowledge"]),
    }
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in WHEEL_BASE_MEMBERS | required_assets:
            content = json.dumps(manifest) if name == MOIRAI_MANIFEST else "asset\n"
            archive.writestr(name, content)

    valid = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "smoke_built_wheel.py"), str(wheel)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr

    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(MOIRAI_PREFIX + "graph.yaml", "not a business skill\n")

    invalid = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "smoke_built_wheel.py"), str(wheel)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert invalid.returncode == 1
    assert "graph.yaml" in invalid.stderr
