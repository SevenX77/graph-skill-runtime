from __future__ import annotations

import hashlib
import io
import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from graph_skill_runtime.core.authored_text import read_authored_text
from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.parser import parse_markdown_parts
from graph_skill_runtime.core.skill_resolver_protocol import SkillResolverProtocol

logger = logging.getLogger(__name__)


class ArtifactRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    content_hash: str
    store: Literal["ephemeral", "product"]
    version: str | None = None
    manifest_ref: str
    source_map_ref: str

    @field_validator("store")
    @classmethod
    def validate_store(cls, v: Any) -> Literal["ephemeral", "product"]:
        if v not in ("ephemeral", "product"):
            raise ValueError("store must be either 'ephemeral' or 'product'")
        return cast(Literal["ephemeral", "product"], v)


class CompiledArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_ref: ArtifactRef
    execution_fingerprint: str
    source_map_ref: str
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    artifact_bytes: bytes | None = Field(default=None, exclude=True)


class ArtifactBytes(BaseModel):
    model_config = ConfigDict(frozen=True)

    bytes_ref: str
    expected_content_hash: str


def build_compiled_artifact_manifest(
    *,
    compiled: Any,
    artifact_ref: ArtifactRef,
    execution_fingerprint: str,
    diagnostics: list[dict[str, Any]] | None = None,
) -> CompiledArtifactManifest:
    if diagnostics is None:
        diagnostics = []
    return CompiledArtifactManifest(
        artifact_ref=artifact_ref,
        execution_fingerprint=execution_fingerprint,
        source_map_ref=artifact_ref.source_map_ref,
        diagnostics=diagnostics,
    )


def _graph_file(source_path: Path) -> Path:
    return source_path / "graph.yaml"


def _phase_ids_from_graph(graph_text: str) -> list[str]:
    document = yaml.safe_load(graph_text)
    phases = document.get("phases", []) if isinstance(document, dict) else []
    phase_ids: list[str] = []
    if isinstance(phases, list):
        for item in phases:
            if isinstance(item, dict):
                phase_id = item.get("id")
                if isinstance(phase_id, str):
                    phase_ids.append(phase_id)
    return phase_ids


def _phase_line(graph_lines: list[str], phase_id: str) -> int:
    quoted_single = f"- '{phase_id}'"
    quoted_double = f'- "{phase_id}"'
    plain = f"- {phase_id}"
    for index, line in enumerate(graph_lines, start=1):
        stripped = line.strip()
        if stripped in {plain, quoted_single, quoted_double}:
            return index
        if stripped.startswith("- id:") and phase_id in stripped:
            return index
        if stripped.startswith("phases:") and phase_id in stripped:
            return index
    return 1


def _build_source_map(source_path: Path) -> dict[str, Any]:
    graph_path = _graph_file(source_path)
    graph_text = read_authored_text(graph_path)
    graph_lines = graph_text.splitlines()
    graph_rel = graph_path.relative_to(source_path).as_posix()
    nodes: dict[str, Any] = {}
    for phase_id in _phase_ids_from_graph(graph_text):
        line = _phase_line(graph_lines, phase_id)
        nodes[phase_id] = {
            "node_id": phase_id,
            "kind": "phase",
            "source": {
                "path": graph_rel,
                "line": line,
                "span": {
                    "start_line": line,
                    "end_line": line,
                },
            },
        }
    return {
        "schema_version": "mvp1.source_map.v1",
        "nodes": nodes,
    }


