"""Explicit, manifest-owned installation of optional host integration assets."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from graph_skill_runtime.application.config import default_user_config_path
from graph_skill_runtime.domain.models import JsonObject
from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets
from graph_skill_runtime.integrations.models import (
    HostDetection,
    IntegrationAction,
    IntegrationChange,
    IntegrationConflict,
    IntegrationOperation,
    IntegrationPlan,
    IntegrationRequest,
    IntegrationResourceKind,
    IntegrationResult,
    IntegrationScope,
    IntegrationTarget,
)
from graph_skill_runtime.integrations.renderers import renderer_for
from graph_skill_runtime.ports.integrations import (
    FileProjection,
    IntegrationAssetBundle,
    JsonEntryProjection,
    ProjectionContext,
    ProjectionResource,
    TextBlockProjection,
)

_MAX_CONFIG_BYTES = 4 * 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_EXECUTABLES: Mapping[IntegrationTarget, str] = {
    IntegrationTarget.CLAUDE: "claude",
    IntegrationTarget.CODEX: "codex",
    IntegrationTarget.COPILOT: "copilot",
    IntegrationTarget.CURSOR: "cursor-agent",
    IntegrationTarget.GEMINI: "gemini",
    IntegrationTarget.OPENCODE: "opencode",
}


class _ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: str = Field(min_length=1)
    resource_kind: IntegrationResourceKind
    path: str = Field(min_length=1)
    selector: tuple[str, ...] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    container_created: bool = False
    created_json_parents: tuple[tuple[str, ...], ...] = ()


class _InstallManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.install-manifest.v1"]
    integration_id: Literal["moirai"]
    asset_version: str = Field(min_length=1)
    target: IntegrationTarget
    scope: IntegrationScope
    entries: tuple[_ManifestEntry, ...]

    @model_validator(mode="after")
    def _unique_resources(self) -> Self:
        resource_ids = [entry.resource_id for entry in self.entries]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("manifest resource ids must be unique")
        return self


@dataclass(frozen=True)
class _Mutation:
    target: IntegrationTarget
    resource_id: str
    resource_kind: IntegrationResourceKind
    path: Path
    selector: tuple[str, ...]
    action: IntegrationAction
    content_sha256: str | None
    before: bytes | None
    after: bytes | None
    manifest_entry: _ManifestEntry | None

    def public(self) -> IntegrationChange:
        return IntegrationChange(
            target=self.target,
            resource_id=self.resource_id,
            resource_kind=self.resource_kind,
            action=self.action,
            path=str(self.path),
            selector=self.selector,
            content_sha256=self.content_sha256,
        )


@dataclass(frozen=True)
class _PreparedTarget:
    target: IntegrationTarget
    manifest_path: Path
    manifest_before: bytes | None
    manifest_after: bytes | None
    mutations: tuple[_Mutation, ...]


@dataclass(frozen=True)
class _PreparedOperation:
    plan: IntegrationPlan
    targets: tuple[_PreparedTarget, ...]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json(value: JsonValue) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    document: JsonObject = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _read_bounded(path: Path, *, limit: int) -> bytes | None:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError(f"cannot inspect {path}: {exc}") from exc
    if not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    if size > limit:
        raise ValueError(f"file exceeds the {limit}-byte safety limit: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _decode_json_document(content: bytes | None, *, path: Path) -> JsonObject:
    if content is None:
        return {}
    try:
        parsed = json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"shared JSON config is invalid: {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"shared JSON config must contain an object: {path}")
    return cast(JsonObject, parsed)


def _lookup_json(document: JsonObject, selector: tuple[str, ...]) -> tuple[bool, JsonValue | None]:
    current: JsonValue = document
    for key in selector:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _set_json(document: JsonObject, selector: tuple[str, ...], value: JsonValue) -> None:
    if not selector:
        raise ValueError("JSON entry selector cannot be empty")
    current: JsonObject = document
    for key in selector[:-1]:
        child = current.get(key)
        if child is None:
            nested: JsonObject = {}
            current[key] = nested
            current = nested
            continue
        if not isinstance(child, dict):
            raise ValueError(f"JSON selector parent {key!r} is not an object")
        current = child
    current[selector[-1]] = value


def _remove_json(document: JsonObject, selector: tuple[str, ...]) -> None:
    if not selector:
        raise ValueError("JSON entry selector cannot be empty")
    current: JsonObject = document
    for key in selector[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            return
        current = child
    current.pop(selector[-1], None)


def _missing_json_parents(
    document: JsonObject,
    selector: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    current: JsonObject = document
    prefix: list[str] = []
    missing: list[tuple[str, ...]] = []
    for key in selector[:-1]:
        prefix.append(key)
        child = current.get(key)
        if child is None:
            missing.append(tuple(prefix))
            current = {}
            continue
        if not isinstance(child, dict):
            raise ValueError(f"JSON selector parent {key!r} is not an object")
        current = child
    return tuple(missing)


def _prune_created_json_parents(
    document: JsonObject,
    created_parents: tuple[tuple[str, ...], ...],
) -> None:
    for selector in sorted(created_parents, key=len, reverse=True):
        if not selector:
            continue
        parent: JsonObject = document
        valid = True
        for key in selector[:-1]:
            child = parent.get(key)
            if not isinstance(child, dict):
                valid = False
                break
            parent = child
        if valid and parent.get(selector[-1]) == {}:
            parent.pop(selector[-1], None)


def _marker_bounds(content: bytes, marker: str) -> tuple[int, int] | None:
    begin = f"# >>> {marker} >>>".encode()
    end = f"# <<< {marker} <<<".encode()
    begin_index = content.find(begin)
    end_index = content.find(end)
    if begin_index < 0 and end_index < 0:
        return None
    if begin_index < 0 or end_index < begin_index:
        raise ValueError(f"managed block markers are incomplete: {marker}")
    if content.find(begin, begin_index + 1) >= 0 or content.find(end, end_index + 1) >= 0:
        raise ValueError(f"managed block markers are duplicated: {marker}")
    block_end = end_index + len(end)
    if content[block_end : block_end + 2] == b"\r\n":
        block_end += 2
    elif content[block_end : block_end + 1] in {b"\n", b"\r"}:
        block_end += 1
    return begin_index, block_end


def _append_text_block(content: bytes | None, block: bytes) -> bytes:
    if content is None or not content:
        return block
    separator = b"" if content.endswith((b"\n\n", b"\r\n\r\n")) else b"\n"
    if not content.endswith((b"\n", b"\r")):
        separator = b"\n\n"
    return content + separator + block


def _remove_text_block(content: bytes, bounds: tuple[int, int]) -> bytes:
    start, end = bounds
    if start > 0 and content[start - 2 : start] == b"\r\n":
        start -= 2
    elif start > 0 and content[start - 1 : start] in {b"\n", b"\r"}:
        start -= 1
    return content[:start] + content[end:]


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


def _manifest_bytes(manifest: _InstallManifest) -> bytes:
    return (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prior_mode: int | None = None
    try:
        prior_mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        pass
    handle = tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if prior_mode is not None:
            temporary.chmod(prior_mode)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class IntegrationInstaller:
    """Plan and apply safe projections; construction and detection are read-only."""

    def __init__(
        self,
        *,
        assets: IntegrationAssetBundle | None = None,
        home: Path | None = None,
        user_state_root: Path | None = None,
        python_executable: Path | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._assets = assets or PackagedMoiraiAssets()
        self._home = (home or Path.home()).expanduser().resolve(strict=False)
        self._user_state_root = (
            user_state_root or default_user_config_path().parent
        ).expanduser().resolve(strict=False)
        self._python_executable = (
            python_executable or Path(sys.executable)
        ).expanduser().resolve(strict=False)
        self._which = which

    def detect_hosts(self) -> tuple[HostDetection, ...]:
        """Probe PATH without writing host state or invoking a vendor process."""

        detections: list[HostDetection] = []
        for target in IntegrationTarget:
            executable_name = _EXECUTABLES[target]
            found = self._which(executable_name)
            detections.append(
                HostDetection(
                    target=target,
                    detected=found is not None,
                    executable=found,
                    evidence=(
                        f"found {executable_name!r} on PATH"
                        if found is not None
                        else f"{executable_name!r} is not on PATH"
                    ),
                )
            )
        return tuple(detections)

    def detected_targets(self) -> tuple[IntegrationTarget, ...]:
        return tuple(item.target for item in self.detect_hosts() if item.detected)

    def plan_install(self, request: IntegrationRequest) -> IntegrationPlan:
        return self._prepare_install(request).plan

    def install(self, request: IntegrationRequest) -> IntegrationResult:
        prepared = self._prepare_install(request)
        if not prepared.plan.can_apply:
            return IntegrationResult(
                status="conflict",
                plan=prepared.plan,
                applied_changes=0,
            )
        applied, changed = self._apply(prepared)
        return IntegrationResult(
            status="installed" if changed else "unchanged",
            plan=prepared.plan,
            applied_changes=applied,
        )

    def plan_uninstall(self, request: IntegrationRequest) -> IntegrationPlan:
        return self._prepare_uninstall(request).plan

    def uninstall(self, request: IntegrationRequest) -> IntegrationResult:
        prepared = self._prepare_uninstall(request)
        if not prepared.plan.can_apply:
            return IntegrationResult(
                status="conflict",
                plan=prepared.plan,
                applied_changes=0,
            )
        had_manifest = any(target.manifest_before is not None for target in prepared.targets)
        applied, _changed = self._apply(prepared)
        return IntegrationResult(
            status="uninstalled" if had_manifest else "unchanged",
            plan=prepared.plan,
            applied_changes=applied,
        )

    def _context(self, request: IntegrationRequest) -> ProjectionContext:
        project_root = (
            Path(request.project_root).expanduser().resolve(strict=False)
            if request.project_root is not None
            else None
        )
        if project_root is not None and (not project_root.exists() or not project_root.is_dir()):
            raise ValueError(f"project_root must be an existing directory: {project_root}")
        return ProjectionContext(
            scope=request.scope,
            home=self._home,
            project_root=project_root,
            python_executable=self._python_executable,
        )

    def _manifest_path(
        self,
        request: IntegrationRequest,
        context: ProjectionContext,
        target: IntegrationTarget,
    ) -> Path:
        state_root = (
            self._user_state_root
            if request.scope is IntegrationScope.USER
            else _project_root_for_manifest(context) / ".gskill"
        )
        return (
            state_root
            / "integrations"
            / request.integration_id
            / target.value
            / "install-manifest.json"
        ).resolve(strict=False)

    def _validated_resources(
        self,
        target: IntegrationTarget,
        context: ProjectionContext,
    ) -> tuple[ProjectionResource, ...]:
        renderer = renderer_for(target)
        resources = renderer.render(self._assets, context)
        file_roots = tuple(root.resolve(strict=False) for root in renderer.allowed_file_roots(context))
        config_paths = {
            path.resolve(strict=False) for path in renderer.allowed_config_paths(context)
        }
        resource_ids: set[str] = set()
        resource_paths: set[tuple[Path, tuple[str, ...]]] = set()
        validated: list[ProjectionResource] = []
        for resource in resources:
            path = resource.path.resolve(strict=False)
            selector: tuple[str, ...] = ()
            if isinstance(resource, FileProjection):
                if not _inside(path, file_roots):
                    raise ValueError(f"renderer projected a file outside its owned roots: {path}")
                projected: ProjectionResource = FileProjection(
                    resource_id=resource.resource_id,
                    path=path,
                    content=resource.content,
                )
            elif isinstance(resource, JsonEntryProjection):
                if path not in config_paths:
                    raise ValueError(f"renderer projected an unowned JSON config path: {path}")
                selector = resource.selector
                projected = JsonEntryProjection(
                    resource_id=resource.resource_id,
                    path=path,
                    selector=selector,
                    value=resource.value,
                )
            else:
                if path not in config_paths:
                    raise ValueError(f"renderer projected an unowned text config path: {path}")
                selector = (resource.marker,)
                projected = TextBlockProjection(
                    resource_id=resource.resource_id,
                    path=path,
                    marker=resource.marker,
                    content=resource.content,
                )
            if projected.resource_id in resource_ids:
                raise ValueError(f"renderer duplicated resource id: {projected.resource_id}")
            address = (path, selector)
            if address in resource_paths:
                raise ValueError(f"renderer duplicated target address: {path} {selector}")
            resource_ids.add(projected.resource_id)
            resource_paths.add(address)
            validated.append(projected)
        return tuple(validated)

    def _read_manifest(
        self,
        path: Path,
    ) -> tuple[bytes | None, _InstallManifest | None, str | None]:
        try:
            content = _read_bounded(path, limit=_MAX_MANIFEST_BYTES)
            if content is None:
                return None, None, None
            parsed = json.loads(
                content.decode("utf-8-sig"),
                object_pairs_hook=_unique_object,
            )
            manifest = _InstallManifest.model_validate(parsed)
            return content, manifest, None
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
            return None, None, str(exc)

    def _validate_manifest(
        self,
        *,
        manifest: _InstallManifest,
        request: IntegrationRequest,
        target: IntegrationTarget,
        resources: tuple[ProjectionResource, ...],
    ) -> str | None:
        if manifest.integration_id != request.integration_id:
            return "manifest integration id does not match the requested integration"
        if manifest.target is not target or manifest.scope is not request.scope:
            return "manifest target or scope does not match the requested projection"
        by_id = {entry.resource_id: entry for entry in manifest.entries}
        expected_ids = {resource.resource_id for resource in resources}
        if set(by_id) != expected_ids:
            return "manifest resource inventory differs from the canonical renderer; uninstall first"
        for resource in resources:
            entry = by_id[resource.resource_id]
            expected_kind, expected_selector = _resource_identity(resource)
            if entry.resource_kind is not expected_kind:
                return f"manifest kind changed for {entry.resource_id}"
            if Path(entry.path).resolve(strict=False) != resource.path.resolve(strict=False):
                return f"manifest path changed for {entry.resource_id}"
            if entry.selector != expected_selector:
                return f"manifest selector changed for {entry.resource_id}"
        return None

    def _prepare_install(self, request: IntegrationRequest) -> _PreparedOperation:
        context = self._context(request)
        conflicts: list[IntegrationConflict] = []
        prepared_targets: list[_PreparedTarget] = []
        for target in request.targets:
            resources = self._validated_resources(target, context)
            manifest_path = self._manifest_path(request, context, target)
            manifest_before, manifest, manifest_error = self._read_manifest(manifest_path)
            if manifest_error is not None:
                conflicts.append(
                    IntegrationConflict(
                        target=target,
                        resource_id="manifest",
                        path=str(manifest_path),
                        reason=manifest_error,
                    )
                )
                prepared_targets.append(
                    _PreparedTarget(target, manifest_path, manifest_before, None, ())
                )
                continue
            if manifest is not None:
                mismatch = self._validate_manifest(
                    manifest=manifest,
                    request=request,
                    target=target,
                    resources=resources,
                )
                if mismatch is not None:
                    conflicts.append(
                        IntegrationConflict(
                            target=target,
                            resource_id="manifest",
                            path=str(manifest_path),
                            reason=mismatch,
                        )
                    )
                    prepared_targets.append(
                        _PreparedTarget(target, manifest_path, manifest_before, None, ())
                    )
                    continue
            owned = {entry.resource_id: entry for entry in manifest.entries} if manifest else {}
            mutations: list[_Mutation] = []
            entries: list[_ManifestEntry] = []
            for resource in resources:
                entry = owned.get(resource.resource_id)
                try:
                    mutation = self._plan_install_resource(target, resource, entry)
                except ValueError as exc:
                    kind, selector = _resource_identity(resource)
                    conflicts.append(
                        IntegrationConflict(
                            target=target,
                            resource_id=resource.resource_id,
                            path=str(resource.path),
                            reason=str(exc),
                        )
                    )
                    mutation = _Mutation(
                        target=target,
                        resource_id=resource.resource_id,
                        resource_kind=kind,
                        path=resource.path,
                        selector=selector,
                        action=IntegrationAction.UNCHANGED,
                        content_sha256=None,
                        before=None,
                        after=None,
                        manifest_entry=None,
                    )
                mutations.append(mutation)
                if mutation.manifest_entry is not None:
                    entries.append(mutation.manifest_entry)
            manifest_after: bytes | None = None
            if len(entries) == len(resources):
                manifest_after = _manifest_bytes(
                    _InstallManifest(
                        schema_version="gskill.install-manifest.v1",
                        integration_id="moirai",
                        asset_version=self._assets.asset_version,
                        target=target,
                        scope=request.scope,
                        entries=tuple(entries),
                    )
                )
            prepared_targets.append(
                _PreparedTarget(
                    target=target,
                    manifest_path=manifest_path,
                    manifest_before=manifest_before,
                    manifest_after=manifest_after,
                    mutations=tuple(mutations),
                )
            )
        return self._prepared_operation(
            operation=IntegrationOperation.INSTALL,
            request=request,
            targets=tuple(prepared_targets),
            conflicts=tuple(conflicts),
        )

    def _plan_install_resource(
        self,
        target: IntegrationTarget,
        resource: ProjectionResource,
        owned: _ManifestEntry | None,
    ) -> _Mutation:
        if isinstance(resource, FileProjection):
            return self._plan_install_file(target, resource, owned)
        if isinstance(resource, JsonEntryProjection):
            return self._plan_install_json(target, resource, owned)
        return self._plan_install_text(target, resource, owned)

    def _plan_install_file(
        self,
        target: IntegrationTarget,
        resource: FileProjection,
        owned: _ManifestEntry | None,
    ) -> _Mutation:
        before = _read_bounded(resource.path, limit=_MAX_CONFIG_BYTES)
        desired_hash = _sha256(resource.content)
        if owned is None and before is not None:
            raise ValueError("target file already exists and is not owned by this integration")
        if owned is not None and before is not None and _sha256(before) != owned.content_sha256:
            raise ValueError("owned target file was modified; preserving the user's content")
        action = (
            IntegrationAction.CREATE
            if before is None
            else IntegrationAction.UNCHANGED
            if before == resource.content
            else IntegrationAction.UPDATE
        )
        entry = _ManifestEntry(
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.FILE,
            path=str(resource.path),
            content_sha256=desired_hash,
        )
        return _Mutation(
            target=target,
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.FILE,
            path=resource.path,
            selector=(),
            action=action,
            content_sha256=desired_hash,
            before=before,
            after=resource.content,
            manifest_entry=entry,
        )

    def _plan_install_json(
        self,
        target: IntegrationTarget,
        resource: JsonEntryProjection,
        owned: _ManifestEntry | None,
    ) -> _Mutation:
        if (
            target is IntegrationTarget.OPENCODE
            and resource.path.with_suffix(".jsonc").exists()
        ):
            raise ValueError(
                "OpenCode JSONC config already exists; the installer will not rewrite or shadow it"
            )
        before = _read_bounded(resource.path, limit=_MAX_CONFIG_BYTES)
        document = _decode_json_document(before, path=resource.path)
        exists, current = _lookup_json(document, resource.selector)
        created_parents = (
            owned.created_json_parents
            if owned is not None
            else _missing_json_parents(document, resource.selector)
        )
        desired_hash = _sha256(_canonical_json(resource.value))
        if owned is None and exists:
            raise ValueError("shared config entry already exists and is not owned by this integration")
        if owned is not None and exists:
            current_hash = _sha256(_canonical_json(current))
            if current_hash != owned.content_sha256:
                raise ValueError("owned shared config entry was modified; preserving the user's value")
            if current_hash == desired_hash:
                after = before
                action = IntegrationAction.UNCHANGED
                entry = _ManifestEntry(
                    resource_id=resource.resource_id,
                    resource_kind=IntegrationResourceKind.JSON_ENTRY,
                    path=str(resource.path),
                    selector=resource.selector,
                    content_sha256=desired_hash,
                    container_created=owned.container_created,
                    created_json_parents=created_parents,
                )
                return _Mutation(
                    target=target,
                    resource_id=resource.resource_id,
                    resource_kind=IntegrationResourceKind.JSON_ENTRY,
                    path=resource.path,
                    selector=resource.selector,
                    action=action,
                    content_sha256=desired_hash,
                    before=before,
                    after=after,
                    manifest_entry=entry,
                )
        _set_json(document, resource.selector, resource.value)
        after = _pretty_json(document)
        action = (
            IntegrationAction.CREATE
            if not exists
            else IntegrationAction.UNCHANGED
            if before == after
            else IntegrationAction.UPDATE
        )
        entry = _ManifestEntry(
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.JSON_ENTRY,
            path=str(resource.path),
            selector=resource.selector,
            content_sha256=desired_hash,
            container_created=owned.container_created if owned is not None else before is None,
            created_json_parents=created_parents,
        )
        return _Mutation(
            target=target,
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.JSON_ENTRY,
            path=resource.path,
            selector=resource.selector,
            action=action,
            content_sha256=desired_hash,
            before=before,
            after=after,
            manifest_entry=entry,
        )

    def _plan_install_text(
        self,
        target: IntegrationTarget,
        resource: TextBlockProjection,
        owned: _ManifestEntry | None,
    ) -> _Mutation:
        before = _read_bounded(resource.path, limit=_MAX_CONFIG_BYTES)
        raw = before or b""
        try:
            if before is not None:
                tomllib.loads(before.decode("utf-8-sig"))
            bounds = _marker_bounds(raw, resource.marker)
        except (UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
            raise ValueError(f"shared TOML config is invalid: {resource.path}: {exc}") from exc
        block_hash = _sha256(resource.content)
        if owned is None and bounds is not None:
            raise ValueError("managed block already exists without an ownership manifest")
        if bounds is None and _toml_has_gskill_server(raw):
            raise ValueError("mcp_servers.gskill already exists and is not owned by this integration")
        if owned is not None and bounds is not None:
            current_block = raw[bounds[0] : bounds[1]]
            if _sha256(current_block) != owned.content_sha256:
                raise ValueError("owned TOML block was modified; preserving the user's content")
        if bounds is None:
            after = _append_text_block(before, resource.content)
            action = IntegrationAction.CREATE
        else:
            after = raw[: bounds[0]] + resource.content + raw[bounds[1] :]
            action = IntegrationAction.UNCHANGED if after == before else IntegrationAction.UPDATE
        entry = _ManifestEntry(
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.TEXT_BLOCK,
            path=str(resource.path),
            selector=(resource.marker,),
            content_sha256=block_hash,
            container_created=owned.container_created if owned is not None else before is None,
        )
        return _Mutation(
            target=target,
            resource_id=resource.resource_id,
            resource_kind=IntegrationResourceKind.TEXT_BLOCK,
            path=resource.path,
            selector=(resource.marker,),
            action=action,
            content_sha256=block_hash,
            before=before,
            after=after,
            manifest_entry=entry,
        )

    def _prepare_uninstall(self, request: IntegrationRequest) -> _PreparedOperation:
        context = self._context(request)
        conflicts: list[IntegrationConflict] = []
        prepared_targets: list[_PreparedTarget] = []
        for target in request.targets:
            resources = self._validated_resources(target, context)
            manifest_path = self._manifest_path(request, context, target)
            manifest_before, manifest, manifest_error = self._read_manifest(manifest_path)
            if manifest_error is not None:
                conflicts.append(
                    IntegrationConflict(
                        target=target,
                        resource_id="manifest",
                        path=str(manifest_path),
                        reason=manifest_error,
                    )
                )
                prepared_targets.append(
                    _PreparedTarget(target, manifest_path, manifest_before, None, ())
                )
                continue
            if manifest is None:
                prepared_targets.append(
                    _PreparedTarget(target, manifest_path, None, None, ())
                )
                continue
            mismatch = self._validate_manifest(
                manifest=manifest,
                request=request,
                target=target,
                resources=resources,
            )
            if mismatch is not None:
                conflicts.append(
                    IntegrationConflict(
                        target=target,
                        resource_id="manifest",
                        path=str(manifest_path),
                        reason=mismatch,
                    )
                )
                prepared_targets.append(
                    _PreparedTarget(target, manifest_path, manifest_before, None, ())
                )
                continue
            mutations: list[_Mutation] = []
            for entry in manifest.entries:
                try:
                    mutations.append(self._plan_uninstall_entry(target, entry))
                except ValueError as exc:
                    conflicts.append(
                        IntegrationConflict(
                            target=target,
                            resource_id=entry.resource_id,
                            path=entry.path,
                            reason=str(exc),
                        )
                    )
            prepared_targets.append(
                _PreparedTarget(
                    target=target,
                    manifest_path=manifest_path,
                    manifest_before=manifest_before,
                    manifest_after=None,
                    mutations=tuple(mutations),
                )
            )
        return self._prepared_operation(
            operation=IntegrationOperation.UNINSTALL,
            request=request,
            targets=tuple(prepared_targets),
            conflicts=tuple(conflicts),
        )

    def _plan_uninstall_entry(
        self,
        target: IntegrationTarget,
        entry: _ManifestEntry,
    ) -> _Mutation:
        path = Path(entry.path).resolve(strict=False)
        before = _read_bounded(path, limit=_MAX_CONFIG_BYTES)
        if entry.resource_kind is IntegrationResourceKind.FILE:
            action, after = self._uninstall_file_state(entry, before)
        elif entry.resource_kind is IntegrationResourceKind.JSON_ENTRY:
            action, after = self._uninstall_json_state(entry, path, before)
        else:
            action, after = self._uninstall_text_state(entry, before)
        return _Mutation(
            target=target,
            resource_id=entry.resource_id,
            resource_kind=entry.resource_kind,
            path=path,
            selector=entry.selector,
            action=action,
            content_sha256=entry.content_sha256,
            before=before,
            after=after,
            manifest_entry=None,
        )

    @staticmethod
    def _uninstall_file_state(
        entry: _ManifestEntry,
        before: bytes | None,
    ) -> tuple[IntegrationAction, bytes | None]:
        if before is None:
            return IntegrationAction.UNCHANGED, None
        if _sha256(before) != entry.content_sha256:
            raise ValueError("owned target file was modified; uninstall will not delete it")
        return IntegrationAction.REMOVE, None

    @staticmethod
    def _uninstall_json_state(
        entry: _ManifestEntry,
        path: Path,
        before: bytes | None,
    ) -> tuple[IntegrationAction, bytes | None]:
        if before is None:
            return IntegrationAction.UNCHANGED, None
        document = _decode_json_document(before, path=path)
        exists, current = _lookup_json(document, entry.selector)
        if not exists:
            return IntegrationAction.UNCHANGED, before
        if _sha256(_canonical_json(current)) != entry.content_sha256:
            raise ValueError("owned shared config entry was modified; uninstall will preserve it")
        _remove_json(document, entry.selector)
        _prune_created_json_parents(document, entry.created_json_parents)
        if entry.container_created and not document:
            return IntegrationAction.REMOVE, None
        return IntegrationAction.REMOVE, _pretty_json(document)

    @staticmethod
    def _uninstall_text_state(
        entry: _ManifestEntry,
        before: bytes | None,
    ) -> tuple[IntegrationAction, bytes | None]:
        if before is None:
            return IntegrationAction.UNCHANGED, None
        marker = entry.selector[0] if entry.selector else ""
        bounds = _marker_bounds(before, marker)
        if bounds is None:
            return IntegrationAction.UNCHANGED, before
        current_block = before[bounds[0] : bounds[1]]
        if _sha256(current_block) != entry.content_sha256:
            raise ValueError("owned TOML block was modified; uninstall will preserve it")
        remaining = _remove_text_block(before, bounds)
        after = None if entry.container_created and not remaining.strip() else remaining
        return IntegrationAction.REMOVE, after

    def _prepared_operation(
        self,
        *,
        operation: IntegrationOperation,
        request: IntegrationRequest,
        targets: tuple[_PreparedTarget, ...],
        conflicts: tuple[IntegrationConflict, ...],
    ) -> _PreparedOperation:
        changes = tuple(mutation.public() for target in targets for mutation in target.mutations)
        plan = IntegrationPlan(
            operation=operation,
            integration_id=request.integration_id,
            asset_version=self._assets.asset_version,
            scope=request.scope,
            targets=request.targets,
            changes=changes,
            conflicts=conflicts,
            can_apply=not conflicts,
        )
        return _PreparedOperation(plan=plan, targets=targets)

    def _apply(self, prepared: _PreparedOperation) -> tuple[int, bool]:
        changed_mutations = [
            mutation
            for target in prepared.targets
            for mutation in target.mutations
            if mutation.action is not IntegrationAction.UNCHANGED
        ]
        affected: dict[Path, bytes | None] = {}
        for target in prepared.targets:
            affected[target.manifest_path] = target.manifest_before
            for mutation in target.mutations:
                affected[mutation.path] = mutation.before
        created_directories = self._missing_parent_directories(tuple(affected))
        touched: list[tuple[Path, bytes | None, bytes | None]] = []
        try:
            for mutation in changed_mutations:
                self._assert_unchanged(mutation.path, mutation.before)
                self._write_or_remove(mutation.path, mutation.after)
                touched.append((mutation.path, mutation.before, mutation.after))
            for target in prepared.targets:
                self._assert_unchanged(target.manifest_path, target.manifest_before)
                if target.manifest_after == target.manifest_before:
                    continue
                self._write_or_remove(target.manifest_path, target.manifest_after)
                touched.append(
                    (target.manifest_path, target.manifest_before, target.manifest_after)
                )
        except Exception as exc:
            rollback_failures = self._restore(tuple(touched))
            self._remove_empty_directories(created_directories)
            if rollback_failures:
                raise RuntimeError(
                    "integration operation failed and rollback was incomplete: "
                    + "; ".join(rollback_failures)
                ) from exc
            raise
        return len(changed_mutations), bool(touched)

    @staticmethod
    def _assert_unchanged(path: Path, expected: bytes | None) -> None:
        current = _read_bounded(path, limit=_MAX_CONFIG_BYTES)
        if current != expected:
            raise ValueError(f"target changed after planning; operation aborted: {path}")

    @staticmethod
    def _write_or_remove(path: Path, content: bytes | None) -> None:
        if content is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return
        _atomic_write(path, content)

    @staticmethod
    def _missing_parent_directories(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        missing: set[Path] = set()
        for path in paths:
            parent = path.parent
            while not parent.exists():
                missing.add(parent)
                if parent == parent.parent:
                    break
                parent = parent.parent
        return tuple(sorted(missing, key=lambda item: len(item.parts), reverse=True))

    @staticmethod
    def _restore(
        touched: tuple[tuple[Path, bytes | None, bytes | None], ...],
    ) -> tuple[str, ...]:
        failures: list[str] = []
        for path, before, written in reversed(touched):
            try:
                current = _read_bounded(path, limit=_MAX_CONFIG_BYTES)
                if current != written:
                    failures.append(f"{path}: changed concurrently after integration write")
                    continue
                IntegrationInstaller._write_or_remove(path, before)
            except (OSError, ValueError) as exc:
                failures.append(f"{path}: {exc}")
        return tuple(failures)

    @staticmethod
    def _remove_empty_directories(paths: tuple[Path, ...]) -> None:
        for directory in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
            except (FileNotFoundError, OSError):
                continue


def _project_root_for_manifest(context: ProjectionContext) -> Path:
    if context.project_root is None:
        raise ValueError("project_root is required for project scope")
    return context.project_root


def _resource_identity(
    resource: ProjectionResource,
) -> tuple[IntegrationResourceKind, tuple[str, ...]]:
    if isinstance(resource, FileProjection):
        return IntegrationResourceKind.FILE, ()
    if isinstance(resource, JsonEntryProjection):
        return IntegrationResourceKind.JSON_ENTRY, resource.selector
    return IntegrationResourceKind.TEXT_BLOCK, (resource.marker,)


def _toml_has_gskill_server(content: bytes) -> bool:
    if not content:
        return False
    try:
        document = tomllib.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc
    servers = document.get("mcp_servers")
    if servers is None:
        return False
    if not isinstance(servers, dict):
        raise ValueError("mcp_servers must be a TOML table")
    return _MCP_SERVER_NAME_FOR_INSTALLER in servers


_MCP_SERVER_NAME_FOR_INSTALLER = "gskill"


__all__ = ["IntegrationInstaller"]
