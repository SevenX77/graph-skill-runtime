"""One-shot converter from the frozen Studio v0.3 layout to portable gSkill v1."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NoReturn, cast

import tomli_w
import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.graph_serializer import serialize_graph
from graph_skill_runtime.core.local_workspace_resolver import LocalWorkspaceResolver
from graph_skill_runtime.core.manifest import (
    AGENT_SKILL_NAME_PATTERN,
    GRAPH_ID_PATTERN,
    ArtifactDeclaration,
    GraphManifest,
    GraphPhaseRef,
)
from graph_skill_runtime.core.parser import parse_markdown_parts
from graph_skill_runtime.domain.models import (
    ArtifactRequest,
    CompareCandidate,
    InputBinding,
    NodeOverride,
    PhaseAddress,
    RunPreset,
)
from graph_skill_runtime.migration.atomic_publish import publish_directory_no_replace

_LEGACY_GRAPH_FIELDS = frozenset(
    {"schema_version", "name", "description", "llm_role", "io", "phases", "iterate"}
)
_PHASE_FILES = ("LOGIC.md", "SUBGRAPH.md", "SKILL.md")
_RESOURCE_DIRS = ("references", "examples", "scripts", "assets", "tools")
_PHASE_TAG_RE = re.compile(r"<phase\b([^>]*)>(.*?)</phase>", re.IGNORECASE | re.DOTALL)
_DEPENDS_RE = re.compile(r"\bdepends_on\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)


class MigrationDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source_path: str | None = None
    field_path: str | None = None


class MigrationFileMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    destination: str
    kind: Literal["skill", "graph", "phase", "resource", "config"]
    graph_id: str | None = None
    phase_id: str | None = None


class ArtifactMigration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_index: int = Field(ge=0)
    normalized_definition: dict[str, JsonValue]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: str


class ConfigDisposition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_field: str
    owner: Literal["portable", "preset", "studio-adapter", "report"]
    destination_field: str | None = None


class MigrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["gskill.migration-report.v1"] = "gskill.migration-report.v1"
    status: Literal["completed", "failed"]
    source: str
    destination: str
    preset_id: str
    converter_version: str
    file_mappings: tuple[MigrationFileMapping, ...] = ()
    graph_references: dict[str, str] = Field(default_factory=dict)
    artifact_mappings: tuple[ArtifactMigration, ...] = ()
    config_dispositions: tuple[ConfigDisposition, ...] = ()
    diagnostics: tuple[MigrationDiagnostic, ...] = ()


class MigrationFailure(ValueError):
    """A preflight or staged validation failure with a machine-readable report."""

    def __init__(self, report: MigrationReport) -> None:
        self.report = report
        message = report.diagnostics[0].message if report.diagnostics else "migration failed"
        super().__init__(message)


class _MigrationProblem(ValueError):
    def __init__(self, code: str, message: str, *, source: Path | None = None, field: str | None = None) -> None:
        self.diagnostic = MigrationDiagnostic(
            code=code,
            message=message,
            source_path=str(source) if source is not None else None,
            field_path=field,
        )
        super().__init__(message)


@dataclass(frozen=True)
class _LegacyPhase:
    phase_id: str
    mode: Literal["logic", "subgraph", "agent"]
    source_file: Path
    frontmatter: dict[str, Any]
    body: str


@dataclass(frozen=True)
class _LegacyGraph:
    source_root: Path
    graph_id: str
    description: str
    llm_role: str | None
    io: dict[str, Any]
    iterate: dict[str, Any] | None
    phases: tuple[GraphPhaseRef, ...]
    documents: tuple[_LegacyPhase, ...]
    local_references: tuple[str, ...]


@dataclass(frozen=True)
class _MigrationPlan:
    source: Path
    destination: Path
    root_graph: _LegacyGraph
    registry_graphs: tuple[_LegacyGraph, ...]
    reference_ids: dict[str, str]
    artifacts: tuple[ArtifactDeclaration, ...]
    artifact_mappings: tuple[ArtifactMigration, ...]
    preset: RunPreset | None
    config_dispositions: tuple[ConfigDisposition, ...]
    preset_id: str
    runtime_config_source: Path | None


def _converter_version() -> str:
    try:
        return version("graph-skill-runtime")
    except PackageNotFoundError:
        return "0+local"


def _plain_data(value: Any) -> Any:
    """Detach authored YAML values from parser-specific container classes."""

    if isinstance(value, Mapping):
        return {str(key): _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    if isinstance(value, str):
        return str(value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def _problem(
    code: str,
    message: str,
    *,
    source: Path | None = None,
    field: str | None = None,
) -> NoReturn:
    raise _MigrationProblem(code, message, source=source, field=field)


def _normalize_graph_id(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        normalized = "graph"
    if len(normalized) > 64:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        normalized = f"{normalized[:55].rstrip('-')}-{digest}"
    if re.fullmatch(GRAPH_ID_PATTERN, normalized) is None:
        _problem("GSKILL_MIGRATION_GRAPH_ID_INVALID", f"cannot normalize graph id from {value!r}")
    return normalized


def _legacy_phase_refs(graph_path: Path, body: str, declared: list[str]) -> tuple[GraphPhaseRef, ...]:
    raw_refs: list[tuple[str, tuple[str, ...], bool]] = []
    for match in _PHASE_TAG_RE.finditer(body):
        phase_id = match.group(2).strip()
        depends_match = _DEPENDS_RE.search(match.group(1))
        if depends_match is None:
            _problem(
                "GSKILL_MIGRATION_TOPOLOGY_INVALID",
                f"legacy phase {phase_id!r} has no explicit depends_on",
                source=graph_path,
                field="phases",
            )
        dependencies = tuple(
            item for item in re.split(r"[\s,]+", depends_match.group(2).strip()) if item
        )
        output = re.search(r"(?:^|\s)output(?:\s|$|=)", match.group(1)) is not None
        raw_refs.append((phase_id, dependencies, output))

    body_ids = [item[0] for item in raw_refs]
    if body_ids != declared:
        _problem(
            "GSKILL_MIGRATION_TOPOLOGY_INVALID",
            "legacy frontmatter phases and body phase order must match exactly",
            source=graph_path,
            field="phases",
        )
    if not any(item[2] for item in raw_refs):
        upstream_ids = {dependency for _, dependencies, _ in raw_refs for dependency in dependencies}
        raw_refs = [
            (phase_id, dependencies, phase_id not in upstream_ids)
            for phase_id, dependencies, _ in raw_refs
        ]
    try:
        return tuple(
            GraphPhaseRef(id=phase_id, depends_on=dependencies, output=output)
            for phase_id, dependencies, output in raw_refs
        )
    except ValidationError as exc:
        _problem(
            "GSKILL_MIGRATION_TOPOLOGY_INVALID",
            f"legacy topology cannot be represented by portable v1: {exc}",
            source=graph_path,
            field="phases",
        )


def _legacy_phase_document(source_root: Path, phase_id: str) -> tuple[_LegacyPhase, list[str]]:
    phase_dir = source_root / "phases" / phase_id
    matches = [phase_dir / filename for filename in _PHASE_FILES if (phase_dir / filename).is_file()]
    if len(matches) != 1:
        _problem(
            "GSKILL_MIGRATION_PHASE_INVENTORY_INVALID",
            f"legacy phase {phase_id!r} must contain exactly one of {', '.join(_PHASE_FILES)}",
            source=phase_dir,
        )
    phase_file = matches[0]
    phase_frontmatter, phase_body, _ = parse_markdown_parts(phase_file)
    references: list[str] = []
    mode: Literal["logic", "subgraph", "agent"]
    if phase_file.name == "LOGIC.md":
        mode = "logic"
    elif phase_file.name == "SUBGRAPH.md":
        mode = "subgraph"
        path_value = phase_frontmatter.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            _problem(
                "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
                f"legacy subgraph phase {phase_id!r} has no path",
                source=phase_file,
                field="path",
            )
        references.append(path_value)
    else:
        mode = "agent"
        raw_subgraphs = phase_frontmatter.get("subgraphs", [])
        if not isinstance(raw_subgraphs, list):
            _problem(
                "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
                "legacy agent subgraphs must be a list",
                source=phase_file,
                field="subgraphs",
            )
        for item in raw_subgraphs:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                _problem(
                    "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
                    "every legacy agent subgraph requires a path",
                    source=phase_file,
                    field="subgraphs",
                )
            references.append(str(item["path"]))
    return (
        _LegacyPhase(
            phase_id=phase_id,
            mode=mode,
            source_file=phase_file,
            frontmatter=phase_frontmatter,
            body=phase_body,
        ),
        references,
    )


def _legacy_phase_documents(
    source_root: Path, declared: list[str]
) -> tuple[tuple[_LegacyPhase, ...], tuple[str, ...]]:
    documents: list[_LegacyPhase] = []
    references: list[str] = []
    for phase_id in declared:
        document, phase_references = _legacy_phase_document(source_root, phase_id)
        documents.append(document)
        references.extend(phase_references)
    return tuple(documents), tuple(dict.fromkeys(references))


def _read_legacy_graph(source_root: Path) -> _LegacyGraph:
    graph_path = source_root / "GRAPH.md"
    if not graph_path.is_file():
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "source graph has no GRAPH.md", source=graph_path)
    frontmatter, body, _ = parse_markdown_parts(graph_path)
    unknown = sorted(set(frontmatter) - _LEGACY_GRAPH_FIELDS)
    if unknown:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            "legacy GRAPH.md has unsupported fields: " + ", ".join(unknown),
            source=graph_path,
        )
    if frontmatter.get("schema_version") != "v0.3.0":
        _problem(
            "GSKILL_MIGRATION_SOURCE_VERSION_UNSUPPORTED",
            "source GRAPH.md schema_version must be v0.3.0",
            source=graph_path,
            field="schema_version",
        )
    legacy_name = frontmatter.get("name")
    if not isinstance(legacy_name, str) or not legacy_name.strip():
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "legacy graph name is required", source=graph_path)
    declared = frontmatter.get("phases")
    if not isinstance(declared, list) or not declared or not all(isinstance(item, str) for item in declared):
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "legacy phases must be list[str]", source=graph_path)
    refs = _legacy_phase_refs(graph_path, body, cast(list[str], declared))

    documents, local_references = _legacy_phase_documents(source_root, cast(list[str], declared))

    io = frontmatter.get("io")
    if not isinstance(io, dict):
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "legacy graph io is required", source=graph_path)
    description_raw = frontmatter.get("description")
    description = (
        description_raw.strip()
        if isinstance(description_raw, str) and description_raw.strip()
        else f"Migrated {legacy_name.strip()} graph."
    )
    llm_role = frontmatter.get("llm_role")
    if llm_role is not None and (not isinstance(llm_role, str) or not llm_role.strip()):
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "llm_role must be a non-empty string", source=graph_path)
    iterate = frontmatter.get("iterate")
    if iterate is not None and not isinstance(iterate, dict):
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "iterate must be an object", source=graph_path)
    return _LegacyGraph(
        source_root=source_root,
        graph_id=_normalize_graph_id(legacy_name),
        description=description,
        llm_role=llm_role,
        io=io,
        iterate=cast(dict[str, Any] | None, iterate),
        phases=refs,
        documents=documents,
        local_references=local_references,
    )


def _resolved_local_graph(source: Path, graph_root: Path, value: str) -> Path:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (graph_root / candidate).resolve()
    try:
        resolved.relative_to(source)
    except ValueError:
        _problem(
            "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
            f"legacy graph reference {value!r} escapes source root",
            source=graph_root,
            field="path",
        )
    if not resolved.is_dir() or not (resolved / "GRAPH.md").is_file():
        _problem(
            "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
            f"legacy graph reference {value!r} does not resolve to a v0.3 graph",
            source=graph_root,
            field="path",
        )
    return resolved


def _artifact_candidate(stem: str) -> str:
    normalized = unicodedata.normalize("NFC", stem).strip().lower()
    candidate = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "artifact"
    if candidate[0].isdigit():
        candidate = f"artifact-{candidate}"
    return candidate


def _normalized_artifact(
    raw: object,
    *,
    index: int,
    source_path: Path,
) -> tuple[dict[str, JsonValue], str, str, str]:
    if not isinstance(raw, dict):
        _problem(
            "GSKILL_MIGRATION_ARTIFACT_INVALID",
            f"artifact at index {index} must be an object",
            source=source_path,
            field=f"artifacts.{index}",
        )
    unknown = sorted(set(raw) - {"stem", "fields", "mode", "format"})
    if unknown:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            f"artifact at index {index} has unknown fields: {', '.join(unknown)}",
            source=source_path,
            field=f"artifacts.{index}",
        )
    stem = raw.get("stem")
    fields = raw.get("fields")
    if not isinstance(stem, str) or not stem.strip():
        _problem(
            "GSKILL_MIGRATION_ARTIFACT_INVALID",
            f"artifact at index {index} requires a non-empty stem",
            source=source_path,
            field=f"artifacts.{index}.stem",
        )
    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) for item in fields):
        _problem(
            "GSKILL_MIGRATION_ARTIFACT_INVALID",
            f"artifact at index {index} requires non-empty string fields",
            source=source_path,
            field=f"artifacts.{index}.fields",
        )
    normalized: dict[str, JsonValue] = {
        "stem": unicodedata.normalize("NFC", stem).strip(),
        "fields": [unicodedata.normalize("NFC", item).strip() for item in fields],
        "mode": raw.get("mode", "single"),
        "format": raw.get("format", "json"),
    }
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return normalized, canonical, digest, _artifact_candidate(stem)


def _artifact_declarations(
    raw_artifacts: object,
    *,
    source_path: Path,
) -> tuple[tuple[ArtifactDeclaration, ...], tuple[ArtifactMigration, ...]]:
    if raw_artifacts is None:
        return (), ()
    if not isinstance(raw_artifacts, list):
        _problem(
            "GSKILL_MIGRATION_ARTIFACT_INVALID",
            "runtime_config artifacts must be a list",
            source=source_path,
            field="artifacts",
        )

    normalized_rows: list[dict[str, JsonValue]] = []
    canonical_rows: list[str] = []
    hashes: list[str] = []
    candidates: list[str] = []
    for index, raw in enumerate(raw_artifacts):
        normalized, canonical, digest, candidate = _normalized_artifact(
            raw, index=index, source_path=source_path
        )
        normalized_rows.append(normalized)
        canonical_rows.append(canonical)
        hashes.append(digest)
        candidates.append(candidate)

    duplicates = sorted({row for row in canonical_rows if canonical_rows.count(row) > 1})
    if duplicates:
        _problem(
            "GSKILL_MIGRATION_ARTIFACT_DUPLICATE",
            "runtime_config contains duplicate artifact definitions",
            source=source_path,
            field="artifacts",
        )

    candidate_counts = {candidate: candidates.count(candidate) for candidate in set(candidates)}
    prefix_length = 8
    while True:
        artifact_ids = [
            candidate
            if candidate_counts[candidate] == 1
            else f"{candidate}-{digest[:prefix_length]}"
            for candidate, digest in zip(candidates, hashes, strict=True)
        ]
        if len(set(artifact_ids)) == len(artifact_ids):
            break
        prefix_length += 4
        if prefix_length > 64:
            _problem(
                "GSKILL_MIGRATION_ARTIFACT_ID_COLLISION",
                "artifact ids remain ambiguous after using the full definition hash",
                source=source_path,
                field="artifacts",
            )

    declarations: list[ArtifactDeclaration] = []
    mappings: list[ArtifactMigration] = []
    for index, (normalized, digest, artifact_id) in enumerate(
        zip(normalized_rows, hashes, artifact_ids, strict=True)
    ):
        try:
            declaration = ArtifactDeclaration(
                artifact_id=artifact_id,
                stem=cast(str, normalized["stem"]),
                fields=tuple(cast(list[str], normalized["fields"])),
                mode=cast(Any, normalized["mode"]),
                format=cast(Any, normalized["format"]),
            )
        except ValidationError as exc:
            _problem(
                "GSKILL_MIGRATION_ARTIFACT_INVALID",
                f"artifact at index {index} is invalid after normalization: {exc}",
                source=source_path,
                field=f"artifacts.{index}",
            )
        declarations.append(declaration)
        mappings.append(
            ArtifactMigration(
                source_index=index,
                normalized_definition=normalized,
                sha256=digest,
                artifact_id=artifact_id,
            )
        )
    return tuple(declarations), tuple(mappings)


def _mapping(value: object, *, name: str, source: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            f"{name} must be an object",
            source=source,
            field=name,
        )
    return cast(dict[str, Any], value)


def _has_values(value: object) -> bool:
    if isinstance(value, dict):
        return any(_has_values(item) for item in value.values())
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "", False)


def _phase_address(graph_id: str, phase_id: str, known_phases: set[str], source: Path) -> PhaseAddress:
    if phase_id not in known_phases:
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            f"runtime config references unknown root phase {phase_id!r}",
            source=source,
        )
    return PhaseAddress(graph_id=graph_id, phase_id=phase_id)


def _migrated_inputs(
    document: dict[str, Any],
    *,
    root_graph: _LegacyGraph,
    source: Path,
) -> tuple[dict[str, JsonValue], list[InputBinding]]:
    inputs_doc = _mapping(document.get("inputs", {}), name="inputs", source=source)
    unknown_inputs = sorted(
        set(inputs_doc) - {"import_root", "manifest", "active", "removed", "conflicts"}
    )
    if unknown_inputs:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            "runtime inputs has unknown fields: " + ", ".join(unknown_inputs),
            source=source,
            field="inputs",
        )
    if _has_values(inputs_doc.get("conflicts", {})):
        _problem(
            "GSKILL_MIGRATION_CONFIG_CONFLICT",
            "runtime config contains unresolved Studio input conflicts",
            source=source,
            field="inputs.conflicts",
        )
    active = _mapping(inputs_doc.get("active", {}), name="inputs.active", source=source)
    root_inputs = _mapping(active.get("root", {}), name="inputs.active.root", source=source)
    phase_inputs = _mapping(active.get("phases", {}), name="inputs.active.phases", source=source)
    known_phases = {phase.id for phase in root_graph.phases}
    bindings: list[InputBinding] = []
    for phase_id, raw_fields in sorted(phase_inputs.items()):
        fields = _mapping(raw_fields, name=f"inputs.active.phases.{phase_id}", source=source)
        address = _phase_address(root_graph.graph_id, phase_id, known_phases, source)
        bindings.extend(
            InputBinding(address=address, field=field_name, value=cast(JsonValue, value))
            for field_name, value in sorted(fields.items())
        )
    return cast(dict[str, JsonValue], root_inputs), bindings


def _llm_nodes(llm: dict[str, Any], field: str, *, source: Path) -> dict[str, Any]:
    container = _mapping(llm.get(field, {}), name=f"llm.{field}", source=source)
    unknown = sorted(set(container) - {"nodes"})
    if unknown:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            f"llm.{field} has unknown fields: {', '.join(unknown)}",
            source=source,
            field=f"llm.{field}",
        )
    return _mapping(container.get("nodes", {}), name=f"llm.{field}.nodes", source=source)


def _migrated_node_overrides(
    llm: dict[str, Any],
    *,
    root_graph: _LegacyGraph,
    source: Path,
) -> list[NodeOverride]:
    node_params = _llm_nodes(llm, "node_params", source=source)
    custom_params = _llm_nodes(llm, "custom_params", source=source)
    known_phases = {phase.id for phase in root_graph.phases}
    overrides: list[NodeOverride] = []
    for phase_id in sorted(set(node_params) | set(custom_params)):
        address = _phase_address(root_graph.graph_id, phase_id, known_phases, source)
        params = dict(_mapping(node_params.get(phase_id, {}), name=f"node_params.{phase_id}", source=source))
        custom = _mapping(custom_params.get(phase_id, {}), name=f"custom_params.{phase_id}", source=source)
        timeout = params.pop("timeout_seconds", None)
        overrides.append(
            NodeOverride(
                address=address,
                timeout_seconds=cast(float | None, timeout),
                custom_params=cast(dict[str, JsonValue], {**params, **custom}),
            )
        )
    return overrides


def _migrated_compare_candidates(
    llm: dict[str, Any],
    *,
    root_graph: _LegacyGraph,
    source: Path,
) -> list[CompareCandidate]:
    compare_nodes = _llm_nodes(llm, "compare_candidates", source=source)
    known_phases = {phase.id for phase in root_graph.phases}
    converted: list[CompareCandidate] = []
    for phase_id, raw_candidates in sorted(compare_nodes.items()):
        address = _phase_address(root_graph.graph_id, phase_id, known_phases, source)
        if not isinstance(raw_candidates, list):
            _problem(
                "GSKILL_MIGRATION_CONFIG_INVALID",
                f"compare candidates for {phase_id!r} must be a list",
                source=source,
            )
        for index, raw_candidate in enumerate(raw_candidates):
            candidate = _mapping(
                raw_candidate,
                name=f"compare_candidates.{phase_id}.{index}",
                source=source,
            )
            unknown = sorted(set(candidate) - {"candidate_id", "id", "model_override", "model"})
            if unknown:
                _problem(
                    "GSKILL_MIGRATION_UNKNOWN_FIELD",
                    f"compare candidate has unknown fields: {', '.join(unknown)}",
                    source=source,
                )
            candidate_id = candidate.get("candidate_id", candidate.get("id"))
            if not isinstance(candidate_id, str):
                _problem(
                    "GSKILL_MIGRATION_CONFIG_INVALID",
                    "compare candidate requires candidate_id",
                    source=source,
                )
            model = candidate.get("model_override", candidate.get("model"))
            converted.append(
                CompareCandidate(
                    address=address,
                    candidate_id=candidate_id,
                    model_override=model if isinstance(model, str) else None,
                )
            )
    return converted


def _migrated_breakpoints(
    document: dict[str, Any],
    *,
    root_graph: _LegacyGraph,
    source: Path,
) -> list[PhaseAddress]:
    raw_breakpoints = document.get("breakpoints", [])
    if not isinstance(raw_breakpoints, list):
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            "breakpoints must be a list",
            source=source,
            field="breakpoints",
        )
    known_phases = {phase.id for phase in root_graph.phases}
    breakpoints: list[PhaseAddress] = []
    for raw_breakpoint in raw_breakpoints:
        breakpoint_phase_id: object = raw_breakpoint if isinstance(raw_breakpoint, str) else None
        if isinstance(raw_breakpoint, dict):
            breakpoint_phase_id = raw_breakpoint.get("phase_id") or raw_breakpoint.get("node_id")
        if not isinstance(breakpoint_phase_id, str):
            _problem(
                "GSKILL_MIGRATION_CONFIG_INVALID",
                "each breakpoint must identify a root phase",
                source=source,
                field="breakpoints",
            )
        breakpoints.append(
            _phase_address(root_graph.graph_id, breakpoint_phase_id, known_phases, source)
        )
    return breakpoints


def _runtime_preset(
    runtime_config: Path | None,
    *,
    root_graph: _LegacyGraph,
    preset_id: str,
) -> tuple[
    tuple[ArtifactDeclaration, ...],
    tuple[ArtifactMigration, ...],
    RunPreset | None,
    tuple[ConfigDisposition, ...],
]:
    if runtime_config is None:
        return (), (), None, ()
    try:
        document = json.loads(runtime_config.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            f"cannot read legacy runtime config: {exc}",
            source=runtime_config,
        )
    if not isinstance(document, dict) or document.get("schema_version") != "studio.runtime_config.v2":
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            "runtime config schema_version must be studio.runtime_config.v2",
            source=runtime_config,
            field="schema_version",
        )
    unknown_top = sorted(
        set(document) - {"schema_version", "inputs", "llm", "breakpoints", "artifacts"}
    )
    if unknown_top:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            "runtime config has unknown top-level fields: " + ", ".join(unknown_top),
            source=runtime_config,
        )

    root_inputs, bindings = _migrated_inputs(
        document, root_graph=root_graph, source=runtime_config
    )
    llm = _mapping(document.get("llm", {}), name="llm", source=runtime_config)
    unknown_llm = sorted(set(llm) - {"node_params", "compare_candidates", "custom_params"})
    if unknown_llm:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            "runtime llm has unknown fields: " + ", ".join(unknown_llm),
            source=runtime_config,
            field="llm",
        )
    node_overrides = _migrated_node_overrides(llm, root_graph=root_graph, source=runtime_config)
    compare_candidates = _migrated_compare_candidates(
        llm, root_graph=root_graph, source=runtime_config
    )
    breakpoints = _migrated_breakpoints(
        document, root_graph=root_graph, source=runtime_config
    )

    artifacts, artifact_mappings = _artifact_declarations(
        document.get("artifacts", []), source_path=runtime_config
    )
    try:
        preset = RunPreset(
            preset_id=preset_id,
            inputs=root_inputs,
            bindings=tuple(bindings),
            breakpoints=tuple(breakpoints),
            node_overrides=tuple(node_overrides),
            compare_candidates=tuple(compare_candidates),
            artifact_requests=tuple(
                ArtifactRequest(artifact_id=artifact.artifact_id) for artifact in artifacts
            ),
        )
    except ValidationError as exc:
        _problem(
            "GSKILL_MIGRATION_CONFIG_INVALID",
            f"runtime config cannot form a safe RunPreset: {exc}",
            source=runtime_config,
        )
    dispositions = (
        ConfigDisposition(
            source_field="inputs.active.root", owner="preset", destination_field="inputs"
        ),
        ConfigDisposition(
            source_field="inputs.active.phases", owner="preset", destination_field="bindings"
        ),
        ConfigDisposition(
            source_field="llm.node_params.nodes", owner="preset", destination_field="node_overrides"
        ),
        ConfigDisposition(
            source_field="llm.custom_params.nodes", owner="preset", destination_field="node_overrides"
        ),
        ConfigDisposition(
            source_field="llm.compare_candidates.nodes",
            owner="preset",
            destination_field="compare_candidates",
        ),
        ConfigDisposition(
            source_field="breakpoints", owner="preset", destination_field="breakpoints"
        ),
        ConfigDisposition(
            source_field="artifacts", owner="portable", destination_field="graph.yaml.artifacts"
        ),
        ConfigDisposition(source_field="inputs.import_root", owner="studio-adapter"),
        ConfigDisposition(source_field="inputs.manifest", owner="studio-adapter"),
        ConfigDisposition(source_field="inputs.removed", owner="studio-adapter"),
        ConfigDisposition(source_field="inputs.conflicts", owner="report"),
    )
    return artifacts, artifact_mappings, preset, dispositions


def _validate_migration_paths(source: Path, destination: Path, preset_id: str) -> tuple[Path, Path]:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().resolve(strict=False)
    if not source.is_dir():
        _problem("GSKILL_MIGRATION_SOURCE_INVALID", "SOURCE must be a directory", source=source)
    if source == destination:
        _problem("GSKILL_MIGRATION_DESTINATION_INVALID", "SOURCE and DESTINATION must differ")
    try:
        destination.relative_to(source)
    except ValueError:
        pass
    else:
        _problem(
            "GSKILL_MIGRATION_DESTINATION_INVALID",
            "DESTINATION must not be inside SOURCE",
            source=destination,
        )
    if destination.exists():
        _problem(
            "GSKILL_MIGRATION_DESTINATION_EXISTS",
            "DESTINATION already exists; migration never overwrites it",
            source=destination,
        )
    if re.fullmatch(AGENT_SKILL_NAME_PATTERN, destination.name) is None or len(destination.name) > 64:
        _problem(
            "GSKILL_MIGRATION_DESTINATION_INVALID",
            "DESTINATION basename must be a valid Agent Skills name",
            source=destination,
        )
    if re.fullmatch(r"^[A-Za-z][A-Za-z0-9_.-]*$", preset_id) is None:
        _problem("GSKILL_MIGRATION_PRESET_INVALID", f"invalid preset id {preset_id!r}")
    return source, destination


def _build_plan(
    source: Path,
    destination: Path,
    *,
    runtime_config: Path | None,
    preset_id: str,
) -> _MigrationPlan:
    source, destination = _validate_migration_paths(source, destination, preset_id)
    root_graph = _read_legacy_graph(source)

    reference_roots: dict[str, Path] = {}
    for reference in root_graph.local_references:
        reference_roots[reference] = _resolved_local_graph(source, root_graph.source_root, reference)
    registry_graphs: list[_LegacyGraph] = []
    graph_by_root: dict[Path, _LegacyGraph] = {}
    for graph_root in dict.fromkeys(reference_roots.values()):
        graph = _read_legacy_graph(graph_root)
        if graph.local_references:
            _problem(
                "GSKILL_MIGRATION_NESTED_SUBGRAPH_UNSUPPORTED",
                f"legacy child graph {graph_root} contains nested graph references",
                source=graph_root,
            )
        if (graph_root / "tools").exists():
            _problem(
                "GSKILL_MIGRATION_GRAPH_RESOURCE_UNSUPPORTED",
                "legacy child graph root tools/ cannot be promoted without changing tool scope",
                source=graph_root / "tools",
            )
        registry_graphs.append(graph)
        graph_by_root[graph_root] = graph

    all_graph_ids = [root_graph.graph_id, *(graph.graph_id for graph in registry_graphs)]
    if len(all_graph_ids) != len(set(all_graph_ids)):
        _problem(
            "GSKILL_MIGRATION_GRAPH_ID_COLLISION",
            "legacy graph names normalize to duplicate graph ids",
            source=source,
        )
    reference_ids = {
        legacy_reference: graph_by_root[resolved_root].graph_id
        for legacy_reference, resolved_root in reference_roots.items()
    }

    selected_runtime_config = runtime_config
    if selected_runtime_config is None:
        default_config = source / ".workspace" / "runtime_config.json"
        selected_runtime_config = default_config if default_config.is_file() else None
    elif not selected_runtime_config.is_absolute():
        selected_runtime_config = (Path.cwd() / selected_runtime_config).resolve(strict=False)
    if selected_runtime_config is not None:
        selected_runtime_config = selected_runtime_config.resolve(strict=True)
    artifacts, artifact_mappings, preset, dispositions = _runtime_preset(
        selected_runtime_config,
        root_graph=root_graph,
        preset_id=preset_id,
    )
    return _MigrationPlan(
        source=source,
        destination=destination,
        root_graph=root_graph,
        registry_graphs=tuple(registry_graphs),
        reference_ids=reference_ids,
        artifacts=artifacts,
        artifact_mappings=artifact_mappings,
        preset=preset,
        config_dispositions=dispositions,
        preset_id=preset_id,
        runtime_config_source=selected_runtime_config,
    )


def _render_root_skill(plan: _MigrationPlan) -> str:
    legacy_purpose = " ".join(plan.root_graph.description.split())
    activation_description = (
        f"{legacy_purpose} Use this skill when a request requires its structured graph workflow."
    )
    if len(activation_description) > 1024:
        _problem(
            "GSKILL_MIGRATION_SKILL_METADATA_INVALID",
            "legacy description is too long to form Agent Skills activation metadata",
            source=plan.root_graph.source_root / "GRAPH.md",
            field="description",
        )
    frontmatter = {
        "name": plan.destination.name,
        "description": activation_description,
    }
    body = f"""# {plan.destination.name}

