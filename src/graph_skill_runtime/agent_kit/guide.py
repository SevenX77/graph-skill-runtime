"""Read-only guidance for configuring the packaged Agent kit."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from graph_skill_runtime.agent_kit.catalog import PackagedAgentKitAssets


class AgentKitGuideAsset(BaseModel):
    """One canonical source file an authorized user or Agent may place."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: str = Field(min_length=1)


class AgentKitHostPlacement(BaseModel):
    """Current documented instruction and Skill locations for one host."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: Literal["codex", "claude-code", "other"]
    user_instructions: str = Field(min_length=1)
    project_instructions: str = Field(min_length=1)
    user_skills: str = Field(min_length=1)
    project_skills: str = Field(min_length=1)
    notes: tuple[str, ...] = ()


class AgentKitGuideResult(BaseModel):
    """Self-contained, non-mutating setup decision guide."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.agent-kit-guide.v1"] = (
        "gskill.agent-kit-guide.v1"
    )
    kind: Literal["agent_kit_guide"] = "agent_kit_guide"
    status: Literal["guidance"] = "guidance"
    kit_version: str = Field(min_length=1)
    gskill_version: str = Field(min_length=1)
    writes_performed: Literal[False] = False
    decisions: tuple[str, ...] = Field(min_length=1)
    placements: tuple[AgentKitHostPlacement, ...] = Field(min_length=1)
    assets: tuple[AgentKitGuideAsset, ...] = Field(min_length=1)


def _guide_asset(relative_path: str, content: bytes) -> AgentKitGuideAsset:
    return AgentKitGuideAsset(
        relative_path=relative_path,
        sha256=hashlib.sha256(content).hexdigest(),
        content=content.decode("utf-8"),
    )


def _configuration_assets(
    assets: PackagedAgentKitAssets,
) -> tuple[AgentKitGuideAsset, ...]:
    files = [_guide_asset("AGENTS.md", assets.agents_template())]
    files.extend(
        _guide_asset(f"rules/{name}", content)
        for name, content in assets.rule_files()
    )
    for skill_id in assets.skill_ids():
        files.append(
            _guide_asset(
                f"skills/{skill_id}/SKILL.md",
                assets.skill_file(skill_id),
            )
        )
        files.extend(
            _guide_asset(f"skills/{skill_id}/references/{name}", content)
            for name, content in assets.skill_reference_files(skill_id)
        )
    return tuple(files)


def agent_configuration_guide(
    *,
    assets: PackagedAgentKitAssets | None = None,
) -> AgentKitGuideResult:
    """Return configuration choices and canonical bytes without writing anything."""

    active_assets = assets or PackagedAgentKitAssets()
    return AgentKitGuideResult(
        kit_version=active_assets.kit_version,
        gskill_version=active_assets.gskill_version,
        decisions=(
            "Ask which hosts must discover the kit.",
            "Ask whether the guidance and Skills should apply to this user or one project.",
            "Ask whether the user will edit manually or authorizes the current Agent to edit.",
            "Inspect every selected existing instruction and Skill destination before proposing changes.",
            "Present an additive merge and copy plan; never replace an existing instruction file.",
            "Write only after the user approves the exact scope and destinations.",
            "Start a fresh host session and verify instruction plus implicit Skill discovery.",
        ),
        placements=(
            AgentKitHostPlacement(
                host="codex",
                user_instructions="$CODEX_HOME/AGENTS.md (default ~/.codex/AGENTS.md)",
                project_instructions="$REPO_ROOT/AGENTS.md",
                user_skills="$HOME/.agents/skills",
                project_skills="$REPO_ROOT/.agents/skills",
                notes=(
                    "Merge the AGENTS.md asset as one Graph Skill Runtime section and retain its rule index.",
                    "Copy the rules tree to an owner-selected location and make the merged section point to it.",
                    "Copy each skills/<id> tree beneath the selected Skill root.",
                ),
            ),
            AgentKitHostPlacement(
                host="claude-code",
                user_instructions="$HOME/.claude/CLAUDE.md",
                project_instructions=(
                    "$REPO_ROOT/CLAUDE.md or $REPO_ROOT/.claude/CLAUDE.md"
                ),
                user_skills="$HOME/.claude/skills",
                project_skills="$REPO_ROOT/.claude/skills",
                notes=(
                    "Claude Code reads CLAUDE.md, not AGENTS.md.",
                    "A project CLAUDE.md may import @AGENTS.md when that matches the owner's policy.",
                    "Copy the rules tree to an owner-selected location and make the merged section point to it.",
                    "Copy each skills/<id> tree beneath the selected Skill root.",
                ),
            ),
            AgentKitHostPlacement(
                host="other",
                user_instructions="The host-documented user instruction file",
                project_instructions="The host-documented project instruction file",
                user_skills="The host-documented user Agent Skills root",
                project_skills="The host-documented project Agent Skills root",
                notes=(
                    "Verify that the host implements the open Agent Skills format before copying.",
                    "Keep provider-specific configuration outside runtime core.",
                ),
            ),
        ),
        assets=_configuration_assets(active_assets),
    )
