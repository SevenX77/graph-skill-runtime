from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_skill_runtime.integrations import installer as installer_module
from graph_skill_runtime.integrations.installer import IntegrationInstaller
from graph_skill_runtime.integrations.models import (
    IntegrationRequest,
    IntegrationScope,
    IntegrationTarget,
)
from graph_skill_runtime.integrations.renderers import renderer_for
from graph_skill_runtime.ports.integrations import (
    FileProjection,
    JsonEntryProjection,
    ProjectionContext,
    TextBlockProjection,
)
from tests.integrations._fake_assets import FakeMoiraiAssets


def _installer(tmp_path: Path) -> IntegrationInstaller:
    return IntegrationInstaller(
        assets=FakeMoiraiAssets(),
        home=tmp_path / "home",
        user_state_root=tmp_path / "runtime-state",
        python_executable=tmp_path / "python-runtime",
        which=lambda _name: None,
    )


def _project_request(tmp_path: Path, *targets: IntegrationTarget) -> IntegrationRequest:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    return IntegrationRequest(
        targets=targets,
        scope=IntegrationScope.PROJECT,
        project_root=str(project),
    )


def _resources(
    tmp_path: Path,
    target: IntegrationTarget,
) -> tuple[FileProjection | JsonEntryProjection | TextBlockProjection, ...]:
    project = tmp_path / "project"
    return renderer_for(target).render(
        FakeMoiraiAssets(),
        ProjectionContext(
            scope=IntegrationScope.PROJECT,
            home=tmp_path / "home",
            project_root=project,
            python_executable=tmp_path / "python-runtime",
        ),
    )


def test_dry_plan_for_all_renderers_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    request = _project_request(tmp_path, *tuple(IntegrationTarget))
    project = Path(request.project_root or "")
    before = tuple(project.iterdir())

    plan = _installer(tmp_path).plan_install(request)

    assert plan.can_apply is True
    assert len(plan.targets) == 6
    assert tuple(project.iterdir()) == before
    assert not (project / ".gskill").exists()
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("target", tuple(IntegrationTarget))
def test_each_renderer_installs_idempotently_and_uninstalls_its_owned_projection(
    tmp_path: Path,
    target: IntegrationTarget,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, target)
    resources = _resources(tmp_path, target)

    installed = installer.install(request)
    repeated = installer.install(request)

    assert installed.status == "installed"
    assert installed.applied_changes == len(resources)
    assert repeated.status == "unchanged"
    assert repeated.applied_changes == 0
    for resource in resources:
        assert resource.path.exists()
    manifest = (
        Path(request.project_root or "")
        / ".gskill"
        / "integrations"
        / "moirai"
        / target.value
        / "install-manifest.json"
    )
    assert manifest.is_file()

    removed = installer.uninstall(request)

    assert removed.status == "uninstalled"
    assert removed.applied_changes == len(resources)
    assert not manifest.exists()
    for resource in resources:
        assert not resource.path.exists()
    assert installer.uninstall(request).status == "unchanged"


@pytest.mark.parametrize(
    "target",
    tuple(target for target in IntegrationTarget if target is not IntegrationTarget.CODEX),
)
def test_json_config_merge_and_uninstall_preserve_unrelated_user_values(
    tmp_path: Path,
    target: IntegrationTarget,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, target)
    config = next(
        resource for resource in _resources(tmp_path, target) if isinstance(resource, JsonEntryProjection)
    )
    config.path.parent.mkdir(parents=True, exist_ok=True)
    config.path.write_text('{"unrelated":{"keep":true}}\n', encoding="utf-8")

    assert installer.install(request).status == "installed"
    assert installer.uninstall(request).status == "uninstalled"

    assert json.loads(config.path.read_text(encoding="utf-8")) == {
        "unrelated": {"keep": True}
    }


def test_codex_managed_toml_block_preserves_existing_bytes(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CODEX)
    config = next(
        resource
        for resource in _resources(tmp_path, IntegrationTarget.CODEX)
        if isinstance(resource, TextBlockProjection)
    )
    original = b'# keep this comment\nmodel = "current"\n'
    config.path.parent.mkdir(parents=True, exist_ok=True)
    config.path.write_bytes(original)

    assert installer.install(request).status == "installed"
    assert config.marker.encode() in config.path.read_bytes()
    assert installer.uninstall(request).status == "uninstalled"
    assert config.path.read_bytes() == original