Use this directory as the explicit skill root for every operation.

Prefer the installed Graph Skill Runtime MCP tools (`compile`, `predict`, `run`, `resume`, and
`submit_agent_result`). If MCP is unavailable, use the equivalent installed `gskill` console
subcommands. Consume the structured result and diagnostics. Do not invoke the runtime through
`python -m`, and do not assume installing the runtime registered this business skill.
"""
    return _markdown(frontmatter, body)


def _markdown(frontmatter: dict[str, Any], body: str) -> str:
    rendered = yaml.safe_dump(
        _plain_data(frontmatter),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return f"---\n{rendered}---\n{body.lstrip()}".rstrip() + "\n"


def _portable_graph(graph: _LegacyGraph, *, artifacts: tuple[ArtifactDeclaration, ...]) -> GraphManifest:
    try:
        return GraphManifest.model_validate(
            {
                "schema_version": "gskill.graph.v1",
                "graph_id": graph.graph_id,
                "description": graph.description,
                "llm_role": graph.llm_role,
                "io": graph.io,
                "phases": graph.phases,
                "iterate": graph.iterate,
                "artifacts": artifacts,
            }
        )
    except ValidationError as exc:
        _problem(
            "GSKILL_MIGRATION_GRAPH_INVALID",
            f"legacy graph {graph.source_root} cannot form portable graph.yaml: {exc}",
            source=graph.source_root / "GRAPH.md",
        )


def _resolved_reference_id(plan: _MigrationPlan, graph: _LegacyGraph, value: str) -> str:
    resolved = _resolved_local_graph(plan.source, graph.source_root, value)
    for legacy_value, graph_id in plan.reference_ids.items():
        if _resolved_local_graph(plan.source, plan.root_graph.source_root, legacy_value) == resolved:
            return graph_id
    _problem(
        "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
        f"legacy reference {value!r} is not owned by the root graph reference set",
        source=graph.source_root,
    )


def _rewrite_resource_paths(
    frontmatter: dict[str, Any],
    *,
    graph: _LegacyGraph,
    is_root: bool,
) -> None:
    for field_name in ("references", "examples"):
        declarations = frontmatter.get(field_name, [])
        if not isinstance(declarations, list):
            continue
        for declaration in declarations:
            if not isinstance(declaration, dict) or not isinstance(declaration.get("path"), str):
                continue
            authored_path = declaration["path"]
            parts = PurePosixPath(authored_path).parts
            expected_root = "references" if field_name == "references" else "examples"
            accepted_roots = {expected_root, "refs"} if field_name == "references" else {expected_root}
            if (
                not parts
                or Path(authored_path).is_absolute()
                or "\\" in authored_path
                or any(part in {"", ".", ".."} or ":" in part for part in parts)
                or parts[0] not in accepted_roots
            ):
                _problem(
                    "GSKILL_MIGRATION_RESOURCE_PATH_UNSUPPORTED",
                    f"legacy {field_name} path {authored_path!r} must be under "
                    f"{sorted(accepted_roots)!r} and remain inside its graph root",
                    source=graph.source_root,
                    field=field_name,
                )
            source_file = graph.source_root.joinpath(*parts)
            if source_file.is_symlink() or not source_file.is_file():
                _problem(
                    "GSKILL_MIGRATION_RESOURCE_PATH_UNSUPPORTED",
                    f"legacy {field_name} path {authored_path!r} is not a regular file",
                    source=source_file,
                    field=field_name,
                )
            portable_parts = (expected_root, *parts[1:])
            portable_path = PurePosixPath(*portable_parts).as_posix()
            declaration["path"] = (
                portable_path
                if is_root
                else f"graphs/{graph.graph_id}/{portable_path}"
            )


def _rewrite_subgraph_phase(
    plan: _MigrationPlan,
    graph: _LegacyGraph,
    phase: _LegacyPhase,
    data: dict[str, Any],
) -> None:
    path_value = data.pop("path", None)
    if not isinstance(path_value, str):
        _problem(
            "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
            "SUBGRAPH.md path disappeared during conversion",
            source=phase.source_file,
        )
    data["graph"] = _resolved_reference_id(plan, graph, path_value)


def _rewrite_agent_phase(
    plan: _MigrationPlan,
    graph: _LegacyGraph,
    phase: _LegacyPhase,
    data: dict[str, Any],
) -> None:
    subgraphs = data.get("subgraphs", [])
    if isinstance(subgraphs, list):
        rewritten: list[dict[str, Any]] = []
        for raw in subgraphs:
            if not isinstance(raw, dict):
                _problem(
                    "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
                    "agent subgraph declaration must be an object",
                    source=phase.source_file,
                )
            item = dict(raw)
            path_value = item.pop("path", None)
            if not isinstance(path_value, str):
                _problem(
                    "GSKILL_MIGRATION_GRAPH_REFERENCE_INVALID",
                    "agent subgraph declaration requires path",
                    source=phase.source_file,
                )
            item["graph"] = _resolved_reference_id(plan, graph, path_value)
            rewritten.append(item)
        data["subgraphs"] = rewritten
    raw_subagents = data.get("subagents", [])
    if not isinstance(raw_subagents, list):
        return
    for subagent in raw_subagents:
        target = subagent.get("target_skill") if isinstance(subagent, dict) else None
        if not isinstance(target, str) or re.fullmatch(AGENT_SKILL_NAME_PATTERN, target) is None:
            _problem(
                "GSKILL_MIGRATION_EXTERNAL_SKILL_INVALID",
                "external subagent target_skill must already be a valid Agent Skills name",
                source=phase.source_file,
                field="subagents",
            )


def _portable_phase_frontmatter(
    plan: _MigrationPlan,
    graph: _LegacyGraph,
    phase: _LegacyPhase,
) -> dict[str, Any]:
    data = dict(phase.frontmatter)
    if "batch" in data:
        _problem(
            "GSKILL_MIGRATION_UNKNOWN_FIELD",
            "legacy phase batch cannot be migrated without changing its execution contract; use iterate",
            source=phase.source_file,
            field="batch",
        )
    data.pop("mode", None)
    data.pop("schema_version", None)
    data.pop("phase_id", None)
    data.pop("graph_skill_id", None)
    data.setdefault("name", phase.phase_id)
    if phase.mode == "subgraph":
        _rewrite_subgraph_phase(plan, graph, phase, data)
    elif phase.mode == "agent":
        _rewrite_agent_phase(plan, graph, phase, data)
    _rewrite_resource_paths(data, graph=graph, is_root=graph.source_root == plan.source)
    return data


def _phase_model_validates(
    phase: _LegacyPhase,
    frontmatter: dict[str, Any],
) -> None:
    from graph_skill_runtime.core.loader import build_phase_document

    filename = {"logic": "LOGIC.md", "subgraph": "SUBGRAPH.md", "agent": "AGENT.md"}[phase.mode]
    try:
        build_phase_document(
            phase.phase_id,
            phase.source_file.with_name(filename),
            phase.mode,
            frontmatter,
            phase.body,
        )
    except Exception as exc:
        _problem(
            "GSKILL_MIGRATION_PHASE_INVALID",
            f"phase {phase.phase_id!r} cannot form portable {filename}: {exc}",
            source=phase.source_file,
        )


def _copy_entry(source: Path, destination: Path) -> None:
    if source.is_symlink():
        _problem(
            "GSKILL_MIGRATION_SYMLINK_UNSUPPORTED",
            "migration does not copy symlinks",
            source=source,
        )
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _render_graph(
    plan: _MigrationPlan,
    graph: _LegacyGraph,
    destination_graph: Path,
    *,
    artifacts: tuple[ArtifactDeclaration, ...],
    mappings: list[MigrationFileMapping],
) -> None:
    bundle_root = destination_graph.parents[1] if destination_graph.parent.name == "graphs" else destination_graph
    _write_text(destination_graph / "graph.yaml", serialize_graph(_portable_graph(graph, artifacts=artifacts)))
    mappings.append(
        MigrationFileMapping(
            source=(graph.source_root / "GRAPH.md").relative_to(plan.source).as_posix(),
            destination=(destination_graph / "graph.yaml").relative_to(bundle_root).as_posix(),
            kind="graph",
            graph_id=graph.graph_id,
        )
    )
    for phase in graph.documents:
        destination_phase = destination_graph / "phases" / phase.phase_id
        destination_phase.mkdir(parents=True, exist_ok=False)
        portable_frontmatter = _portable_phase_frontmatter(plan, graph, phase)
        _phase_model_validates(phase, portable_frontmatter)
        target_name = {"logic": "LOGIC.md", "subgraph": "SUBGRAPH.md", "agent": "AGENT.md"}[phase.mode]
        for child in phase.source_file.parent.iterdir():
            if child.name in _PHASE_FILES:
                continue
            _copy_entry(child, destination_phase / child.name)
        _write_text(destination_phase / target_name, _markdown(portable_frontmatter, phase.body))
        mappings.append(
            MigrationFileMapping(
                source=phase.source_file.relative_to(plan.source).as_posix(),
                destination=(destination_phase / target_name).relative_to(bundle_root).as_posix(),
                kind="phase",
                graph_id=graph.graph_id,
                phase_id=phase.phase_id,
            )
        )
    if graph.source_root != plan.source:
        for resource_name in ("references", "examples", "scripts", "assets"):
            source_resource = graph.source_root / resource_name
            if source_resource.exists():
                _copy_entry(source_resource, destination_graph / resource_name)
        legacy_refs = graph.source_root / "refs"
        if legacy_refs.exists():
            if (graph.source_root / "references").exists():
                _problem(
                    "GSKILL_MIGRATION_RESOURCE_COLLISION",
                    "legacy graph contains both refs/ and references/ resource owners",
                    source=graph.source_root,
                )
            _copy_entry(legacy_refs, destination_graph / "references")


def _project_config_text(preset: RunPreset) -> str:
    preset_data = preset.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"schema_version", "kind", "preset_id"},
    )
    document = {
        "schema_version": "gskill.config.v1",
        "presets": {preset.preset_id: preset_data},
    }
    return tomli_w.dumps(document)


def _render_plan(plan: _MigrationPlan, stage: Path) -> tuple[MigrationFileMapping, ...]:
    mappings: list[MigrationFileMapping] = [
        MigrationFileMapping(source="GRAPH.md", destination="SKILL.md", kind="skill")
    ]
    _write_text(stage / "SKILL.md", _render_root_skill(plan))
    _render_graph(
        plan,
        plan.root_graph,
        stage,
        artifacts=plan.artifacts,
        mappings=mappings,
    )
    for graph in plan.registry_graphs:
        _render_graph(
            plan,
            graph,
            stage / "graphs" / graph.graph_id,
            artifacts=(),
            mappings=mappings,
        )
    for resource_name in _RESOURCE_DIRS:
        source_resource = plan.source / resource_name
        if source_resource.exists():
            _copy_entry(source_resource, stage / resource_name)
            mappings.append(
                MigrationFileMapping(
                    source=resource_name,
                    destination=resource_name,
                    kind="resource",
                )
            )
    legacy_refs = plan.source / "refs"
    if legacy_refs.exists():
        if (plan.source / "references").exists():
            _problem(
                "GSKILL_MIGRATION_RESOURCE_COLLISION",
                "legacy root contains both refs/ and references/ resource owners",
                source=plan.source,
            )
        _copy_entry(legacy_refs, stage / "references")
        mappings.append(
            MigrationFileMapping(
                source="refs",
                destination="references",
                kind="resource",
            )
        )
    if plan.preset is not None:
        _write_text(stage / "gskill.toml", _project_config_text(plan.preset))
        assert plan.runtime_config_source is not None
        try:
            config_source = plan.runtime_config_source.relative_to(plan.source).as_posix()
        except ValueError:
            config_source = plan.runtime_config_source.as_posix()
        mappings.append(
            MigrationFileMapping(
                source=config_source,
                destination="gskill.toml",
                kind="config",
            )
        )
    return tuple(mappings)


def _report(
    plan: _MigrationPlan,
    *,
    status: Literal["completed", "failed"],
    mappings: tuple[MigrationFileMapping, ...] = (),
    diagnostics: tuple[MigrationDiagnostic, ...] = (),
) -> MigrationReport:
    return MigrationReport(
        status=status,
        source=str(plan.source),
        destination=str(plan.destination),
        preset_id=plan.preset_id,
        converter_version=_converter_version(),
        file_mappings=mappings,
        graph_references=dict(plan.reference_ids),
        artifact_mappings=plan.artifact_mappings,
        config_dispositions=plan.config_dispositions,
        diagnostics=diagnostics,
    )


def _preset_runtime_input_fields(plan: _MigrationPlan) -> dict[str, set[str]] | None:
    if plan.preset is None:
        return None
    fields: dict[str, set[str]] = {}
    for binding in plan.preset.bindings:
        if binding.address.graph_id == plan.root_graph.graph_id:
            fields.setdefault(binding.address.phase_id, set()).add(binding.field)
    return fields or None


def _failure_report(
    source: Path,
    destination: Path,
    preset_id: str,
    diagnostic: MigrationDiagnostic,
) -> MigrationReport:
    return MigrationReport(
        status="failed",
        source=str(source.expanduser().resolve(strict=False)),
        destination=str(destination.expanduser().resolve(strict=False)),
        preset_id=preset_id,
        converter_version=_converter_version(),
        diagnostics=(diagnostic,),
    )


def migrate_studio_skill(
    source: str | Path,
    destination: str | Path,
    *,
    runtime_config: str | Path | None = None,
    preset_id: str = "migrated",
) -> MigrationReport:
    """Convert one legacy source without modifying it or overwriting a destination."""

    source_path = Path(source)
    destination_path = Path(destination)
    try:
        plan = _build_plan(
            source_path,
            destination_path,
            runtime_config=Path(runtime_config) if runtime_config is not None else None,
            preset_id=preset_id,
        )
    except _MigrationProblem as exc:
        raise MigrationFailure(
            _failure_report(source_path, destination_path, preset_id, exc.diagnostic)
        ) from exc

    destination_parent = plan.destination.parent
    destination_parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=".gskill-migrate-", dir=destination_parent)
    ).resolve()
    stage = staging_parent / plan.destination.name
    stage.mkdir()
    try:
        mappings = _render_plan(plan, stage)
        compile_skill(
            stage,
            cache=False,
            skill_resolver=LocalWorkspaceResolver(
                [
                    stage.parent,
                    plan.destination.parent,
                    plan.destination.parent / "skills",
                    plan.source.parent,
                    plan.source.parent / "skills",
                    Path.cwd(),
                    Path.cwd() / "skills",
                ]
            ),
            runtime_input_fields=_preset_runtime_input_fields(plan),
        )
        report = _report(plan, status="completed", mappings=mappings)
        _write_text(
            stage / ".gskill-migration-report.json",
            report.model_dump_json(indent=2) + "\n",
        )
        try:
            publish_directory_no_replace(stage, plan.destination)
        except FileExistsError:
            _problem(
                "GSKILL_MIGRATION_DESTINATION_EXISTS",
                "DESTINATION appeared while migration was staged; migration never overwrites it",
                source=plan.destination,
            )
        return report
    except MigrationFailure:
        raise
    except _MigrationProblem as exc:
        raise MigrationFailure(
            _report(plan, status="failed", diagnostics=(exc.diagnostic,))
        ) from exc
    except Exception as exc:
        diagnostic = MigrationDiagnostic(
            code="GSKILL_MIGRATION_STAGED_VALIDATION_FAILED",
            message=str(exc),
            source_path=str(stage),
        )
        raise MigrationFailure(
            _report(plan, status="failed", diagnostics=(diagnostic,))
        ) from exc
    finally:
        if staging_parent.exists():
            try:
                shutil.rmtree(staging_parent)
            except OSError:
                pass


__all__ = [
    "ArtifactMigration",
    "ConfigDisposition",
    "MigrationDiagnostic",
    "MigrationFailure",
    "MigrationFileMapping",
    "MigrationReport",
    "migrate_studio_skill",
]
