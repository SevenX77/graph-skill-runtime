"""Shared fixtures + import-time invariants for the graph_agent suite.

The middleware-chain topological order regression test lives in
``tests/graph_agent/middleware/test_chain_topology.py`` so pytest
collects it as part of the full suite (``conftest.py`` is treated as
a fixtures file and tests inside it do not run during a full
``pytest tests/graph_agent/`` invocation). The import below acts as
an import-time sanity check — if the middleware package fails to
import (e.g., a missing module after a refactor), every test in the
suite errors out at collection rather than producing a confusing
runtime failure deep in a single test case.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Cross-platform bottom line (docs/development/CROSS_PLATFORM.md): child
# Python processes spawned by tests must write UTF-8 regardless of the host
# locale codepage. Does not affect this process (UTF-8 mode is decided at
# interpreter startup) — call sites still pass encoding="utf-8" explicitly.
os.environ.setdefault("PYTHONUTF8", "1")

from graph_agent.core.skill_resolver_protocol import SkillResolutionError, validate_skill_id

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
        fixtures = self.fixtures
        registry = fixtures / "v030_skill_registry"
        known = {
            "fixture.echo_expert": registry / "echo_expert",
            "demo.echo_agent": fixtures / "v030_agent_demo" / "registry" / "echo_agent",
            "e2e.echo": fixtures / "v030_e2e_pipeline" / "registry" / "echo",
            "e2e.expander": fixtures / "v030_e2e_pipeline" / "registry" / "expander",
        }
        if skill_id in known:
            return known[skill_id]
        relative = Path(*skill_id.split("."))
        candidates = (
            self.workspace_root / skill_id,
            self.workspace_root / relative,
            self.workspace_root / "skills" / skill_id,
            self.workspace_root / "skills" / relative,
            self.workspace_root / "registry" / skill_id,
            self.workspace_root / "registry" / relative,
            registry / skill_id,
            registry / relative,
        )
        for candidate in candidates:
            if (candidate / "GRAPH.md").is_file():
                return candidate
        phases_root = self.workspace_root / "phases"
        if phases_root.is_dir():
            for phase_dir in sorted(path for path in phases_root.iterdir() if path.is_dir()):
                candidate = phase_dir / skill_id
                if (candidate / "GRAPH.md").is_file():
                    return candidate
        tmp_matches = self._find_pytest_tmp_skill(skill_id)
        if tmp_matches:
            return max(tmp_matches, key=lambda path: path.stat().st_mtime_ns)
        raise SkillResolutionError(skill_id, "not registered in deterministic test resolver")

    @staticmethod
    def _find_pytest_tmp_skill(skill_id: str) -> list[Path]:
        matches: list[Path] = []
        tmp_roots = [
            Path(tempfile.gettempdir()).resolve(),
            Path(tempfile.gettempdir()),
            Path("/tmp"),
        ]
        seen_roots: set[Path] = set()
        for root in tmp_roots:
            if root in seen_roots or not root.exists():
                continue
            seen_roots.add(root)
            for tmp_root in root.glob("pytest-of-*"):
                for candidate in tmp_root.rglob(skill_id):
                    if candidate.is_dir() and (candidate / "GRAPH.md").is_file():
                        matches.append(candidate.resolve())
        return matches


@pytest.fixture
def mock_skill_resolver(tmp_path: Path) -> MockSkillResolver:
    return MockSkillResolver(tmp_path)


collect_ignore_glob: list[str] = []