def test_unmanaged_file_conflict_blocks_every_target_without_overwrite(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(
        tmp_path,
        IntegrationTarget.CLAUDE,
        IntegrationTarget.CODEX,
    )
    claude_skill = next(
        resource
        for resource in _resources(tmp_path, IntegrationTarget.CLAUDE)
        if isinstance(resource, FileProjection) and resource.path.name == "SKILL.md"
    )
    claude_skill.path.parent.mkdir(parents=True, exist_ok=True)
    claude_skill.path.write_text("user content\n", encoding="utf-8")

    result = installer.install(request)

    assert result.status == "conflict"
    assert result.applied_changes == 0
    assert claude_skill.path.read_text(encoding="utf-8") == "user content\n"
    codex_resources = _resources(tmp_path, IntegrationTarget.CODEX)
    assert all(not resource.path.exists() for resource in codex_resources)
    assert not (Path(request.project_root or "") / ".gskill").exists()


@pytest.mark.parametrize(
    "target",
    tuple(target for target in IntegrationTarget if target is not IntegrationTarget.CODEX),
)
def test_unmanaged_shared_json_entry_is_never_adopted_or_overwritten(
    tmp_path: Path,
    target: IntegrationTarget,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, target)
    resources = _resources(tmp_path, target)
    config = next(resource for resource in resources if isinstance(resource, JsonEntryProjection))
    config.path.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, object] = {}
    current: dict[str, object] = document
    for key in config.selector[:-1]:
        nested: dict[str, object] = {}
        current[key] = nested
        current = nested
    current[config.selector[-1]] = config.value
    config.path.write_text(json.dumps(document), encoding="utf-8")

    result = installer.install(request)

    assert result.status == "conflict"
    assert "not owned" in result.plan.conflicts[0].reason
    assert json.loads(config.path.read_text(encoding="utf-8")) == document
    assert all(
        not resource.path.exists()
        for resource in resources
        if resource.path != config.path
    )


def test_unmanaged_codex_server_without_markers_blocks_install(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CODEX)
    resources = _resources(tmp_path, IntegrationTarget.CODEX)
    config = next(resource for resource in resources if isinstance(resource, TextBlockProjection))
    original = b'[mcp_servers.gskill]\ncommand = "user-command"\n'
    config.path.parent.mkdir(parents=True, exist_ok=True)
    config.path.write_bytes(original)

    result = installer.install(request)

    assert result.status == "conflict"
    assert "already exists" in result.plan.conflicts[0].reason
    assert config.path.read_bytes() == original
    assert all(
        not resource.path.exists()
        for resource in resources
        if resource.path != config.path
    )


def test_incompatible_codex_mcp_parent_blocks_install_without_rewriting_config(
    tmp_path: Path,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CODEX)
    resources = _resources(tmp_path, IntegrationTarget.CODEX)
    config = next(resource for resource in resources if isinstance(resource, TextBlockProjection))
    original = b'mcp_servers = "user-value"\n'
    config.path.parent.mkdir(parents=True, exist_ok=True)
    config.path.write_bytes(original)

    result = installer.install(request)

    assert result.status == "conflict"
    assert "must be a TOML table" in result.plan.conflicts[0].reason
    assert config.path.read_bytes() == original
    assert all(
        not resource.path.exists()
        for resource in resources
        if resource.path != config.path
    )


def test_opencode_jsonc_config_is_preserved_as_an_explicit_conflict(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.OPENCODE)
    resources = _resources(tmp_path, IntegrationTarget.OPENCODE)
    config = next(resource for resource in resources if isinstance(resource, JsonEntryProjection))
    jsonc = config.path.with_suffix(".jsonc")
    original = '{\n  // keep this comment\n  "model": "user/model",\n}\n'
    jsonc.parent.mkdir(parents=True, exist_ok=True)
    jsonc.write_text(original, encoding="utf-8")

    result = installer.install(request)

    assert result.status == "conflict"
    assert "JSONC" in result.plan.conflicts[0].reason
    assert jsonc.read_text(encoding="utf-8") == original
    assert not config.path.exists()
    assert all(
        not resource.path.exists()
        for resource in resources
        if resource.path != config.path
    )


def test_modified_owned_file_blocks_uninstall_and_preserves_whole_install(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CURSOR)
    resources = _resources(tmp_path, IntegrationTarget.CURSOR)
    assert installer.install(request).status == "installed"
    skill = next(
        resource
        for resource in resources
        if isinstance(resource, FileProjection) and resource.path.name == "SKILL.md"
    )
    skill.path.write_text("user modified\n", encoding="utf-8")

    result = installer.uninstall(request)

    assert result.status == "conflict"
    assert result.applied_changes == 0
    assert skill.path.read_text(encoding="utf-8") == "user modified\n"
    assert all(resource.path.exists() for resource in resources)


