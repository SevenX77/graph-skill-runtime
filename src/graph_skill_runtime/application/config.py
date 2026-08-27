"""Resolve user, project, preset, and invocation configuration into one snapshot."""

from __future__ import annotations

import os
import sys
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from graph_skill_runtime.domain.models import (
    ArtifactRequest,
    CheckpointStoreConfig,
    CompareCandidate,
    ConfigResolution,
    ConfigSource,
    ExecutorConfig,
    HostNativeExecutorConfig,
    InputBinding,
    JsonObject,
    NodeOverride,
    PermissionPolicy,
    PhaseAddress,
    ResolvedRuntimeProfile,
    RunInvocation,
    RunPreset,
    RunRequest,
    RuntimeErrorCode,
    RuntimeErrorPayload,
    RuntimeProfile,
    RuntimeProfileOverlay,
    SecretBinding,
    SqliteCheckpointStoreConfig,
    ValueOrigin,
)


class ConfigurationError(ValueError):
    """A configuration boundary rejected input before runtime execution."""

    def __init__(self, payload: RuntimeErrorPayload) -> None:
        super().__init__(payload.message)
        self.payload = payload


class _PresetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: JsonObject = Field(default_factory=dict)
    secret_inputs: tuple[SecretBinding, ...] = ()
    bindings: tuple[InputBinding, ...] = ()
    breakpoints: tuple[PhaseAddress, ...] = ()
    node_overrides: tuple[NodeOverride, ...] = ()
    compare_candidates: tuple[CompareCandidate, ...] = ()
    artifact_requests: tuple[ArtifactRequest, ...] = ()

    def to_preset(self, preset_id: str) -> RunPreset:
        return RunPreset(
            preset_id=preset_id,
            inputs=self.inputs,
            secret_inputs=self.secret_inputs,
            bindings=self.bindings,
            breakpoints=self.breakpoints,
            node_overrides=self.node_overrides,
            compare_candidates=self.compare_candidates,
            artifact_requests=self.artifact_requests,
        )


class _ProjectConfigDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["gskill.config.v1"]
    runtime: RuntimeProfileOverlay = Field(default_factory=RuntimeProfileOverlay)
    presets: dict[str, _PresetDocument] = Field(default_factory=dict)


class _UserConfigDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["gskill.config.v1"]
    runtime: RuntimeProfileOverlay = Field(default_factory=RuntimeProfileOverlay)


@dataclass
class _ProfileAccumulator:
    executor: ExecutorConfig = field(default_factory=HostNativeExecutorConfig)
    checkpoint_store: CheckpointStoreConfig = field(default_factory=SqliteCheckpointStoreConfig)
    state_dir: str | None = None
    permissions: PermissionPolicy = field(default_factory=PermissionPolicy)
    required_capabilities: tuple[str, ...] = ()
    fallback_executors: tuple[ExecutorConfig, ...] = ()
    origins: dict[str, ValueOrigin] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> _ProfileAccumulator:
        accumulator = cls()
        for field_name in (
            "executor",
            "checkpoint_store",
            "state_dir",
            "permissions",
            "required_capabilities",
            "fallback_executors",
        ):
            accumulator.origins[field_name] = ValueOrigin(
                field=f"runtime.{field_name}", source=ConfigSource.DEFAULT
            )
        return accumulator

    def apply(
        self,
        overlay: RuntimeProfileOverlay | None,
        *,
        source: ConfigSource,
        source_path: Path | None,
    ) -> None:
        if overlay is None:
            return
        rendered_source_path = str(source_path) if source_path is not None else None
        if overlay.executor is not None:
            self.executor = overlay.executor
            self.origins["executor"] = ValueOrigin(
                field="runtime.executor", source=source, source_path=rendered_source_path
            )
        if overlay.checkpoint_store is not None:
            self.checkpoint_store = overlay.checkpoint_store
            self.origins["checkpoint_store"] = ValueOrigin(
                field="runtime.checkpoint_store",
                source=source,
                source_path=rendered_source_path,
            )
        if overlay.state_dir is not None:
            self.state_dir = overlay.state_dir
            self.origins["state_dir"] = ValueOrigin(
                field="runtime.state_dir", source=source, source_path=rendered_source_path
            )
        if overlay.permissions is not None:
            self.permissions = overlay.permissions
            self.origins["permissions"] = ValueOrigin(
                field="runtime.permissions", source=source, source_path=rendered_source_path
            )
        if overlay.required_capabilities is not None:
            self.required_capabilities = tuple(overlay.required_capabilities)
            self.origins["required_capabilities"] = ValueOrigin(
                field="runtime.required_capabilities",
                source=source,
                source_path=rendered_source_path,
            )
        if overlay.fallback_executors is not None:
            self.fallback_executors = tuple(overlay.fallback_executors)
            self.origins["fallback_executors"] = ValueOrigin(
                field="runtime.fallback_executors",
                source=source,
                source_path=rendered_source_path,
            )


