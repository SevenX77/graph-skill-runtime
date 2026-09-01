"""Compiled bundle cache for portable gSkill v1."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import uuid
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from graph_skill_runtime.core.loader import CompiledSkill, PhaseDocument
from graph_skill_runtime.core.manifest import GraphManifest, PhaseAST, RootSkillManifest

logger = logging.getLogger(__name__)


def get_cache_dir() -> Path:
    return Path.home() / ".cache" / "graph-skill-runtime-portable-v1"


def compute_cache_key(root: Path, *, schema_version: int) -> str:
    """Key one compiled bundle by its inputs AND by the rules that compiled it.

    ``schema_version`` is the caller's compile-rule identity
    (``compiler.CACHE_SCHEMA_VERSION``); it is passed in rather than imported so
    this module keeps knowing nothing about compile rules. It is required, with
    no default, because a caller that omitted it would silently mint keys that
    outlive the rules behind them — the exact defect the field exists to close.
    """
    root = root.resolve()
    payload = {
        "format": "portable-v1",
        "rules": schema_version,
        "root": str(root),
        "python": list(sys.version_info[:3]),
        "package": _get_graph_skill_runtime_version(),
        "files": _skill_file_metadata(root),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_from_cache(key: str, root: Path) -> CompiledSkill | None:
    cache_file = get_cache_dir() / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        snapshot = json.loads(cache_file.read_text(encoding="utf-8"))
        return _rehydrate_compiled_skill(snapshot, root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("[Cache] Failed to load cached compiled skill %s: %s", key, exc)
        return None


def save_to_cache(key: str, compiled: CompiledSkill) -> None:
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"
    # Write-then-replace, borrowed from CPython's bytecode writer
    # (importlib._bootstrap_external._write_atomic): a plain write_text
    # truncates the destination first, so a concurrent reader sees half a
    # snapshot and a concurrent Windows writer hits a sharing violation.
    # os.replace is atomic within one directory on both POSIX and Windows.
    # Divergence from CPython: a failed replace/cleanup is swallowed — the
    # cache is an optimization, and losing one entry must not fail the
    # compile that already succeeded (Windows can refuse the replace while
    # a reader holds the destination open).
    temp_file = cache_dir / f"{key}.{uuid.uuid4().hex}.tmp"
    temp_file.write_text(
        json.dumps(_dehydrate_compiled_skill(compiled), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    try:
        os.replace(temp_file, cache_file)
    except OSError as exc:
        logger.warning("[Cache] Failed to publish cache entry %s: %s", key, exc)
        try:
            temp_file.unlink()
        except OSError:
            pass


#: File types a compile reads: the markdown documents it parses and the Python
#: modules it imports (validators, logic actions, tools).
_COMPILE_INPUT_SUFFIXES = frozenset({".md", ".py", ".yaml"})


def _is_skipped_dir(name: str) -> bool:
    """Directories a compile never reads, pruned before descending into them.

    Not tidiness — each one is actively harmful in the key. ``.workspace`` holds
    run/predict output that every execution rewrites, so keying on it would
    invalidate the cache after each run. ``.git`` is large enough to make the walk
    itself the dominant cost. ``__pycache__`` mirrors sources the key already
    covers, with mtimes that move on import rather than on edit.
    """
    return name.startswith(".") or name == "__pycache__"


def _collect_skill_files(root: Path) -> list[Path]:
    """Every compile input under the skill root.

    Deliberately over-approximate. An input the key MISSES makes ``compile_skill``
    answer for a tree that is not the one on disk — a wrong answer. An extra file
    in the key only costs a recompile. Build caches that get this right (ccache's
    depfiles, Bazel's declared inputs) all treat an unsound dependency set as a
    correctness bug rather than a tuning knob, and this follows that side.

    Known remaining hole: a subgraph resolved OUTSIDE this root (a linked skill)
    is still not covered, because the resolved set is only known after compiling.
    Closing that needs the loader to report its read-set and the cache snapshot to
    carry it — a separate change. The remaining gap is limited to out-of-root
    external skill links.
    """
    files: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if not _is_skipped_dir(name)]
        base = Path(directory)
        files.extend(
            base / filename
            for filename in filenames
            if Path(filename).suffix in _COMPILE_INPUT_SUFFIXES
        )
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _skill_file_metadata(root: Path) -> list[tuple[str, int, int]]:
    metadata_rows: list[tuple[str, int, int]] = []
    for path in _collect_skill_files(root):
        stat = path.stat()
        metadata_rows.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    return metadata_rows


def _get_graph_skill_runtime_version() -> str:
    try:
        return metadata.version("graph-skill-runtime")
    except metadata.PackageNotFoundError:
        return "0+local"


def _dehydrate_compiled_skill(compiled: CompiledSkill) -> dict[str, Any]:
    registry = compiled.graph_registry or {compiled.manifest.graph_id: compiled}
    if compiled.skill_manifest is None:
        raise ValueError("portable compiled skill has no root Agent Skills manifest")
    return {
        "format": "portable-v1",
        "root_graph_id": compiled.manifest.graph_id,
        "skill_manifest": compiled.skill_manifest.model_dump(mode="json", by_alias=True),
        "graphs": {graph_id: _dehydrate_graph(graph) for graph_id, graph in registry.items()},
    }


def _dehydrate_graph(compiled: CompiledSkill) -> dict[str, Any]:
    return {
        "raw": compiled.raw,
        "manifest": compiled.manifest.model_dump(mode="json"),
        "graph_root": compiled.graph_root.relative_to(compiled.skill_root).as_posix() or ".",
        "nodes": [
            {
                "phase_name": node.phase_name,
                "path": str(node.path),
                "mode": node.mode,
                "frontmatter": node.frontmatter,
                "raw_blocks": node.raw_blocks,
                "ast": node.ast.model_dump(mode="json"),
            }
            for node in compiled.nodes
        ],
        "subagents_by_phase": {
            phase_id: [
                {
                    "parent_phase_id": subagent.parent_phase_id,
                    "name": subagent.name,
                    "target_skill": subagent.target_skill,
                    "description": subagent.description,
                    "root": str(subagent.root),
                    "input_schema": subagent.input_schema,
                    "expected_schema": subagent.expected_schema,
                }
                for subagent in subagents
            ]
            for phase_id, subagents in compiled.subagents_by_phase.items()
        },
        "phase_tokens": {
            phase_id: {
                "phase_id": token.phase_id,
                "raw_text": token.raw_text,
                "line_start": token.line_start,
                "line_end": token.line_end,
                "attrs": token.attrs,
            }
            for phase_id, token in compiled.phase_tokens.items()
        },
    }


def _rehydrate_compiled_skill(snapshot: dict[str, Any], root: Path) -> CompiledSkill:
    if snapshot.get("format") != "portable-v1":
        raise ValueError("unsupported cache snapshot format")
    skill_manifest = RootSkillManifest.model_validate(snapshot["skill_manifest"])
    graph_registry: dict[str, CompiledSkill] = {}
    graph_snapshots = dict(snapshot["graphs"])
    for graph_id, graph_snapshot in graph_snapshots.items():
        graph_registry[str(graph_id)] = _rehydrate_graph(
            dict(graph_snapshot),
            root.resolve(),
            graph_registry,
            skill_manifest,
        )
    root_graph_id = str(snapshot["root_graph_id"])
    return graph_registry[root_graph_id]


def _rehydrate_graph(
    snapshot: dict[str, Any],
    root: Path,
    graph_registry: dict[str, CompiledSkill],
    skill_manifest: RootSkillManifest,
) -> CompiledSkill:
    from graph_skill_runtime.core.loader import (
        CompiledSubagent,
        PhaseTokenInfo,
        _discover_actions_and_tools,
        _inject_subagent_tools,
        _subagent_input_model_name,
    )
    from graph_skill_runtime.core.subagents import build_subagent_input_model

    manifest = GraphManifest.model_validate(snapshot["manifest"])
    adapter: TypeAdapter[PhaseAST] = TypeAdapter(PhaseAST)
    nodes = [
        PhaseDocument(
            phase_name=str(node["phase_name"]),
            path=Path(node["path"]),
            mode=str(node["mode"]),
            frontmatter=dict(node["frontmatter"]),
            raw_blocks=dict(node["raw_blocks"]),
            ast=adapter.validate_python(node["ast"]),
        )
        for node in snapshot["nodes"]
    ]
    actions, tools = _discover_actions_and_tools(root.resolve(), nodes)
    subagents_by_phase: dict[str, list[CompiledSubagent]] = {}
    for phase_id, subagents in dict(snapshot["subagents_by_phase"]).items():
        hydrated_subagents: list[CompiledSubagent] = []
        for item in subagents:
            input_schema = dict(item["input_schema"])
            input_model = build_subagent_input_model(
                _subagent_input_model_name(str(item["parent_phase_id"]), str(item["name"])),
                input_schema,
            )
            hydrated_subagents.append(
                CompiledSubagent(
                    parent_phase_id=str(item["parent_phase_id"]),
                    name=str(item["name"]),
                    target_skill=str(item["target_skill"]),
                    description=str(item["description"]),
                    root=Path(item["root"]),
                    input_schema=input_schema,
                    input_model=input_model,
                    expected_schema=dict(item["expected_schema"]),
                )
            )
        subagents_by_phase[str(phase_id)] = hydrated_subagents
    phase_tokens: dict[str, PhaseTokenInfo] = {}
    for phase_id, token in dict(snapshot["phase_tokens"]).items():
        phase_tokens[str(phase_id)] = PhaseTokenInfo(
            phase_id=str(token["phase_id"]),
            raw_text=str(token["raw_text"]),
            line_start=int(token["line_start"]),
            line_end=int(token["line_end"]),
            attrs=dict(token["attrs"]),
        )
    tools = _inject_subagent_tools(tools, subagents_by_phase)
    return CompiledSkill(
        raw=dict(snapshot["raw"]),
        manifest=manifest,
        nodes=nodes,
        actions=actions,
        tools=tools,
        subagents_by_phase=subagents_by_phase,
        phase_tokens=phase_tokens,
        skill_manifest=skill_manifest,
        skill_root=root,
        graph_root=(root / str(snapshot["graph_root"])).resolve(),
        graph_registry=graph_registry,
    )


__all__ = ["compute_cache_key", "get_cache_dir", "load_from_cache", "save_to_cache"]
