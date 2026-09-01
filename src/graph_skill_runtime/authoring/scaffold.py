"""Create one minimal portable gSkill without adopting existing content."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from graph_skill_runtime.core.manifest import AGENT_SKILL_NAME_PATTERN
from graph_skill_runtime.gskill_version import GSKILL_SCHEMA_VERSION


class CreateGSkillResult(BaseModel):
    """Structured result for the module CLI ``create`` authoring boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.create-result.v1"] = "gskill.create-result.v1"
    kind: Literal["create_gskill_result"] = "create_gskill_result"
    status: Literal["created"] = "created"
    skill_root: str = Field(min_length=1)
    gskill_version: Literal["gskill.graph.v1"] = GSKILL_SCHEMA_VERSION
    files: tuple[str, ...] = Field(min_length=1)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _root_skill(name: str, description: str) -> str:
    activation = f"gSkill for Graph Skill Runtime: {description}"
    if len(activation) > 1024:
        raise ValueError("the generated Agent Skill description exceeds 1024 characters")
    return f"""---
name: {name}
description: {_yaml_string(activation)}
metadata:
  gskill: {GSKILL_SCHEMA_VERSION}
---

# {name}

This directory is a gSkill executed by Graph Skill Runtime. Use the installed
`gskill` Agent Skill to compile it before prediction or execution, prefer the
`gskill` MCP server when available, and use `python -m graph_skill_runtime` as
the CLI fallback.
"""


def _graph(description: str) -> str:
    return f"""schema_version: {GSKILL_SCHEMA_VERSION}
graph_id: main
description: {_yaml_string(description)}
io:
  inputs:
    type: object
    required: [request]
    additionalProperties: false
    properties:
      request: {{type: string}}
  outputs:
    type: object
    required: [result]
    additionalProperties: false
    properties:
      result: {{type: string}}
phases:
  - id: main
    depends_on: [input]
    output: true
"""


def _agent_phase() -> str:
    return """---
name: complete request
io:
  inputs:
    type: object
    required: [request]
    additionalProperties: false
    properties:
      request: {type: string}
  outputs:
    type: object
    required: [result]
    additionalProperties: false
    properties:
      result: {type: string}
subagents: []
subgraphs: []
references: []
examples: []
---

<role>
Complete one bounded request using only the supplied input and permitted host capabilities.
</role>

<goal>
Return the requested result through the declared output contract.
</goal>

<step id="S1" name="complete">
Complete the request and preserve uncertainty when the available evidence is insufficient.
</step>

<protocol id="P1">
Return only the declared result value and do not invent unavailable facts.
</protocol>
"""


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def create_gskill(
    name: str,
    *,
    parent: str | Path,
    description: str,
) -> CreateGSkillResult:
    """Create a valid one-Agent-phase gSkill beneath an existing parent directory."""

    if re.fullmatch(AGENT_SKILL_NAME_PATTERN, name) is None:
        raise ValueError(
            "NAME must contain lowercase ASCII letters, digits, or single hyphens"
        )
    clean_description = description.strip()
    if not clean_description:
        raise ValueError("--description must be non-empty")
    parent_path = Path(parent).resolve(strict=False)
    if not parent_path.is_dir():
        raise ValueError(f"--path must name an existing directory: {parent_path}")
    destination = parent_path / name
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists and will not be adopted: {destination}")

    authored = {
        "SKILL.md": _root_skill(name, clean_description),
        "graph.yaml": _graph(clean_description),
        "phases/main/AGENT.md": _agent_phase(),
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=parent_path))
    try:
        for relative, content in authored.items():
            _write_text(temporary / Path(relative), content)
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return CreateGSkillResult(
        skill_root=str(destination),
        files=tuple(authored),
    )