def default_user_config_path() -> Path:
    """Return the OS-standard user configuration path without creating it."""

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "graph-skill-runtime" / "gskill.toml"


def _config_error(message: str, *, source_path: Path | None = None) -> ConfigurationError:
    return ConfigurationError(
        RuntimeErrorPayload(
            code=RuntimeErrorCode.CONFIG_INVALID,
            message=message,
            source_path=str(source_path) if source_path is not None else None,
        )
    )


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise _config_error(f"cannot read configuration: {exc}", source_path=path) from exc
    try:
        return tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise _config_error(f"invalid TOML: {exc}", source_path=path) from exc


def _load_user_config(path: Path) -> _UserConfigDocument | None:
    if not path.exists():
        return None
    try:
        return _UserConfigDocument.model_validate(_read_toml(path))
    except ValidationError as exc:
        raise _config_error(f"invalid user RuntimeProfile: {exc}", source_path=path) from exc


def _load_project_config(path: Path) -> _ProjectConfigDocument | None:
    if not path.exists():
        return None
    try:
        return _ProjectConfigDocument.model_validate(_read_toml(path))
    except ValidationError as exc:
        raise _config_error(f"invalid project configuration: {exc}", source_path=path) from exc


def _resolved_state_root(
    accumulator: _ProfileAccumulator,
    *,
    skill_root: Path,
    user_config_path: Path,
) -> Path:
    if accumulator.state_dir is None:
        return (skill_root / ".gskill").resolve(strict=False)

    candidate = Path(accumulator.state_dir).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)

    origin = accumulator.origins["state_dir"]
    if origin.source is ConfigSource.USER:
        return (user_config_path.parent / candidate).resolve(strict=False)
    return (skill_root / candidate).resolve(strict=False)


def _business_origins(
    preset: RunPreset,
    *,
    source: ConfigSource,
    source_path: Path | None,
) -> list[ValueOrigin]:
    rendered_source_path = str(source_path) if source_path is not None else None
    origins = [
        ValueOrigin(field=field_name, source=source, source_path=rendered_source_path)
        for field_name in (
            "inputs",
            "secret_inputs",
            "bindings",
            "breakpoints",
            "node_overrides",
            "compare_candidates",
            "artifact_requests",
        )
    ]
    origins.extend(
        ValueOrigin(
            field=f"inputs.{field_name}", source=source, source_path=rendered_source_path
        )
        for field_name in sorted(preset.inputs)
    )
    return origins


