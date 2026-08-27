from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from graph_skill_runtime.adapters.snapshots import LocalRunSnapshotStore
from graph_skill_runtime.application.config import ConfigResolver, ConfigurationError
from graph_skill_runtime.domain.models import (
    ConfigSource,
    HostNativeExecutorConfig,
    RunInvocation,
    RunPreset,
    RuntimeProfileOverlay,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_four_layers_resolve_to_one_absolute_replayable_snapshot(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    user_config = tmp_path / "user-config" / "gskill.toml"
    _write(
        user_config,
        """schema_version = "gskill.config.v1"

[runtime]
state_dir = "user-state"
required_capabilities = ["user-capability"]

[runtime.executor]
kind = "cli"
vendor = "codex"
""",
    )
    _write(
        skill_root / "gskill.toml",
        """schema_version = "gskill.config.v1"

[runtime]
state_dir = ".project-state"
required_capabilities = ["project-capability"]

[runtime.executor]
kind = "embedded"

[presets.fast.inputs]
topic = "preset topic"

[[presets.fast.artifact_requests]]
artifact_id = "report"
""",
    )

    resolver = ConfigResolver(user_config_path=user_config)
    invocation = RunInvocation(
        skill_root=str(skill_root),
        run_id="run-1",
        preset_id="fast",
        runtime=RuntimeProfileOverlay(executor=HostNativeExecutorConfig()),
        inputs={"topic": "invocation topic"},
    )
    resolution = resolver.resolve(invocation)

    assert resolution.profile.profile.executor.kind == "host-native"
    assert resolution.profile.profile.required_capabilities == ("project-capability",)
    assert resolution.profile.state_root == str((skill_root / ".project-state").resolve())
    assert resolution.request.inputs == {"topic": "invocation topic"}
    assert resolution.request.artifact_requests[0].artifact_id == "report"
    assert resolution.request.profile == resolution.profile
    assert resolution.request.run_id == "run-1"

    profile_origins = {origin.field: origin.source for origin in resolution.profile.field_origins}
    assert profile_origins["runtime.executor"] is ConfigSource.INVOCATION
    assert profile_origins["runtime.state_dir"] is ConfigSource.PROJECT
    assert profile_origins["runtime.required_capabilities"] is ConfigSource.PROJECT
    value_origins = {origin.field: origin.source for origin in resolution.request.value_origins}
    assert value_origins["inputs"] is ConfigSource.INVOCATION
    assert value_origins["inputs.topic"] is ConfigSource.INVOCATION
    assert value_origins["artifact_requests"] is ConfigSource.PRESET

    snapshot_store = LocalRunSnapshotStore()
    snapshot_path = Path(snapshot_store.save(resolution.request))
    assert snapshot_path.is_file()
    assert snapshot_store.load(Path(resolution.profile.state_root), "run-1") == resolution.request


def test_run_request_and_persisted_snapshot_are_immutable(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    resolver = ConfigResolver(user_config_path=tmp_path / "missing.toml")
    original = resolver.resolve(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="immutable-run",
            inputs={"nested": {"items": ["first"]}},
        )
    ).request
    changed = resolver.resolve(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="immutable-run",
            inputs={"nested": {"items": ["second"]}},
        )
    ).request

    nested = original.inputs["nested"]
    assert isinstance(nested, dict)
    items = nested["items"]
    assert isinstance(items, list)
    with pytest.raises(TypeError, match="immutable"):
        original.inputs["new"] = "mutated"
    with pytest.raises(TypeError, match="immutable"):
        nested["new"] = "mutated"
    with pytest.raises(TypeError, match="immutable"):
        items.append("mutated")

    store = LocalRunSnapshotStore()
    path = Path(store.save(original))
    assert Path(store.save(original)) == path
    with pytest.raises(ValueError, match="different content"):
        store.save(changed)
    assert store.load(Path(original.profile.state_root), original.run_id) == original


def test_relative_user_state_dir_is_anchored_to_user_config_directory(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    user_config = tmp_path / "config" / "gskill.toml"
    _write(
        user_config,
        """schema_version = "gskill.config.v1"
[runtime]
state_dir = "machine-state"
""",
    )

    resolution = ConfigResolver(user_config_path=user_config).resolve(
        RunInvocation(skill_root=str(skill_root), run_id="run-user")
    )

    assert resolution.profile.state_root == str((user_config.parent / "machine-state").resolve())


def test_explicit_empty_invocation_inputs_clear_preset_defaults(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    _write(
        skill_root / "gskill.toml",
        """schema_version = "gskill.config.v1"
[presets.default.inputs]
topic = "preset"
""",
    )

    resolution = ConfigResolver(user_config_path=tmp_path / "missing.toml").resolve(
        RunInvocation(
            skill_root=str(skill_root),
            run_id="run-clear",
            preset_id="default",
            inputs={},
        )
    )

    assert resolution.request.inputs == {}


def test_user_config_cannot_own_named_business_presets(tmp_path: Path) -> None:
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    user_config = tmp_path / "user" / "gskill.toml"
    _write(
        user_config,
        """schema_version = "gskill.config.v1"
[presets.forbidden.inputs]
topic = "wrong owner"
""",
    )

    with pytest.raises(ConfigurationError, match="invalid user RuntimeProfile"):
        ConfigResolver(user_config_path=user_config).resolve(
            RunInvocation(skill_root=str(skill_root))
        )


@pytest.mark.parametrize("payload", [{"api_key": "raw"}, {"nested": {"access-token": "raw"}}])
def test_persistent_literal_inputs_reject_secret_shaped_keys(payload: object) -> None:
    with pytest.raises(ValidationError, match="SecretReference"):
        RunPreset.model_validate({"preset_id": "unsafe", "inputs": payload})