def test_modified_owned_json_entry_blocks_uninstall_without_removing_files(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.GEMINI)
    resources = _resources(tmp_path, IntegrationTarget.GEMINI)
    assert installer.install(request).status == "installed"
    config = next(resource for resource in resources if isinstance(resource, JsonEntryProjection))
    document = json.loads(config.path.read_text(encoding="utf-8"))
    document["mcpServers"]["gskill"]["command"] = "user-command"
    config.path.write_text(json.dumps(document), encoding="utf-8")

    result = installer.uninstall(request)

    assert result.status == "conflict"
    assert json.loads(config.path.read_text(encoding="utf-8"))["mcpServers"]["gskill"][
        "command"
    ] == "user-command"
    assert all(resource.path.exists() for resource in resources)


def test_tampered_manifest_cannot_redirect_uninstall_to_an_arbitrary_file(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.COPILOT)
    assert installer.install(request).status == "installed"
    manifest = (
        Path(request.project_root or "")
        / ".gskill"
        / "integrations"
        / "moirai"
        / "copilot"
        / "install-manifest.json"
    )
    victim = tmp_path / "victim.txt"
    victim.write_text("keep\n", encoding="utf-8")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["entries"][0]["path"] = str(victim)
    manifest.write_text(json.dumps(document), encoding="utf-8")

    result = installer.uninstall(request)

    assert result.status == "conflict"
    assert victim.read_text(encoding="utf-8") == "keep\n"


def test_manifest_with_duplicate_json_keys_is_a_conflict_and_cannot_authorize_deletion(
    tmp_path: Path,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.COPILOT)
    assert installer.install(request).status == "installed"
    manifest = (
        Path(request.project_root or "")
        / ".gskill"
        / "integrations"
        / "moirai"
        / "copilot"
        / "install-manifest.json"
    )
    original = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        original.replace(
            '"integration_id": "moirai",',
            '"integration_id": "wrong",\n  "integration_id": "moirai",',
            1,
        ),
        encoding="utf-8",
    )

    result = installer.uninstall(request)

    assert result.status == "conflict"
    assert "duplicate JSON key: integration_id" in result.plan.conflicts[0].reason
    assert manifest.is_file()


def test_apply_failure_rolls_back_created_files_and_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CLAUDE)
    project = Path(request.project_root or "")
    real_atomic_write = installer_module._atomic_write
    calls = 0

    def fail_second_write(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated disk failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(installer_module, "_atomic_write", fail_second_write)

    with pytest.raises(OSError, match="simulated disk failure"):
        installer.install(request)

    assert tuple(project.iterdir()) == ()


def test_apply_race_preserves_a_concurrent_user_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _installer(tmp_path)
    request = _project_request(tmp_path, IntegrationTarget.CLAUDE)
    resources = _resources(tmp_path, IntegrationTarget.CLAUDE)
    first = resources[0]
    concurrent = resources[1]
    real_atomic_write = installer_module._atomic_write
    calls = 0

    def introduce_concurrent_file(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        real_atomic_write(path, content)
        if calls == 1:
            concurrent.path.parent.mkdir(parents=True, exist_ok=True)
            concurrent.path.write_text("user-created during install\n", encoding="utf-8")

    monkeypatch.setattr(installer_module, "_atomic_write", introduce_concurrent_file)

    with pytest.raises(ValueError, match="changed after planning"):
        installer.install(request)

    assert not first.path.exists()
    assert concurrent.path.read_text(encoding="utf-8") == "user-created during install\n"


def test_user_scope_uses_host_home_and_runtime_owned_manifest_root(tmp_path: Path) -> None:
    installer = _installer(tmp_path)
    request = IntegrationRequest(
        targets=(IntegrationTarget.CODEX,),
        scope=IntegrationScope.USER,
    )

    assert installer.install(request).status == "installed"

    assert (tmp_path / "home" / ".agents" / "skills" / "moirai" / "SKILL.md").is_file()
    assert (
        tmp_path
        / "runtime-state"
        / "integrations"
        / "moirai"
        / "codex"
        / "install-manifest.json"
    ).is_file()


def test_detection_is_read_only_and_uses_exact_vendor_executable_names(tmp_path: Path) -> None:
    probes: list[str] = []

    def which(name: str) -> str | None:
        probes.append(name)
        return f"/tools/{name}" if name in {"codex", "gemini"} else None

    installer = IntegrationInstaller(
        assets=FakeMoiraiAssets(),
        home=tmp_path / "home",
        user_state_root=tmp_path / "state",
        python_executable=tmp_path / "python",
        which=which,
    )

    detections = installer.detect_hosts()

    assert installer.detected_targets() == (
        IntegrationTarget.CODEX,
        IntegrationTarget.GEMINI,
    )
    assert {item.target for item in detections if item.detected} == {
        IntegrationTarget.CODEX,
        IntegrationTarget.GEMINI,
    }
    assert set(probes) == {"claude", "codex", "copilot", "cursor-agent", "gemini", "opencode"}
    assert not (tmp_path / "home").exists()
    assert not (tmp_path / "state").exists()
