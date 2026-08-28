"""Validated access to canonical integration assets inside the distribution."""

from __future__ import annotations

import json
import re
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML as RuamelYAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError

_ASSET_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class _RoleAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    host_name: str
    description: str = Field(min_length=1)
    skills: tuple[str, ...]


class _SkillAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    references: tuple[str, ...]


class _SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=1024)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _require_unique(values: list[str], *, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_identifiers(values: tuple[str, ...]) -> None:
    for name in values:
        if _ASSET_NAME.fullmatch(name) is None:
            raise ValueError(f"invalid integration asset id: {name!r}")


def _validate_knowledge_files(filenames: tuple[str, ...]) -> set[str]:
    _require_unique(list(filenames), label="knowledge filenames")
    for filename in filenames:
        if _FILE_NAME.fullmatch(filename) is None:
            raise ValueError(f"invalid knowledge filename: {filename!r}")
    return set(filenames)


def _validate_references(
    roles: tuple[_RoleAsset, ...],
    skills: tuple[_SkillAsset, ...],
    knowledge: set[str],
) -> None:
    skill_ids = {skill.id for skill in skills}
    for role in roles:
        unknown = set(role.skills) - skill_ids
        if unknown:
            raise ValueError(f"role {role.id!r} references unknown skills: {sorted(unknown)}")
    for skill in skills:
        unknown = set(skill.references) - knowledge
        if unknown:
            raise ValueError(
                f"skill {skill.id!r} references unknown knowledge files: {sorted(unknown)}"
            )


def _file_inventory(root: Traversable, prefix: str = "") -> set[str]:
    inventory: set[str] = set()
    try:
        children = tuple(root.iterdir())
    except OSError as exc:
        raise ValueError(f"cannot enumerate packaged MoirAI assets: {exc}") from exc
    for child in children:
        relative = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_dir():
            inventory.update(_file_inventory(child, relative))
        elif child.is_file():
            inventory.add(relative)
        else:
            raise ValueError(f"packaged MoirAI asset is not a regular file: {relative}")
    return inventory


def _validate_skill_metadata(content: bytes, *, skill_id: str) -> None:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"MoirAI skill {skill_id!r} is not UTF-8: {exc}") from exc
    if "\r" in text:
        raise ValueError(f"MoirAI skill {skill_id!r} must use LF line endings")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"MoirAI skill {skill_id!r} has no YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"MoirAI skill {skill_id!r} has unclosed YAML frontmatter") from exc
    yaml_reader = RuamelYAML(typ="safe")
    yaml_reader.allow_duplicate_keys = False
    try:
        raw_metadata = yaml_reader.load("\n".join(lines[1:closing]))
        metadata = _SkillMetadata.model_validate(raw_metadata)
    except (RuamelYAMLError, ValidationError) as exc:
        raise ValueError(f"invalid MoirAI skill metadata for {skill_id!r}: {exc}") from exc
    if metadata.name != skill_id:
        raise ValueError(
            f"MoirAI skill metadata name {metadata.name!r} must equal asset id {skill_id!r}"
        )
    if not "\n".join(lines[closing + 1 :]).strip():
        raise ValueError(f"MoirAI skill {skill_id!r} has an empty instruction body")


def _validate_inventory(*, actual: set[str], expected: set[str]) -> None:
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append("missing=" + ", ".join(missing))
    if unexpected:
        details.append("unexpected=" + ", ".join(unexpected))
    raise ValueError("invalid packaged MoirAI asset inventory: " + "; ".join(details))


class _AssetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.integration-assets.v1"]
    integration_id: Literal["moirai"]
    asset_version: str = Field(min_length=1)
    roles: tuple[_RoleAsset, ...]
    skills: tuple[_SkillAsset, ...]
    knowledge: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_names_and_references(self) -> _AssetManifest:
        role_ids = [role.id for role in self.roles]
        host_names = [role.host_name for role in self.roles]
        skill_ids = [skill.id for skill in self.skills]
        _require_unique(role_ids, label="role ids")
        _require_unique(host_names, label="role host names")
        _require_unique(skill_ids, label="skill ids")
        _validate_identifiers(tuple((*role_ids, *host_names, *skill_ids)))
        knowledge = _validate_knowledge_files(self.knowledge)
        _validate_references(self.roles, self.skills, knowledge)
        return self


