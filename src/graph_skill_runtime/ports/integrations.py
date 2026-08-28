"""Provider-neutral projection contracts for optional host integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias

from graph_skill_runtime.domain.models import JsonObject
from graph_skill_runtime.integrations.models import IntegrationScope, IntegrationTarget


@dataclass(frozen=True)
class ProjectionContext:
    """Resolved local roots and launcher used by one host renderer."""

    scope: IntegrationScope
    home: Path
    project_root: Path | None
    python_executable: Path


@dataclass(frozen=True)
class FileProjection:
    """A complete file whose bytes are owned by the integration manifest."""

    resource_id: str
    path: Path
    content: bytes


@dataclass(frozen=True)
class JsonEntryProjection:
    """One owned entry inside a shared JSON configuration document."""

    resource_id: str
    path: Path
    selector: tuple[str, ...]
    value: JsonObject


@dataclass(frozen=True)
class TextBlockProjection:
    """One marker-delimited block inside a shared text configuration file."""

    resource_id: str
    path: Path
    marker: str
    content: bytes


ProjectionResource: TypeAlias = FileProjection | JsonEntryProjection | TextBlockProjection


class IntegrationAssetBundle(Protocol):
    """Read-only canonical asset source consumed by host renderers."""

    @property
    def integration_id(self) -> str: ...

    @property
    def asset_version(self) -> str: ...

    def skill_ids(self) -> tuple[str, ...]: ...

    def role_ids(self) -> tuple[str, ...]: ...

    def role_host_name(self, role_id: str) -> str: ...

    def role_description(self, role_id: str) -> str: ...

    def role_skill_ids(self, role_id: str) -> tuple[str, ...]: ...

    def role_body(self, role_id: str) -> str: ...

    def skill_file(self, skill_id: str) -> bytes: ...

    def skill_reference_files(self, skill_id: str) -> tuple[tuple[str, bytes], ...]: ...


class HostIntegrationRenderer(Protocol):
    """Adapter boundary for one host's native discovery and MCP formats."""

    @property
    def target(self) -> IntegrationTarget: ...

    def render(
        self,
        assets: IntegrationAssetBundle,
        context: ProjectionContext,
    ) -> tuple[ProjectionResource, ...]: ...

    def allowed_file_roots(self, context: ProjectionContext) -> tuple[Path, ...]: ...

    def allowed_config_paths(self, context: ProjectionContext) -> tuple[Path, ...]: ...


__all__ = [
    "FileProjection",
    "HostIntegrationRenderer",
    "IntegrationAssetBundle",
    "JsonEntryProjection",
    "ProjectionContext",
    "ProjectionResource",
    "TextBlockProjection",
]