def _build_artifact_archive(source_path: Path, relative_paths: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for rel_path in relative_paths:
            zip_info = zipfile.ZipInfo(rel_path)
            zip_info.date_time = (1980, 1, 1, 0, 0, 0)
            zip_info.compress_type = zipfile.ZIP_STORED
            zip_info.external_attr = 0o644 << 16
            archive.writestr(zip_info, (source_path / rel_path).read_bytes())
    return buffer.getvalue()


def _canonical_skill_entry_for_fingerprint(path: Path) -> bytes:
    frontmatter, body, _ = parse_markdown_parts(path)
    stable_frontmatter = dict(frontmatter)
    metadata = stable_frontmatter.get("metadata")
    if isinstance(metadata, dict):
        stable_metadata = dict(metadata)
        stable_metadata.pop("ui", None)
        stable_frontmatter["metadata"] = stable_metadata
    canonical_frontmatter = json.dumps(
        stable_frontmatter,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"---\n{canonical_frontmatter}\n---\n{body}".encode()


def _default_artifact_output_root() -> Path:
    return Path(tempfile.gettempdir()) / "graph_skill_runtime" / "artifacts"


def _artifact_relative_paths(source_path: Path) -> list[str]:
    relative_paths: list[str] = []
    for path in source_path.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_path)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        if path.suffix in (".pyc", ".pyo", ".pyd"):
            continue
        relative_paths.append(relative.as_posix())
    return sorted(relative_paths)


def _fingerprint_file_content(source_path: Path, relative_path: str) -> bytes:
    path = source_path / relative_path
    content = path.read_bytes()
    if relative_path == "SKILL.md":
        try:
            return _canonical_skill_entry_for_fingerprint(path)
        except Exception as exc:
            logger.warning(
                "compile_artifact_fingerprint_skill_entry_fallback rel_path=%s error=%s",
                relative_path,
                exc,
            )
    elif relative_path.endswith("graph.yaml"):
        try:
            graph_document = yaml.safe_load(content.decode("utf-8"))
            return json.dumps(graph_document, ensure_ascii=False, sort_keys=True).encode()
        except Exception as exc:
            logger.warning(
                "compile_artifact_fingerprint_graph_fallback rel_path=%s error=%s",
                relative_path,
                exc,
            )
    return content


def _execution_fingerprint(
    source_path: Path,
    relative_paths: list[str],
    runtime_config_fingerprint: str | None,
) -> str:
    hasher = hashlib.sha256()
    for relative_path in relative_paths:
        hasher.update(relative_path.encode())
        content = _fingerprint_file_content(source_path, relative_path)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    if runtime_config_fingerprint:
        runtime_bytes = runtime_config_fingerprint.encode()
        hasher.update(b"runtime_config")
        hasher.update(len(runtime_bytes).to_bytes(8, "big"))
        hasher.update(runtime_bytes)
    return f"sha256:{hasher.hexdigest()}"


def compile_artifact(
    *,
    source_root: str | Path,
    skill_resolver: SkillResolverProtocol,
    store: Literal["ephemeral", "product"] = "ephemeral",
    version: str | None = None,
    artifact_output_root: str | Path | None = None,
    runtime_input_fields: dict[str, set[str]] | None = None,
    runtime_config_fingerprint: str | None = None,
) -> CompiledArtifactManifest:
    source_path = Path(source_root)

    # 1. Invoke Engine compiler to validate the skill
    compile_skill(
        source_path,
        cache=False,
        skill_resolver=skill_resolver,
        runtime_input_fields=runtime_input_fields,
    )

    relative_paths = _artifact_relative_paths(source_path)
    artifact_bytes = _build_artifact_archive(source_path, relative_paths)
    content_hash_hex = hashlib.sha256(artifact_bytes).hexdigest()
    content_hash = f"sha256:{content_hash_hex}"
    execution_fingerprint = _execution_fingerprint(
        source_path,
        relative_paths,
        runtime_config_fingerprint,
    )

    objects_root = Path(artifact_output_root) if artifact_output_root is not None else _default_artifact_output_root()
    objects_dir = objects_root / content_hash_hex
    objects_dir.mkdir(parents=True, exist_ok=True)
    source_map_path = objects_dir / "source_map.json"
    manifest_path = objects_dir / "manifest.json"

    artifact_ref = ArtifactRef(
        artifact_id=source_path.name,
        content_hash=content_hash,
        store=store,
        version=version,
        manifest_ref=manifest_path.resolve().as_uri(),
        source_map_ref=source_map_path.resolve().as_uri(),
    )

    manifest = CompiledArtifactManifest(
        artifact_ref=artifact_ref,
        execution_fingerprint=execution_fingerprint,
        source_map_ref=artifact_ref.source_map_ref,
        diagnostics=[],
        artifact_bytes=artifact_bytes,
    )

    source_map_path.write_text(
        json.dumps(_build_source_map(source_path), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return manifest