class PackagedMoiraiAssets:
    """Read one validated, immutable MoirAI asset bundle from package resources."""

    def __init__(self, root: Traversable | None = None) -> None:
        self._root = root or resources.files("graph_skill_runtime.integrations.assets").joinpath(
            "moirai"
        )
        try:
            raw = self._root.joinpath("integration.json").read_text(encoding="utf-8")
            if "\r" in raw:
                raise ValueError("integration.json must use LF line endings")
            self._manifest = _AssetManifest.model_validate(
                json.loads(raw, object_pairs_hook=_unique_json_object)
            )
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid packaged MoirAI integration manifest: {exc}") from exc
        self._roles = {role.id: role for role in self._manifest.roles}
        self._skills = {skill.id: skill for skill in self._manifest.skills}
        self._validate_files()

    @property
    def integration_id(self) -> str:
        return self._manifest.integration_id

    @property
    def asset_version(self) -> str:
        return self._manifest.asset_version

    def skill_ids(self) -> tuple[str, ...]:
        return tuple(skill.id for skill in self._manifest.skills)

    def role_ids(self) -> tuple[str, ...]:
        return tuple(role.id for role in self._manifest.roles)

    def knowledge_files(self) -> tuple[str, ...]:
        return self._manifest.knowledge

    def role_host_name(self, role_id: str) -> str:
        return self._role(role_id).host_name

    def role_description(self, role_id: str) -> str:
        return self._role(role_id).description

    def role_skill_ids(self, role_id: str) -> tuple[str, ...]:
        return self._role(role_id).skills

    def role_body(self, role_id: str) -> str:
        return self._read_text("roles", f"{self._role(role_id).id}.md")

    def skill_file(self, skill_id: str) -> bytes:
        skill = self._skill(skill_id)
        return self._read_bytes("skills", skill.id, "SKILL.md")

    def skill_reference_files(self, skill_id: str) -> tuple[tuple[str, bytes], ...]:
        skill = self._skill(skill_id)
        return tuple(
            (filename, self._read_bytes("knowledge", filename))
            for filename in skill.references
        )

    def _role(self, role_id: str) -> _RoleAsset:
        try:
            return self._roles[role_id]
        except KeyError as exc:
            raise ValueError(f"unknown MoirAI role: {role_id}") from exc

    def _skill(self, skill_id: str) -> _SkillAsset:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise ValueError(f"unknown MoirAI skill: {skill_id}") from exc

    def _read_text(self, *parts: str) -> str:
        try:
            return self._root.joinpath(*parts).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read packaged MoirAI asset {'/'.join(parts)}: {exc}") from exc

    def _read_bytes(self, *parts: str) -> bytes:
        try:
            return self._root.joinpath(*parts).read_bytes()
        except OSError as exc:
            raise ValueError(f"cannot read packaged MoirAI asset {'/'.join(parts)}: {exc}") from exc

    def _validate_files(self) -> None:
        expected = {"integration.json"}
        expected.update(f"roles/{role_id}.md" for role_id in self.role_ids())
        expected.update(f"skills/{skill_id}/SKILL.md" for skill_id in self.skill_ids())
        expected.update(f"knowledge/{filename}" for filename in self.knowledge_files())
        actual = _file_inventory(self._root)
        _validate_inventory(actual=actual, expected=expected)
        if any(path.casefold().endswith("graph.yaml") for path in actual):
            raise ValueError("MoirAI integration assets must not contain a user business graph.yaml")
        for role_id in self.role_ids():
            body = self.role_body(role_id)
            if not body.strip():
                raise ValueError(f"MoirAI role {role_id!r} has an empty instruction body")
            if "\r" in body:
                raise ValueError(f"MoirAI role {role_id!r} must use LF line endings")
        for skill_id in self.skill_ids():
            content = self.skill_file(skill_id)
            _validate_skill_metadata(content, skill_id=skill_id)
            self.skill_reference_files(skill_id)
        for filename in self.knowledge_files():
            content = self._read_bytes("knowledge", filename)
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"MoirAI knowledge file {filename!r} is not UTF-8: {exc}") from exc
            if not text.strip():
                raise ValueError(f"MoirAI knowledge file {filename!r} is empty")
            if "\r" in text:
                raise ValueError(f"MoirAI knowledge file {filename!r} must use LF line endings")


__all__ = ["PackagedMoiraiAssets"]
