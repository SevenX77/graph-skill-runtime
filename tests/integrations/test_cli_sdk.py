from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_skill_runtime.adapters import cli as cli_module
from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.integrations.installer import IntegrationInstaller
from graph_skill_runtime.integrations.models import (
    IntegrationRequest,
    IntegrationScope,
    IntegrationTarget,
)
from graph_skill_runtime.sdk import (
    detect_integration_hosts,
    install_integration,
    plan_integration_install,
    plan_integration_uninstall,
    uninstall_integration,
)
from tests.integrations._fake_assets import FakeMoiraiAssets


def _installer(
    tmp_path: Path,
    *,
    detected: frozenset[str] = frozenset(),
) -> IntegrationInstaller:
    return IntegrationInstaller(
        assets=FakeMoiraiAssets(),
        home=tmp_path / "home",
        user_state_root=tmp_path / "runtime-state",
        python_executable=tmp_path / "python-runtime",
        which=lambda name: str(tmp_path / "bin" / name) if name in detected else None,
    )


def _request(tmp_path: Path, *targets: IntegrationTarget) -> IntegrationRequest:
    project = tmp_path / "project"
    project.mkdir()
    return IntegrationRequest(
        targets=targets,
        scope=IntegrationScope.PROJECT,
        project_root=str(project),
    )


def test_cli_detection_is_read_only_and_does_not_compose_the_runtime_application(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _installer(tmp_path, detected=frozenset({"codex", "gemini"}))

    def unexpected_composition() -> object:
        raise AssertionError("runtime application must not be composed")

    monkeypatch.setattr(cli_module, "create_application", unexpected_composition)

    exit_code = cli_main(
        ["integrations", "detect"],
        integration_installer=installer,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert {item["target"] for item in payload["detections"] if item["detected"]} == {
        "codex",
        "gemini",
    }
    assert not (tmp_path / "home").exists()
    assert not (tmp_path / "runtime-state").exists()


def test_cli_dry_run_install_reports_plan_without_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installer = _installer(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    exit_code = cli_main(
        [
            "integrations",
            "install",
            "moirai",
            "--targets",
            "claude,codex",
            "--scope",
            "project",
            "--project-root",
            str(project),
            "--dry-run",
        ],
        integration_installer=installer,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "planned"
    assert payload["plan"]["targets"] == ["claude", "codex"]
    assert tuple(project.iterdir()) == ()


def test_cli_detected_install_reinstall_and_uninstall_share_one_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installer = _installer(tmp_path, detected=frozenset({"codex"}))
    project = tmp_path / "project"
    project.mkdir()
    common = [
        "moirai",
        "--targets",
        "detected",
        "--scope",
        "project",
        "--project-root",
        str(project),
    ]

    first_exit = cli_main(
        ["integrations", "install", *common],
        integration_installer=installer,
    )
    first = json.loads(capsys.readouterr().out)
    second_exit = cli_main(
        ["integrations", "install", *common],
        integration_installer=installer,
    )
    second = json.loads(capsys.readouterr().out)
    remove_exit = cli_main(
        ["integrations", "uninstall", *common],
        integration_installer=installer,
    )
    removed = json.loads(capsys.readouterr().out)

    assert first_exit == second_exit == remove_exit == 0
    assert first["status"] == "installed"
    assert second["status"] == "unchanged"
    assert removed["status"] == "uninstalled"
    assert not (project / ".agents" / "skills" / "moirai" / "SKILL.md").exists()


def test_cli_conflict_is_structured_and_returns_exit_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installer = _installer(tmp_path)
    project = tmp_path / "project"
    conflict = project / ".cursor" / "skills" / "moirai" / "SKILL.md"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("user owned\n", encoding="utf-8")

    exit_code = cli_main(
        [
            "integrations",
            "install",
            "moirai",
            "--targets",
            "cursor",
            "--scope",
            "project",
            "--project-root",
            str(project),
        ],
        integration_installer=installer,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["status"] == "conflict"
    assert payload["plan"]["can_apply"] is False
    assert conflict.read_text(encoding="utf-8") == "user owned\n"


def test_cli_detected_requires_at_least_one_supported_host(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    exit_code = cli_main(
        [
            "integrations",
            "install",
            "moirai",
            "--targets",
            "detected",
            "--scope",
            "project",
            "--project-root",
            str(project),
        ],
        integration_installer=_installer(tmp_path),
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["code"] == "GSKILL_INVALID_REQUEST"
    assert "no supported host executables" in payload["message"]
    assert tuple(project.iterdir()) == ()


def test_cli_returns_a_structured_internal_error_for_an_apply_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _installer(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    def fail_apply(_request: IntegrationRequest) -> object:
        raise OSError("simulated write failure")

    monkeypatch.setattr(installer, "install", fail_apply)

    exit_code = cli_main(
        [
            "integrations",
            "install",
            "moirai",
            "--targets",
            "codex",
            "--scope",
            "project",
            "--project-root",
            str(project),
        ],
        integration_installer=installer,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["code"] == "GSKILL_INTERNAL_ERROR"
    assert payload["message"] == "simulated write failure"


def test_sdk_facade_projects_the_same_plan_and_result_models(tmp_path: Path) -> None:
    installer = _installer(tmp_path, detected=frozenset({"claude"}))
    request = _request(tmp_path, IntegrationTarget.CLAUDE)

    assert detect_integration_hosts(installer=installer).detections == installer.detect_hosts()
    assert plan_integration_install(request, installer=installer) == installer.plan_install(request)
    installed = install_integration(request, installer=installer)
    assert installed.status == "installed"
    assert plan_integration_uninstall(request, installer=installer) == installer.plan_uninstall(
        request
    )
    removed = uninstall_integration(request, installer=installer)
    assert removed.status == "uninstalled"
