"""Gate on the gate: the import-linter module-boundary contracts stay real.

`lint-imports` (see `[tool.importlinter]` in `pyproject.toml`) is the machine
check for the layering in `docs/design/v1-alignment.md` section 3.1. A boundary
gate degrades in three ways that the tool itself cannot notice, so each one is
asserted here:

1. The exemption list grows. `ignore_imports` exists to register violations that
   already existed when a contract was introduced, so the contract can be
   enforced from day one instead of waiting for a repo-wide cleanup. That is only
   honest as a RATCHET: the list may shrink, never grow. Adding a line to make a
   NEW import pass converts the contract into a description of whatever the code
   currently does. `IGNORED_IMPORT_BUDGET` below is the frozen count; lowering it
   when a debt is cleared is the intended edit, raising it is the defect this
   test exists to block. The complementary failure -- a debt fixed but its
   exemption left behind, silently widening the contract -- is caught by
   `unmatched_ignore_imports_alerting = "error"`, which is also asserted here.
2. The gate stops running. A contract set that no CI job invokes proves nothing,
   so this test asserts `lint-imports` is a `quality-gates` step and that
   `import-linter` is a declared dev dependency.
3. A contract silently stops covering new code. The package-private contract
   enumerates its source modules (a `forbidden` contract cannot express "every
   package except the owner"), so a newly added top-level subpackage would be
   outside it while the contract still reported KEPT. This test asserts that
   enumeration stays exhaustive against the package on disk.

Contract names are also asserted to cite their authorizing design section, so a
contract cannot be added on nothing but a maintainer's taste.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_ROOT = REPO_ROOT / "src" / "graph_skill_runtime"

# Frozen count of registered pre-existing violations, 2026-09-01, at the commit
# that introduced these contracts. One entry:
#
#   ports.integrations -> integrations.models
#       A provider-neutral Port reaching up into the host-projection layer,
#       which imports ports.integrations back (installer.py, renderers.py) --
#       a two-way dependency between a protocol layer and its implementation.
#       Clearing it means moving `IntegrationScope` / `IntegrationTarget` down
#       to a layer `ports` may depend on, which edits a frozen public contract
#       module and belongs in its own change.
#
# This number may only go DOWN.
IGNORED_IMPORT_BUDGET = 1

# The owner of the package-private region excluded from the private-import
# contract's source list: `core` is allowed to import its own `_predict_internal`.
PRIVATE_CONTRACT_OWNER = "graph_skill_runtime.core"

PRIVATE_CONTRACT_NAME = "Package-private modules are not imported across packages (v1-alignment 3.2)"


def _load_importlinter_config() -> dict[str, Any]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]
    assert isinstance(config, dict)
    return config


def _contracts() -> list[dict[str, Any]]:
    contracts = _load_importlinter_config()["contracts"]
    assert isinstance(contracts, list) and contracts, "at least one import-linter contract must be declared"
    return contracts


def _top_level_module_names() -> set[str]:
    """Return the importable top-level modules inside the package on disk.

    A directory counts only when it holds `__init__.py`: an implicit namespace
    directory (today `skills/`) is not a module import-linter can name, so a
    contract must not claim to cover one.
    """
    names: set[str] = set()
    for entry in PACKAGE_ROOT.iterdir():
        if entry.is_dir() and (entry / "__init__.py").exists():
            names.add(f"graph_skill_runtime.{entry.name}")
        elif entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
            names.add(f"graph_skill_runtime.{entry.stem}")
    assert names, f"no top-level modules found under {PACKAGE_ROOT}"
    return names


def test_root_package_under_analysis_is_the_runtime_package() -> None:
    config = _load_importlinter_config()
    assert config.get("root_package") == "graph_skill_runtime", (
        "import-linter must analyse the runtime package; `tests` is deliberately out of scope "
        "because a unit test of a package-private module is correct by AGENTS.md section 8"
    )


def test_registered_violation_budget_may_only_shrink() -> None:
    """RATCHET: total `ignore_imports` entries must never exceed the frozen budget."""
    registered: list[str] = []
    for contract in _contracts():
        for ignored in contract.get("ignore_imports", []):
            registered.append(f"{contract['name']}: {ignored}")

    assert len(registered) <= IGNORED_IMPORT_BUDGET, (
        f"import-linter now registers {len(registered)} exempted imports but the frozen budget is "
        f"{IGNORED_IMPORT_BUDGET}. An `ignore_imports` entry records a violation that already "
        f"existed when its contract was introduced; it is not a way to admit a new one. Fix the "
        f"import, or -- if the boundary itself is wrong -- change the contract and its cited design "
        f"section instead of exempting the import.\nRegistered:\n  " + "\n  ".join(registered)
    )


def test_clearing_a_registered_violation_must_remove_its_exemption() -> None:
    """The other half of the ratchet, enforced by import-linter itself."""
    config = _load_importlinter_config()
    assert config.get("unmatched_ignore_imports_alerting") == "error", (
        "`unmatched_ignore_imports_alerting` must be \"error\" so that an exemption whose import no "
        "longer exists fails the gate. Downgraded to warn/none, a cleared debt would leave a stale "
        "line behind that silently keeps widening the contract."
    )


def test_every_contract_cites_its_authorizing_design_section() -> None:
    uncited = [
        contract["name"]
        for contract in _contracts()
        if "v1-alignment" not in contract["name"]
    ]
    assert not uncited, (
        "every import-linter contract must name the design section that authorizes it, so the "
        "boundary is traceable to docs/design/v1-alignment.md rather than to the current "
        f"directory shape: {uncited}"
    )


def test_private_module_contract_covers_every_top_level_module() -> None:
    """A `forbidden` contract lists sources explicitly, so the list must stay exhaustive."""
    contract = next(c for c in _contracts() if c["name"] == PRIVATE_CONTRACT_NAME)
    listed = set(contract["source_modules"])
    expected = _top_level_module_names() - {PRIVATE_CONTRACT_OWNER}

    assert listed == expected, (
        "the package-private import contract must list every top-level module except the owning "
        "package, otherwise a newly added subpackage sits outside the contract while it still "
        f"reports KEPT.\nmissing: {sorted(expected - listed)}\nno longer exists: {sorted(listed - expected)}"
    )


def test_package_facade_does_not_re_export_private_internals() -> None:
    """Closes the one gap the contract cannot express: the package root itself.

    `graph_skill_runtime` is the parent of `core`, so import-linter skips it as a
    source module against `core._predict_internal` (overlapping modules do not
    describe a forbiddable import).
    """
    facade = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "_predict_internal" not in facade, (
        "the public facade must not re-export package-private predict internals; "
        "docs/design/v1-alignment.md section 3.2 lists the contracts the top-level package exposes"
    )


def test_import_boundary_gate_runs_in_ci() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "uv run lint-imports" in workflow, (
        "`lint-imports` must run in CI; a boundary contract set that no job invokes is a gate in "
        "name only"
    )

    quality_gates = workflow.split("quality-gates:", 1)[1].split("\n  runtime-tests:", 1)[0]
    assert "uv run lint-imports" in quality_gates, (
        "`lint-imports` must run in the required `quality-gates` job. It is a static check over the "
        "source import graph, so it is platform-independent and does not need repeating in "
        "`cross-platform-smoke`."
    )


def test_import_linter_is_a_declared_dev_dependency() -> None:
    dev_dependencies = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]["dev"]
    assert any(dep.startswith("import-linter") for dep in dev_dependencies), (
        "import-linter must be declared in the `dev` extra so `uv sync --extra dev` installs the "
        "gate; a gate that is not installed cannot run"
    )
