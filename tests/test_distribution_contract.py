from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
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
DIST_INFO = "graph_skill_runtime-0.1.0a1.dist-info"
PACKAGE_VERSION = "0.1.0a1"


def _manifest() -> dict[str, object]:
    return json.loads(
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


def _required_moirai_assets(manifest: dict[str, object], *, prefix: str) -> set[str]:
    roles = manifest["roles"]
    skills = manifest["skills"]
    knowledge = manifest["knowledge"]
    assert isinstance(roles, list)
    assert isinstance(skills, list)
    assert isinstance(knowledge, list)
    return {
        prefix + "integration.json",
        *(prefix + f"roles/{role['id']}.md" for role in roles),
        *(prefix + f"skills/{skill['id']}/SKILL.md" for skill in skills),
        *(prefix + f"knowledge/{name}" for name in knowledge),
    }


def _metadata() -> str:
    return (
        "Metadata-Version: 2.4\n"
        "Name: graph-skill-runtime\n"
        f"Version: {PACKAGE_VERSION}\n"
        "Requires-Python: >=3.11\n"
    )


def _write_fake_wheel(
    path: Path,
    *,
    manifest: dict[str, object],
    extra_members: tuple[str, ...] = (),
) -> None:
    required_assets = _required_moirai_assets(manifest, prefix=MOIRAI_PREFIX)
    members = {
        *WHEEL_BASE_MEMBERS,
        *required_assets,
        f"{DIST_INFO}/METADATA",
        f"{DIST_INFO}/WHEEL",
        f"{DIST_INFO}/entry_points.txt",
        f"{DIST_INFO}/licenses/LICENSE",
        f"{DIST_INFO}/RECORD",
        *extra_members,
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name in members:
            if name == MOIRAI_MANIFEST:
                content = json.dumps(manifest)
            elif name.endswith("/METADATA"):
                content = _metadata()
            elif name.endswith("/WHEEL"):
                content = (
                    "Wheel-Version: 1.0\n"
                    "Generator: contract-test\n"
                    "Root-Is-Purelib: true\n"
                    "Tag: py3-none-any\n"
                )
            elif name.endswith("/entry_points.txt"):
                content = "[console_scripts]\ngskill = graph_skill_runtime.adapters.cli:main\n"
            else:
                content = "asset\n"
            archive.writestr(name, content)


def _add_tar_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    member.mode = 0o644
    archive.addfile(member, io.BytesIO(content))


def _write_fake_sdist(
    path: Path,
    *,
    manifest: dict[str, object],
    extra_members: tuple[str, ...] = (),
) -> None:
    root = f"graph_skill_runtime-{PACKAGE_VERSION}"
    source_prefix = f"{root}/src/"
    manifest_name = source_prefix + MOIRAI_MANIFEST
    required_assets = _required_moirai_assets(
        manifest,
        prefix=source_prefix + MOIRAI_PREFIX,
    )
    members = {
        f"{root}/LICENSE",
        f"{root}/PKG-INFO",
        f"{root}/README.md",
        f"{root}/pyproject.toml",
        f"{root}/src/graph_skill_runtime/__init__.py",
        f"{root}/src/graph_skill_runtime/py.typed",
        *required_assets,
        *extra_members,
    }
    with tarfile.open(path, "w:gz") as archive:
        for name in members:
            if name == manifest_name:
                content = json.dumps(manifest).encode()
            elif name.endswith("/PKG-INFO"):
                content = _metadata().encode()
            elif name.endswith("/pyproject.toml"):
                content = (
                    '[project]\nname = "graph-skill-runtime"\n'
                    f'version = "{PACKAGE_VERSION}"\n'
                    'requires-python = ">=3.11"\n'
                    '[project.scripts]\ngskill = "graph_skill_runtime.adapters.cli:main"\n'
                ).encode()
            else:
                content = b"asset\n"
            _add_tar_file(archive, name, content)


def _run_distribution_validator(dist: Path, manifest_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "accept_release_artifacts.py"),
            "validate",
            "--dist-dir",
            str(dist),
            "--manifest",
            str(manifest_path),
            "--source-commit",
            "0" * 40,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


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
    assert set(jobs["publish-to-pypi"]["needs"]) == {
        "build-distributions",
        "verify-distributions",
    }
    assert jobs["publish-to-pypi"]["permissions"] == {"id-token": "write"}
    assert jobs["publish-to-pypi"]["environment"]["name"] == "pypi"
    verify = jobs["verify-distributions"]
    assert verify["needs"] == "build-distributions"
    assert verify["strategy"]["matrix"]["os"] == [
        "ubuntu-latest",
        "windows-latest",
        "macos-latest",
    ]
    release_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "uv build --no-sources" in release_text
    assert "accept_release_artifacts.py accept" in release_text
    publish_steps = jobs["publish-to-pypi"]["steps"]
    assert publish_steps[-1]["uses"].startswith("pypa/gh-action-pypi-publish@")
    assert "password" not in publish_steps[-1].get("with", {})


def test_ci_required_jobs_carry_source_and_packaged_cross_platform_acceptance() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    assert jobs["runtime-tests"]["needs"] == "quality-gates"
    assert jobs["cross-platform-smoke"]["needs"] == "quality-gates"
    assert jobs["cross-platform-smoke"]["env"]["UV_PYTHON"] == "3.11"
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "uv build --no-sources" in ci_text
    assert ci_text.count("accept_release_artifacts.py accept") == 2
    for command in ("ruff check", "mypy --strict", "validate_round28_manifest.py"):
        assert command in ci_text


def test_distribution_validator_requires_closed_wheel_and_sdist_inventories(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / f"graph_skill_runtime-{PACKAGE_VERSION}-py3-none-any.whl"
    sdist = dist / f"graph_skill_runtime-{PACKAGE_VERSION}.tar.gz"
    artifact_manifest = tmp_path / "build" / "release-artifacts.json"
    manifest = _manifest()
    _write_fake_wheel(wheel, manifest=manifest)
    _write_fake_sdist(sdist, manifest=manifest)

    valid = _run_distribution_validator(dist, artifact_manifest)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    recorded = json.loads(artifact_manifest.read_text(encoding="utf-8"))
    assert recorded["schema_version"] == "gskill.release-artifacts.v1"
    assert recorded["version"] == PACKAGE_VERSION
    assert {item["kind"] for item in recorded["artifacts"]} == {"wheel", "sdist"}

    wrong_checkout = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "accept_release_artifacts.py"),
            "accept",
            "--dist-dir",
            str(dist),
            "--manifest",
            str(artifact_manifest),
            "--expected-source-commit",
            "1" * 40,
            "--logic-skill",
            str(REPO_ROOT / "examples" / "hello-world"),
            "--agent-skill",
            str(REPO_ROOT / "tests" / "fixtures" / "demo-echo-agent"),
            "--evidence",
            str(tmp_path / "should-not-exist.json"),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert wrong_checkout.returncode == 1
    assert "different checkout" in wrong_checkout.stderr

    with wheel.open("ab") as stream:
        stream.write(b"changed after manifest")
    tampered = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "accept_release_artifacts.py"),
            "accept",
            "--dist-dir",
            str(dist),
            "--manifest",
            str(artifact_manifest),
            "--expected-source-commit",
            "0" * 40,
            "--logic-skill",
            str(REPO_ROOT / "examples" / "hello-world"),
            "--agent-skill",
            str(REPO_ROOT / "tests" / "fixtures" / "demo-echo-agent"),
            "--evidence",
            str(tmp_path / "should-not-exist.json"),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert tampered.returncode == 1
    assert "size/SHA-256" in tampered.stderr

    _write_fake_wheel(
        wheel,
        manifest=manifest,
        extra_members=(MOIRAI_PREFIX + "graph.yaml",),
    )
    invalid_wheel = _run_distribution_validator(dist, artifact_manifest)
    assert invalid_wheel.returncode == 1
    assert "graph.yaml" in invalid_wheel.stderr

    _write_fake_wheel(wheel, manifest=manifest)
    root = f"graph_skill_runtime-{PACKAGE_VERSION}"
    _write_fake_sdist(
        sdist,
        manifest=manifest,
        extra_members=(
            f"{root}/src/graph_skill_runtime/integrations/assets/moirai/graph.yaml",
        ),
    )
    invalid_sdist = _run_distribution_validator(dist, artifact_manifest)
    assert invalid_sdist.returncode == 1
    assert "graph.yaml" in invalid_sdist.stderr
