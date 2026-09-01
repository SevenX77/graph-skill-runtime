"""Validated access to the provider-neutral Agent kit package resources."""

from __future__ import annotations

import json
import re
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML as RuamelYAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError

from graph_skill_runtime.gskill_version import GSKILL_SCHEMA_VERSION

_ASSET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FILE_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*\.md$")


class _SkillAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    references: tuple[str, ...]


class _SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=1024)


class _AssetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.agent-kit-assets.v1"]
    kit_version: str = Field(min_length=1)
    gskill_version: Literal["gskill.graph.v1"]
    agents_template: Literal["AGENTS.md"]
    rules: tuple[str, ...] = Field(min_length=1)
    skills: tuple[_SkillAsset, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_inventory(self) -> _AssetManifest:
        if self.gskill_version != GSKILL_SCHEMA_VERSION:
            raise ValueError("Agent kit and runtime gSkill versions disagree")
        if len(self.rules) != len(set(self.rules)):
            raise ValueError("Agent kit rule filenames must be unique")
        if any(_FILE_NAME.fullmatch(name) is None for name in self.rules):
            raise ValueError("Agent kit rule filenames are invalid")
        skill_ids = [skill.id for skill in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Agent kit skill ids must be unique")
        if any(_ASSET_ID.fullmatch(skill_id) is None for skill_id in skill_ids):
            raise ValueError("Agent kit skill ids are invalid")
        rules = set(self.rules)
        for skill in self.skills:
            if len(skill.references) != len(set(skill.references)):
                raise ValueError(f"Agent kit skill {skill.id!r} repeats a reference")
            unknown = set(skill.references) - rules
            if unknown:
                raise ValueError(
                    f"Agent kit skill {skill.id!r} references unknown rules: {sorted(unknown)}"
                )
        return self


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _file_inventory(root: Traversable, prefix: str = "") -> set[str]:
    inventory: set[str] = set()
    for child in tuple(root.iterdir()):
        relative = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_dir():
            inventory.update(_file_inventory(child, relative))
        elif child.is_file():
            inventory.add(relative)
        else:
            raise ValueError(f"Agent kit asset is not a regular file: {relative}")
    return inventory


def _validate_utf8_lf(content: bytes, *, label: str) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8: {exc}") from exc
    if text.startswith("\ufeff"):
        raise ValueError(f"{label} must not contain a UTF-8 BOM")
    if "\r" in text:
        raise ValueError(f"{label} must use LF line endings")
    if not text.strip():
        raise ValueError(f"{label} is empty")
    return text


def _validate_skill(content: bytes, *, skill_id: str) -> None:
    text = _validate_utf8_lf(content, label=f"Agent kit skill {skill_id!r}")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"Agent kit skill {skill_id!r} has no YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"Agent kit skill {skill_id!r} has unclosed YAML frontmatter") from exc
    reader = RuamelYAML(typ="safe")
    reader.allow_duplicate_keys = False
    try:
        metadata = _SkillMetadata.model_validate(reader.load("\n".join(lines[1:closing])))
    except (RuamelYAMLError, ValidationError) as exc:
        raise ValueError(f"invalid Agent kit skill metadata for {skill_id!r}: {exc}") from exc
    if metadata.name != skill_id:
        raise ValueError(
            f"Agent kit skill metadata name {metadata.name!r} must equal asset id {skill_id!r}"
        )
    if not "\n".join(lines[closing + 1 :]).strip():
        raise ValueError(f"Agent kit skill {skill_id!r} has an empty instruction body")


class PackagedAgentKitAssets:
    """Read one validated, closed Agent kit asset bundle."""

    def __init__(self, root: Traversable | None = None) -> None:
        self._root = root or resources.files("graph_skill_runtime.agent_kit").joinpath(
            "assets"
        )
        try:
            raw = self._root.joinpath("manifest.json").read_text(encoding="utf-8")
            if "\r" in raw:
                raise ValueError("Agent kit manifest must use LF line endings")
            self._manifest = _AssetManifest.model_validate(
                json.loads(raw, object_pairs_hook=_unique_json_object)
            )
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid packaged Agent kit manifest: {exc}") from exc
        self._skills = {skill.id: skill for skill in self._manifest.skills}
        self._validate_files()

    @property
    def kit_version(self) -> str:
        return self._manifest.kit_version

    @property
    def gskill_version(self) -> str:
        return self._manifest.gskill_version

    def rule_files(self) -> tuple[tuple[str, bytes], ...]:
        return tuple((name, self._read_bytes("rules", name)) for name in self._manifest.rules)

    def skill_ids(self) -> tuple[str, ...]:
        return tuple(skill.id for skill in self._manifest.skills)

    def agents_template(self) -> bytes:
        return self._read_bytes(self._manifest.agents_template)

    def skill_file(self, skill_id: str) -> bytes:
        return self._read_bytes("skills", self._skill(skill_id).id, "SKILL.md")

    def skill_reference_files(self, skill_id: str) -> tuple[tuple[str, bytes], ...]:
        return tuple(
            (name, self._read_bytes("rules", name))
            for name in self._skill(skill_id).references
        )

    def source_manifest(self) -> bytes:
        return self._read_bytes("manifest.json")

    def _skill(self, skill_id: str) -> _SkillAsset:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise ValueError(f"unknown Agent kit skill: {skill_id}") from exc

    def _read_bytes(self, *parts: str) -> bytes:
        try:
            return self._root.joinpath(*parts).read_bytes()
        except OSError as exc:
            raise ValueError(f"cannot read packaged Agent kit asset {'/'.join(parts)}: {exc}") from exc

    def _validate_files(self) -> None:
        expected = {"manifest.json", self._manifest.agents_template}
        expected.update(f"rules/{name}" for name in self._manifest.rules)
        expected.update(f"skills/{skill_id}/SKILL.md" for skill_id in self.skill_ids())
        actual = _file_inventory(self._root)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ValueError(
                f"invalid packaged Agent kit inventory: missing={missing}; unexpected={unexpected}"
            )
        if any(path.casefold().endswith("graph.yaml") for path in actual):
            raise ValueError("Agent kit assets must not contain a user business graph.yaml")
        _validate_utf8_lf(self.agents_template(), label="Agent kit AGENTS.md")
        for name, content in self.rule_files():
            _validate_utf8_lf(content, label=f"Agent kit rule {name!r}")
        for skill_id in self.skill_ids():
            _validate_skill(self.skill_file(skill_id), skill_id=skill_id)
