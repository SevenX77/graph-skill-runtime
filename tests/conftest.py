"""Shared fixtures + import-time invariants for the graph_skill_runtime suite.

The middleware-chain topological order regression test lives in
``tests/graph_skill_runtime/middleware/test_chain_topology.py`` so pytest
collects it as part of the full suite (``conftest.py`` is treated as
a fixtures file and tests inside it do not run during a full
``pytest tests/graph_skill_runtime/`` invocation). The import below acts as
an import-time sanity check — if the middleware package fails to
import (e.g., a missing module after a refactor), every test in the
suite errors out at collection rather than producing a confusing
runtime failure deep in a single test case.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Cross-platform bottom line (docs/development/CROSS_PLATFORM.md): child
# Python processes spawned by tests must write UTF-8 regardless of the host
# locale codepage. Does not affect this process (UTF-8 mode is decided at
# interpreter startup) — call sites still pass encoding="utf-8" explicitly.
os.environ.setdefault("PYTHONUTF8", "1")

from graph_skill_runtime.core.skill_resolver_protocol import SkillResolutionError, validate_skill_id

# Import-time sanity: ensure the MVP-3 middleware package is importable
# before any test runs. The actual ordering assertions live in the
# adjacent ``middleware/test_chain_topology.py`` test file.


class MockSkillResolver:
    """Deterministic resolver used by tests that are not exercising lookup behavior."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.fixtures = Path(__file__).resolve().parent / "fixtures"

    def resolve_skill(self, skill_id: str) -> Path:
        validate_skill_id(skill_id)
        candidates = (
            self.workspace_root / skill_id,
            self.workspace_root / "skills" / skill_id,
            self.workspace_root / "registry" / skill_id,
            self.fixtures / skill_id,
        )
        for candidate in candidates:
            if (candidate / "SKILL.md").is_file() and (candidate / "graph.yaml").is_file():
                return candidate
        raise SkillResolutionError(skill_id, "not registered in deterministic test resolver")


@pytest.fixture
def mock_skill_resolver(tmp_path: Path) -> MockSkillResolver:
    return MockSkillResolver(tmp_path)


collect_ignore_glob: list[str] = []
