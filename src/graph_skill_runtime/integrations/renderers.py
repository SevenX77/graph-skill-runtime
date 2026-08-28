"""Six host-native renderers over one canonical MoirAI asset bundle."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from graph_skill_runtime.domain.models import JsonObject
from graph_skill_runtime.integrations.models import IntegrationScope, IntegrationTarget
from graph_skill_runtime.ports.integrations import (
    FileProjection,
    HostIntegrationRenderer,
    IntegrationAssetBundle,
    JsonEntryProjection,
    ProjectionContext,
    ProjectionResource,
    TextBlockProjection,
)

_MCP_RESOURCE_ID = "mcp:gskill"
_MCP_SERVER_NAME = "gskill"


@dataclass(frozen=True)
class _HostLayout:
    skill_root: Path
    agent_root: Path
    config_path: Path


def _project_root(context: ProjectionContext) -> Path:
    if context.project_root is None:
        raise ValueError("project_root is required for a project integration projection")
    return context.project_root


def _frontmatter(
    *,
    name: str | None,
    description: str,
    fields: tuple[tuple[str, str | tuple[str, ...]], ...] = (),
) -> str:
    lines = ["---"]
    if name is not None:
        lines.append(f"name: {json.dumps(name, ensure_ascii=False)}")
    lines.append(f"description: {json.dumps(description, ensure_ascii=False)}")
    for key, value in fields:
        if isinstance(value, tuple):
            lines.append(f"{key}:")
            lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in value)
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(("---", ""))
    return "\n".join(lines)


class _BaseRenderer:
    target: IntegrationTarget

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        raise NotImplementedError

    def _agent_bytes(self, assets: IntegrationAssetBundle, role_id: str) -> bytes:
        body = assets.role_body(role_id).strip() + "\n"
        rendered = _frontmatter(
            name=self._agent_name(assets, role_id),
            description=assets.role_description(role_id),
        )
        return (rendered + body).encode("utf-8")

    def _agent_name(self, assets: IntegrationAssetBundle, role_id: str) -> str:
        return assets.role_host_name(role_id)

    def _agent_suffix(self) -> str:
        return ".md"

    def _mcp_projection(
        self,
        context: ProjectionContext,
        config_path: Path,
    ) -> JsonEntryProjection | TextBlockProjection:
        command = str(context.python_executable)
        value: JsonObject = {
            "command": command,
            "args": ["-m", "graph_skill_runtime", "mcp"],
        }
        return JsonEntryProjection(
            resource_id=_MCP_RESOURCE_ID,
            path=config_path,
            selector=("mcpServers", _MCP_SERVER_NAME),
            value=value,
        )

    def render(
        self,
        assets: IntegrationAssetBundle,
        context: ProjectionContext,
    ) -> tuple[ProjectionResource, ...]:
        layout = self._layout(context)
        projected: list[ProjectionResource] = []
        for skill_id in assets.skill_ids():
            skill_root = layout.skill_root / skill_id
            projected.append(
                FileProjection(
                    resource_id=f"skill:{skill_id}:SKILL.md",
                    path=skill_root / "SKILL.md",
                    content=assets.skill_file(skill_id),
                )
            )
            projected.extend(
                FileProjection(
                    resource_id=f"skill:{skill_id}:reference:{filename}",
                    path=skill_root / "references" / filename,
                    content=content,
                )
                for filename, content in assets.skill_reference_files(skill_id)
            )
        for role_id in assets.role_ids():
            projected.append(
                FileProjection(
                    resource_id=f"role:{role_id}",
                    path=layout.agent_root
                    / f"{self._agent_name(assets, role_id)}{self._agent_suffix()}",
                    content=self._agent_bytes(assets, role_id),
                )
            )
        projected.append(self._mcp_projection(context, layout.config_path))
        return tuple(projected)

    def allowed_file_roots(self, context: ProjectionContext) -> tuple[Path, ...]:
        layout = self._layout(context)
        return (layout.skill_root, layout.agent_root)

    def allowed_config_paths(self, context: ProjectionContext) -> tuple[Path, ...]:
        return (self._layout(context).config_path,)


class ClaudeRenderer(_BaseRenderer):
    target = IntegrationTarget.CLAUDE

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        base = (
            context.home / ".claude"
            if context.scope is IntegrationScope.USER
            else _project_root(context) / ".claude"
        )
        config = (
            context.home / ".claude.json"
            if context.scope is IntegrationScope.USER
            else _project_root(context) / ".mcp.json"
        )
        return _HostLayout(base / "skills", base / "agents", config)

    def _agent_bytes(self, assets: IntegrationAssetBundle, role_id: str) -> bytes:
        rendered = _frontmatter(
            name=assets.role_host_name(role_id),
            description=assets.role_description(role_id),
            fields=(("skills", assets.role_skill_ids(role_id)),),
        )
        return (rendered + assets.role_body(role_id).strip() + "\n").encode("utf-8")


class CodexRenderer(_BaseRenderer):
    target = IntegrationTarget.CODEX

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        if context.scope is IntegrationScope.USER:
            return _HostLayout(
                context.home / ".agents" / "skills",
                context.home / ".codex" / "agents",
                context.home / ".codex" / "config.toml",
            )
        project = _project_root(context)
        return _HostLayout(
            project / ".agents" / "skills",
            project / ".codex" / "agents",
            project / ".codex" / "config.toml",
        )

    def _agent_bytes(self, assets: IntegrationAssetBundle, role_id: str) -> bytes:
        document = {
            "name": self._agent_name(assets, role_id),
            "description": assets.role_description(role_id),
            "developer_instructions": assets.role_body(role_id).strip() + "\n",
        }
        return tomli_w.dumps(document).encode("utf-8")

    def _agent_name(self, assets: IntegrationAssetBundle, role_id: str) -> str:
        # Keep the projected identifier usable on Codex's lower-snake-case
        # agent/tool surfaces. The canonical provider-neutral role name remains
        # unchanged; host-specific normalization belongs in this adapter.
        name = assets.role_host_name(role_id).replace("-", "_")
        if re.fullmatch(r"[a-z0-9_]+", name) is None:
            raise ValueError(f"Codex custom agent name is not representable: {name!r}")
        return name

    def _agent_suffix(self) -> str:
        return ".toml"

    def _mcp_projection(
        self,
        context: ProjectionContext,
        config_path: Path,
    ) -> TextBlockProjection:
        document = {
            "mcp_servers": {
                _MCP_SERVER_NAME: {
                    "command": str(context.python_executable),
                    "args": ["-m", "graph_skill_runtime", "mcp"],
                }
            }
        }
        marker = "graph-skill-runtime:moirai:gskill-mcp"
        body = tomli_w.dumps(document).strip()
        content = (
            f"# >>> {marker} >>>\n{body}\n# <<< {marker} <<<\n"
        ).encode()
        return TextBlockProjection(
            resource_id=_MCP_RESOURCE_ID,
            path=config_path,
            marker=marker,
            content=content,
        )


class CopilotRenderer(_BaseRenderer):
    target = IntegrationTarget.COPILOT

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        if context.scope is IntegrationScope.USER:
            base = context.home / ".copilot"
            return _HostLayout(base / "skills", base / "agents", base / "mcp-config.json")
        project = _project_root(context)
        return _HostLayout(
            project / ".github" / "skills",
            project / ".github" / "agents",
            project / ".github" / "mcp.json",
        )

    def _mcp_projection(
        self,
        context: ProjectionContext,
        config_path: Path,
    ) -> JsonEntryProjection:
        value: JsonObject = {
            "type": "local",
            "command": str(context.python_executable),
            "args": ["-m", "graph_skill_runtime", "mcp"],
            "tools": ["*"],
        }
        return JsonEntryProjection(
            resource_id=_MCP_RESOURCE_ID,
            path=config_path,
            selector=("mcpServers", _MCP_SERVER_NAME),
            value=value,
        )


class CursorRenderer(_BaseRenderer):
    target = IntegrationTarget.CURSOR

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        base = (
            context.home / ".cursor"
            if context.scope is IntegrationScope.USER
            else _project_root(context) / ".cursor"
        )
        return _HostLayout(base / "skills", base / "agents", base / "mcp.json")


class GeminiRenderer(_BaseRenderer):
    target = IntegrationTarget.GEMINI

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        base = (
            context.home / ".gemini"
            if context.scope is IntegrationScope.USER
            else _project_root(context) / ".gemini"
        )
        return _HostLayout(base / "skills", base / "agents", base / "settings.json")

    def _agent_bytes(self, assets: IntegrationAssetBundle, role_id: str) -> bytes:
        rendered = _frontmatter(
            name=assets.role_host_name(role_id),
            description=assets.role_description(role_id),
            fields=(("kind", "local"),),
        )
        return (rendered + assets.role_body(role_id).strip() + "\n").encode("utf-8")


class OpenCodeRenderer(_BaseRenderer):
    target = IntegrationTarget.OPENCODE

    def _layout(self, context: ProjectionContext) -> _HostLayout:
        if context.scope is IntegrationScope.USER:
            base = context.home / ".config" / "opencode"
            return _HostLayout(base / "skills", base / "agents", base / "opencode.json")
        project = _project_root(context)
        return _HostLayout(
            project / ".opencode" / "skills",
            project / ".opencode" / "agents",
            project / ".opencode" / "opencode.json",
        )

    def _agent_bytes(self, assets: IntegrationAssetBundle, role_id: str) -> bytes:
        rendered = _frontmatter(
            name=None,
            description=assets.role_description(role_id),
            fields=(("mode", "subagent"),),
        )
        return (rendered + assets.role_body(role_id).strip() + "\n").encode("utf-8")

    def _mcp_projection(
        self,
        context: ProjectionContext,
        config_path: Path,
    ) -> JsonEntryProjection:
        value: JsonObject = {
            "type": "local",
            "command": [
                str(context.python_executable),
                "-m",
                "graph_skill_runtime",
                "mcp",
            ],
        }
        return JsonEntryProjection(
            resource_id=_MCP_RESOURCE_ID,
            path=config_path,
            selector=("mcp", "servers", _MCP_SERVER_NAME),
            value=value,
        )


_RENDERERS: dict[IntegrationTarget, HostIntegrationRenderer] = {
    renderer.target: renderer
    for renderer in (
        ClaudeRenderer(),
        CodexRenderer(),
        CopilotRenderer(),
        CursorRenderer(),
        GeminiRenderer(),
        OpenCodeRenderer(),
    )
}


def renderer_for(target: IntegrationTarget) -> HostIntegrationRenderer:
    """Return the single renderer that owns one host target."""

    return _RENDERERS[target]


__all__ = [
    "ClaudeRenderer",
    "CodexRenderer",
    "CopilotRenderer",
    "CursorRenderer",
    "GeminiRenderer",
    "OpenCodeRenderer",
    "renderer_for",
]