class ConfigResolver:
    """Own the single five-layer configuration precedence implementation."""

    def __init__(self, *, user_config_path: Path | None = None) -> None:
        self._user_config_path = (user_config_path or default_user_config_path()).expanduser().resolve(
            strict=False
        )

    @property
    def user_config_path(self) -> Path:
        return self._user_config_path

    def resolve(
        self,
        invocation: RunInvocation,
        *,
        portable_runtime: RuntimeProfileOverlay | None = None,
        portable_defaults: RunPreset | None = None,
    ) -> ConfigResolution:
        skill_root = Path(invocation.skill_root).expanduser().resolve(strict=True)
        if not skill_root.is_dir():
            raise _config_error(f"skill_root must be a directory: {skill_root}")

        project_config_path = skill_root / "gskill.toml"
        user_document = _load_user_config(self._user_config_path)
        project_document = _load_project_config(project_config_path)

        profile_accumulator = _ProfileAccumulator.defaults()
        profile_accumulator.apply(
            portable_runtime,
            source=ConfigSource.PORTABLE,
            source_path=None,
        )
        profile_accumulator.apply(
            user_document.runtime if user_document is not None else None,
            source=ConfigSource.USER,
            source_path=self._user_config_path if user_document is not None else None,
        )
        profile_accumulator.apply(
            project_document.runtime if project_document is not None else None,
            source=ConfigSource.PROJECT,
            source_path=project_config_path if project_document is not None else None,
        )
        profile_accumulator.apply(
            invocation.runtime,
            source=ConfigSource.INVOCATION,
            source_path=None,
        )

        state_root = _resolved_state_root(
            profile_accumulator,
            skill_root=skill_root,
            user_config_path=self._user_config_path,
        )
        profile = RuntimeProfile(
            executor=profile_accumulator.executor,
            checkpoint_store=profile_accumulator.checkpoint_store,
            state_dir=str(state_root),
            permissions=profile_accumulator.permissions,
            required_capabilities=profile_accumulator.required_capabilities,
            fallback_executors=profile_accumulator.fallback_executors,
        )
        resolved_profile = ResolvedRuntimeProfile(
            profile=profile,
            skill_root=str(skill_root),
            state_root=str(state_root),
            field_origins=tuple(
                profile_accumulator.origins[field_name]
                for field_name in sorted(profile_accumulator.origins)
            ),
        )

        selected_preset: RunPreset
        business_source: ConfigSource
        business_source_path: Path | None
        if invocation.preset_id is not None:
            if project_document is None or invocation.preset_id not in project_document.presets:
                raise _config_error(
                    f"unknown preset '{invocation.preset_id}'",
                    source_path=project_config_path,
                )
            selected_preset = project_document.presets[invocation.preset_id].to_preset(
                invocation.preset_id
            )
            business_source = ConfigSource.PRESET
            business_source_path = project_config_path
        elif portable_defaults is not None:
            selected_preset = portable_defaults
            business_source = ConfigSource.PORTABLE
            business_source_path = None
        else:
            selected_preset = RunPreset(preset_id="defaults")
            business_source = ConfigSource.DEFAULT
            business_source_path = None

        inputs = selected_preset.inputs if invocation.inputs is None else invocation.inputs
        secret_inputs = (
            selected_preset.secret_inputs
            if invocation.secret_inputs is None
            else invocation.secret_inputs
        )
        bindings = selected_preset.bindings if invocation.bindings is None else invocation.bindings
        breakpoints = (
            selected_preset.breakpoints
            if invocation.breakpoints is None
            else invocation.breakpoints
        )
        node_overrides = (
            selected_preset.node_overrides
            if invocation.node_overrides is None
            else invocation.node_overrides
        )
        compare_candidates = (
            selected_preset.compare_candidates
            if invocation.compare_candidates is None
            else invocation.compare_candidates
        )
        artifact_requests = (
            selected_preset.artifact_requests
            if invocation.artifact_requests is None
            else invocation.artifact_requests
        )

        origins = _business_origins(
            selected_preset,
            source=business_source,
            source_path=business_source_path,
        )
        invocation_fields: tuple[tuple[str, object | None], ...] = (
            ("inputs", invocation.inputs),
            ("secret_inputs", invocation.secret_inputs),
            ("bindings", invocation.bindings),
            ("breakpoints", invocation.breakpoints),
            ("node_overrides", invocation.node_overrides),
            ("compare_candidates", invocation.compare_candidates),
            ("artifact_requests", invocation.artifact_requests),
        )
        overridden_names = {field_name for field_name, value in invocation_fields if value is not None}
        origins = [origin for origin in origins if origin.field.split(".", 1)[0] not in overridden_names]
        for field_name in sorted(overridden_names):
            origins.append(ValueOrigin(field=field_name, source=ConfigSource.INVOCATION))
        if invocation.inputs is not None:
            origins.extend(
                ValueOrigin(field=f"inputs.{field_name}", source=ConfigSource.INVOCATION)
                for field_name in sorted(invocation.inputs)
            )

        run_id = invocation.run_id or str(uuid.uuid4())
        origins.append(
            ValueOrigin(
                field="run_id",
                source=ConfigSource.INVOCATION
                if invocation.run_id is not None
                else ConfigSource.DEFAULT,
            )
        )
        request = RunRequest(
            run_id=run_id,
            preset_id=invocation.preset_id,
            profile=resolved_profile,
            inputs=dict(inputs),
            secret_inputs=tuple(secret_inputs),
            bindings=tuple(bindings),
            breakpoints=tuple(breakpoints),
            node_overrides=tuple(node_overrides),
            compare_candidates=tuple(compare_candidates),
            artifact_requests=tuple(artifact_requests),
            value_origins=tuple(sorted(origins, key=lambda item: item.field)),
        )
        return ConfigResolution(profile=resolved_profile, request=request)
