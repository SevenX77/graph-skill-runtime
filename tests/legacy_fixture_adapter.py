"""Explicitly migrate frozen v0.3 fixtures before exercising current runtime behavior.

This module is test-only. Contract tests import production entry points directly;
behavioral characterization tests with historical authored fixtures import these
wrappers so the only legacy reader exercised is the public one-shot converter.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from graph_skill_runtime.core.compiler import compile_skill as _compile_skill
from graph_skill_runtime.core.graph_assembler import assemble_graph as _assemble_graph
from graph_skill_runtime.core.runner import (
    _run_portable_skill_dict as _run_skill_dict,
)
from graph_skill_runtime.core.runner import (
    predict_skill as _predict_skill,
)
from graph_skill_runtime.core.runner import (
    resume_skill as _resume_skill,
)
from graph_skill_runtime.core.runner import (
    run_skill as _run_skill,
)
from graph_skill_runtime.migration import migrate_studio_skill

_SESSION_ROOT = Path(tempfile.mkdtemp(prefix="gsrt-"))
atexit.register(shutil.rmtree, _SESSION_ROOT, ignore_errors=True)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.as_posix(),
    )
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _portable_name(value: str, digest: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = f"fixture-{digest[:8]}"
    if len(normalized) > 64:
        normalized = f"{normalized[:55].rstrip('-')}-{digest[:8]}"
    return normalized


def portable_fixture_root(
    value: str | Path,
    *,
    runtime_config: dict[str, Any] | None = None,
) -> Path:
    """Return a current-format root, explicitly converting a frozen fixture once."""

    path = Path(value)
    root = path.parent if path.is_file() and path.name == "SKILL.md" else path
    if (root / "SKILL.md").is_file() and (root / "graph.yaml").is_file():
        return root
    if not (root / "GRAPH.md").is_file():
        return root
    tree_digest = _tree_digest(root)
    config_payload = json.dumps(runtime_config, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{tree_digest}\0{config_payload}".encode()).hexdigest()
    destination = _SESSION_ROOT / digest[:12] / _portable_name(root.name, digest)
    if not destination.is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
        runtime_config_path: Path | None = None
        if runtime_config is not None:
            legacy_config = {
                "schema_version": "studio.runtime_config.v2",
                "inputs": runtime_config.get("inputs", {}),
                "llm": runtime_config.get("llm", {}),
                "breakpoints": runtime_config.get("breakpoints", []),
                "artifacts": runtime_config.get("artifacts", []),
            }
            runtime_config_path = destination.parent / "runtime_config.json"
            runtime_config_path.write_text(
                json.dumps(legacy_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        migrate_studio_skill(root, destination, runtime_config=runtime_config_path)
    return destination


def compile_skill(root: str | Path, *args: Any, **kwargs: Any) -> Any:
    return _compile_skill(portable_fixture_root(root), *args, **kwargs)


def load_workflow_from_md(root: str | Path, *args: Any, **kwargs: Any) -> Any:
    portable_root = portable_fixture_root(root)
    callbacks = kwargs.pop("callbacks", None)
    model_resolver = kwargs.pop("model_resolver", None)
    resolver = kwargs.pop("skill_resolver")
    if args or kwargs:
        raise TypeError("unsupported legacy fixture adapter arguments")
    chat_model = (
        model_resolver.resolve(phase_name="<workflow>")
        if model_resolver is not None
        else None
    )
    compiled = _compile_skill(portable_root, skill_resolver=resolver)
    return _assemble_graph(
        compiled,
        chat_model=chat_model,
        callbacks=callbacks,
        skill_resolver=resolver,
    ).graph


def run_skill(skill_path: str | Path, *args: Any, **kwargs: Any) -> Any:
    return _run_skill(
        portable_fixture_root(skill_path, runtime_config=kwargs.get("runtime_config")),
        *args,
        **kwargs,
    )


def predict_skill(skill_path: str | Path, *args: Any, **kwargs: Any) -> Any:
    return _predict_skill(
        portable_fixture_root(skill_path, runtime_config=kwargs.get("runtime_config")),
        *args,
        **kwargs,
    )


def resume_skill(skill_path: str | Path, *args: Any, **kwargs: Any) -> Any:
    return _resume_skill(
        portable_fixture_root(skill_path, runtime_config=kwargs.get("runtime_config")),
        *args,
        **kwargs,
    )


def run_skill_dict(skill_root: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    return _run_skill_dict(portable_fixture_root(skill_root), *args, **kwargs)


__all__ = [
    "compile_skill",
    "load_workflow_from_md",
    "portable_fixture_root",
    "predict_skill",
    "resume_skill",
    "run_skill",
    "run_skill_dict",
]
