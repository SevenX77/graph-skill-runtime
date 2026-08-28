from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import yaml

from graph_skill_runtime.integrations.catalog import PackagedMoiraiAssets
from graph_skill_runtime.integrations.models import IntegrationScope, IntegrationTarget
from graph_skill_runtime.integrations.renderers import renderer_for
from graph_skill_runtime.ports.integrations import (
    FileProjection,
    JsonEntryProjection,
    ProjectionContext,
    TextBlockProjection,
)
from tests.integrations._fake_assets import FakeMoiraiAssets

SNAPSHOT_PATH = Path(__file__).with_name("snapshots") / "moirai_renderers.json"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _portable_path(path: Path, context: ProjectionContext) -> str:
    rendered = path.as_posix()
    anchors = ((context.project_root, "<project>"), (context.home, "<home>"))
    for root, token in anchors:
        if root is None:
            continue
        prefix = root.as_posix()
        if rendered == prefix:
            return token
        if rendered.startswith(prefix + "/"):
            return token + rendered[len(prefix) :]
    raise AssertionError(f"renderer path is outside the declared host roots: {path}")


def _portable_json(value: object, context: ProjectionContext) -> object:
    if isinstance(value, str):
        return "<python>" if value == str(context.python_executable) else value
    if isinstance(value, list):
        return [_portable_json(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _portable_json(item, context) for key, item in value.items()}
    return value


def _resource_snapshot(resource: object, context: ProjectionContext) -> dict[str, object]:
    if isinstance(resource, FileProjection):
        return {
            "kind": "file",
            "resource_id": resource.resource_id,
            "path": _portable_path(resource.path, context),
            "content_sha256": _sha256(resource.content),
        }
    if isinstance(resource, JsonEntryProjection):
        return {
            "kind": "json_entry",
            "resource_id": resource.resource_id,
            "path": _portable_path(resource.path, context),
            "selector": list(resource.selector),
            "value": _portable_json(resource.value, context),
        }
    if isinstance(resource, TextBlockProjection):
        content = resource.content.decode("utf-8")
        document = tomllib.loads(
            "\n".join(
                line
                for line in content.splitlines()
                if not line.startswith("# >>> ") and not line.startswith("# <<< ")
            )
        )
        return {
            "kind": "text_block",
            "resource_id": resource.resource_id,
            "path": _portable_path(resource.path, context),
            "marker": resource.marker,
            "document": _portable_json(document, context),
        }
    raise AssertionError(f"unexpected projection resource: {type(resource)!r}")


def _renderer_snapshot() -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for target in IntegrationTarget:
        scopes: dict[str, object] = {}
        for scope in IntegrationScope:
            context = ProjectionContext(
                scope=scope,
                home=Path("/host-home"),
                project_root=Path("/project") if scope is IntegrationScope.PROJECT else None,
                python_executable=Path("/runtime/python"),
            )
            resources = renderer_for(target).render(FakeMoiraiAssets(), context)
            scopes[scope.value] = [
                _resource_snapshot(resource, context) for resource in resources
            ]
        snapshot[target.value] = scopes
    return snapshot


def _frontmatter(content: bytes) -> dict[str, object]:
    text = content.decode("utf-8")
    assert text.startswith("---\n")
    metadata, _body = text[4:].split("\n---\n", 1)
    parsed = yaml.safe_load(metadata)
    assert isinstance(parsed, dict)
    return parsed


def test_six_host_renderers_match_the_reviewed_project_and_user_snapshot() -> None:
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert _renderer_snapshot() == expected


def test_each_host_agent_profile_uses_only_its_native_metadata_shape() -> None:
    context = ProjectionContext(
        scope=IntegrationScope.PROJECT,
        home=Path("/host-home"),
        project_root=Path("/project"),
        python_executable=Path("/runtime/python"),
    )
    assets = FakeMoiraiAssets()
    expected_markdown = {
        IntegrationTarget.CLAUDE: {
            "name": "moirai",
            "description": "Coordinate one graph-skill workflow.",
            "skills": ["moirai"],
        },
        IntegrationTarget.COPILOT: {
            "name": "moirai",
            "description": "Coordinate one graph-skill workflow.",
        },
        IntegrationTarget.CURSOR: {
            "name": "moirai",
            "description": "Coordinate one graph-skill workflow.",
        },
        IntegrationTarget.GEMINI: {
            "name": "moirai",
            "description": "Coordinate one graph-skill workflow.",
            "kind": "local",
        },
        IntegrationTarget.OPENCODE: {
            "description": "Coordinate one graph-skill workflow.",
            "mode": "subagent",
        },
    }
    for target in IntegrationTarget:
        agent = next(
            resource
            for resource in renderer_for(target).render(assets, context)
            if isinstance(resource, FileProjection) and resource.resource_id == "role:moirai"
        )
        if target is IntegrationTarget.CODEX:
            assert tomllib.loads(agent.content.decode("utf-8")) == {
                "name": "moirai",
                "description": "Coordinate one graph-skill workflow.",
                "developer_instructions": "# MoirAI\n\nUse the installed runtime tools.\n",
            }
        else:
            assert _frontmatter(agent.content) == expected_markdown[target]


def test_every_canonical_asset_is_projected_for_every_renderer() -> None:
    context = ProjectionContext(
        scope=IntegrationScope.PROJECT,
        home=Path("/host-home"),
        project_root=Path("/project"),
        python_executable=Path("/runtime/python"),
    )
    assets = PackagedMoiraiAssets()
    expected_ids = {
        *(f"skill:{skill_id}:SKILL.md" for skill_id in assets.skill_ids()),
        *(
            f"skill:{skill_id}:reference:{filename}"
            for skill_id in assets.skill_ids()
            for filename, _content in assets.skill_reference_files(skill_id)
        ),
        *(f"role:{role_id}" for role_id in assets.role_ids()),
        "mcp:gskill",
    }

    for target in IntegrationTarget:
        resources = renderer_for(target).render(assets, context)
        assert {resource.resource_id for resource in resources} == expected_ids
        assert len(resources) == len(expected_ids)


def test_codex_normalizes_canonical_role_names_for_its_spawn_contract() -> None:
    context = ProjectionContext(
        scope=IntegrationScope.PROJECT,
        home=Path("/host-home"),
        project_root=Path("/project"),
        python_executable=Path("/runtime/python"),
    )

    roles = {
        resource.resource_id: resource
        for resource in renderer_for(IntegrationTarget.CODEX).render(
            PackagedMoiraiAssets(), context
        )
        if isinstance(resource, FileProjection) and resource.resource_id.startswith("role:")
    }

    assert roles["role:clotho"].path == Path(
        "/project/.codex/agents/moirai_clotho.toml"
    )
    assert tomllib.loads(roles["role:clotho"].content.decode("utf-8"))["name"] == (
        "moirai_clotho"
    )
