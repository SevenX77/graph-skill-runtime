"""Composition root for default SDK, CLI, and MCP dependencies."""

from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.adapters.engine import CurrentEngineAdapter
from graph_skill_runtime.adapters.snapshots import LocalRunSnapshotStore
from graph_skill_runtime.application.config import ConfigResolver
from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.ports.runtime import RunSnapshotStore, RuntimeEngine


def create_application(
    *,
    user_config_path: Path | None = None,
    engine: RuntimeEngine | None = None,
    snapshot_store: RunSnapshotStore | None = None,
) -> RuntimeApplication:
    """Build one application service with explicitly replaceable adapters."""

    return RuntimeApplication(
        config_resolver=ConfigResolver(user_config_path=user_config_path),
        engine=engine or CurrentEngineAdapter(),
        snapshot_store=snapshot_store or LocalRunSnapshotStore(),
    )
