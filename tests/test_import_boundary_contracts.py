"""Gate on the gate: the import-linter module-boundary contracts stay real.

`lint-imports` (see `[tool.importlinter]` in `pyproject.toml`) is the machine
check for the layering in `docs/design/v1-alignment.md` section 3.1. A boundary
gate degrades in ways the tool itself cannot notice, so each one is asserted here.

1. An exemption is swapped rather than cleared. `ignore_imports` exists to
   register violations that already existed when a contract was introduced, so
   the contract can be enforced from day one instead of waiting for a repo-wide
   cleanup. Pinning only the COUNT is not enough: it lets a cleared debt pay for
   a brand-new violation, leaving the total unchanged. `AUTHORIZED_EXEMPTIONS`
   below therefore pins each exemption's literal identity, and the comparison is
   equality -- adding, swapping, or silently keeping a cleared entry all fail.
   Clearing the debt means deleting the import AND its entry here.
2. The stale-exemption alarm is disarmed, or was never armed. Once a registered
   violation is fixed, its leftover exemption must break the gate rather than
   keep widening the contract. That is `unmatched_ignore_imports_alerting`, and
   import-linter reads it PER CONTRACT: `application/use_cases.py` consumes only
   six session options and this is not one of them, while every contract class
   declares it as its own field. A top-level key would be dead config that reads
   as protection while providing none, so this test requires the option on each
   contract that carries exemptions and forbids the top-level spelling.
3. The gate stops running. A contract set no CI job invokes proves nothing, so
   this test asserts `lint-imports` is a `quality-gates` step and that
   `import-linter` is a declared dev dependency.
4. A contract silently stops covering new code. Several contracts enumerate
   module lists, and an enumeration goes stale when a top-level subpackage is
   added: the new package sits outside every contract while they all still
   report KEPT. This test asserts every top-level module on disk is named by at
   least one contract, so adding one forces classifying it.
5. A contract is rewritten into a weaker form that still reports KEPT. The
   legacy-converter boundary is the live example: expressed as a single
   `protected` contract it silently lost two properties -- `allowed_importers`
   expands a package to all its descendants (so every adapter, `mcp.py`
   included, could import migration), and `protected` checks direct importers
   only (so `sdk -> adapters.cli -> migration` passed). It now takes two
   contracts, one per claim, and the three assertions below pin the exact shape
   each one needs.
6. A contract is justified by taste. Each contract must name its authority, and
   the recognized authorities are a closed set: a `v1-alignment` section, or an
   established Python language convention (`PEP 8`). The package-private
   contract rests on the latter -- section 3.2 enumerates the public contracts
   but does not itself forbid importing a private module, so citing it alone
   would be a hollow reference.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_ROOT = REPO_ROOT / "src" / "graph_skill_runtime"

LAYERS_CONTRACT = "Layered module boundaries (v1-alignment 3.1)"
MIGRATION_DIRECT_CONTRACT = "Migration is imported only by the CLI converter module (v1-alignment 9, AGENTS.md 4)"
MIGRATION_INDIRECT_CONTRACT = (
    "Migration is not reachable indirectly from any runtime path (v1-alignment 9, AGENTS.md 4)"
)

# The one module authorized to reach the legacy converter, per AGENTS.md section 4
# ("confined to the explicit `gskill migrate studio-skill ...` converter
# boundary"). It must stay the exact module: `allowed_importers` expands a
# package to all its descendants, so naming `graph_skill_runtime.adapters` here
# would admit every adapter, `mcp.py` included.
MIGRATION_ALLOWED_IMPORTER = "graph_skill_runtime.adapters.cli"

# Excluded from the indirect contract's sources because they ARE the converter
# boundary, not runtime paths that must be kept clear of it. `__main__` is the
# `python -m` console entry whose only job is to call the CLI; nothing imports
# it, so excluding it opens no route.
MIGRATION_BOUNDARY_MODULES = frozenset(
    {"graph_skill_runtime.adapters.cli", "graph_skill_runtime.__main__"}
)

# The complete set of registered pre-existing violations, pinned by identity as
# (contract name, import expression), frozen 2026-09-01 at the commit that
# introduced these contracts.
#
#   ports.integrations -> integrations.models
#       A provider-neutral Port reaching up into the host-projection layer,
#       which imports ports.integrations back (installer.py, renderers.py) --
#       a two-way dependency between a protocol layer and its implementation.
#       Clearing it means moving `IntegrationScope` / `IntegrationTarget` down
#       to a layer `ports` may depend on, which edits a frozen public contract
#       module and belongs in its own change.
#
# This set may only lose members. Clearing a debt deletes its entry here and its
# `ignore_imports` line together; leaving either behind fails a gate.
AUTHORIZED_EXEMPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            LAYERS_CONTRACT,
            "graph_skill_runtime.ports.integrations -> graph_skill_runtime.integrations.models",
        ),
    }
)

# Recognized authority markers for a contract name. Closed on purpose: adding a
# new kind of authority is a deliberate edit, not a side effect of naming.
AUTHORITY_MARKERS = ("v1-alignment", "PEP 8")

# Contract keys that hold module names.
_MODULE_LIST_KEYS = (
    "layers",
    "source_modules",
    "forbidden_modules",
    "modules",
    "protected_modules",
    "allowed_importers",
)


def _importlinter_config() -> dict[str, Any]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]
    assert isinstance(config, dict)
    return config


def _contracts() -> list[dict[str, Any]]:
    contracts = _importlinter_config()["contracts"]
    assert isinstance(contracts, list) and contracts, "at least one import-linter contract must be declared"
    return contracts


def _submodule_names(package: str) -> set[str]:
    """Return the importable submodules directly inside one subpackage on disk."""
    root = PACKAGE_ROOT / package
    names: set[str] = set()
    for entry in root.iterdir():
        if entry.is_dir() and (entry / "__init__.py").exists():
            names.add(f"graph_skill_runtime.{package}.{entry.name}")
        elif entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
            names.add(f"graph_skill_runtime.{package}.{entry.stem}")
    assert names, f"no submodules found under {root}"
    return names


def _contract(name: str) -> dict[str, Any]:
    matches = [c for c in _contracts() if c["name"] == name]
    assert len(matches) == 1, f"expected exactly one contract named {name!r}, found {len(matches)}"
    return matches[0]


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
    config = _importlinter_config()
    assert config.get("root_package") == "graph_skill_runtime", (
        "import-linter must analyse the runtime package; `tests` is deliberately out of scope "
        "because a unit test of a package-private module is correct by AGENTS.md section 8"
    )


def test_registered_exemptions_match_the_authorized_set_exactly() -> None:
    """RATCHET: exemptions are pinned by identity, not by count.

    Equality, not a subset check: a new exemption fails, swapping a cleared debt
    for a fresh violation fails, and an entry left behind after its debt is
    cleared fails too.
    """
    registered = {
        (contract["name"], ignored)
        for contract in _contracts()
        for ignored in contract.get("ignore_imports", [])
    }

    unauthorized = registered - AUTHORIZED_EXEMPTIONS
    cleared = AUTHORIZED_EXEMPTIONS - registered

    assert not unauthorized, (
        "import-linter now exempts an import that is not in AUTHORIZED_EXEMPTIONS. An "
        "`ignore_imports` entry records a violation that already existed when its contract was "
        "introduced; it is not a way to admit a new one, and it may not be traded for a debt that "
        "was cleared. Fix the import, or -- if the boundary itself is wrong -- change the contract "
        f"and its cited authority instead of exempting the import.\nUnauthorized: {sorted(unauthorized)}"
    )
    assert not cleared, (
        "an authorized exemption is no longer present in pyproject.toml. If the debt was cleared, "
        "delete its entry from AUTHORIZED_EXEMPTIONS in this test as well -- the ratchet is only "
        f"honest if both sides shrink together.\nNo longer registered: {sorted(cleared)}"
    )


def test_stale_exemption_alarm_is_armed_where_import_linter_reads_it() -> None:
    """The other half of the ratchet, enforced by import-linter itself."""
    config = _importlinter_config()

    assert "unmatched_ignore_imports_alerting" not in config, (
        "`unmatched_ignore_imports_alerting` must not be set at the top level: import-linter reads "
        "only six session options (root_package/root_packages, contract_types, "
        "include_external_packages, exclude_type_checking_imports, show_timings) and this is not "
        "one of them. Verified on 2.14 -- a top-level \"none\" did not silence a stale exemption, "
        "while the same value inside the contract did. A key here is dead config that reads as "
        "protection while providing none; declare it on the contract instead."
    )

    for contract in _contracts():
        if not contract.get("ignore_imports"):
            continue
        assert contract.get("unmatched_ignore_imports_alerting") == "error", (
            f"contract {contract['name']!r} carries exemptions, so it must set "
            "`unmatched_ignore_imports_alerting = \"error\"` in its own options. Downgraded to "
            "warn/none, a cleared debt would leave a stale entry behind that silently keeps "
            "widening the contract."
        )


def test_every_contract_names_a_recognized_authority() -> None:
    uncited = [
        contract["name"]
        for contract in _contracts()
        if not any(marker in contract["name"] for marker in AUTHORITY_MARKERS)
    ]
    assert not uncited, (
        "every import-linter contract must name the authority it rests on, so the boundary is "
        f"traceable rather than a matter of taste. Recognized markers: {AUTHORITY_MARKERS}. A "
        "design section and an established language convention are both acceptable, including "
        f"together, but a contract may not cite nothing: {uncited}"
    )


def test_every_top_level_module_is_named_by_some_contract() -> None:
    """Enumerated contract lists go stale when a subpackage is added."""
    mentioned: set[str] = set()
    for contract in _contracts():
        for key in _MODULE_LIST_KEYS:
            for module in contract.get(key, []):
                mentioned.add(module)

    unclassified = _top_level_module_names() - mentioned
    assert not unclassified, (
        "these top-level modules are not named by any import-linter contract, so they sit outside "
        "every boundary while all contracts still report KEPT. Classify each one into the contracts "
        f"that should govern it: {sorted(unclassified)}"
    )


def test_only_the_cli_converter_module_may_import_migration() -> None:
    """The exact regression this pins: a package-wide allowed importer.

    `allowed_importers` expands a package to all of its descendants, so naming
    `graph_skill_runtime.adapters` would let every adapter -- `mcp.py` included --
    reach the legacy converter, which AGENTS.md section 4 confines to the
    explicit `gskill migrate studio-skill` command.
    """
    contract = _contract(MIGRATION_DIRECT_CONTRACT)
    assert contract["type"] == "protected"
    assert contract["allowed_importers"] == [MIGRATION_ALLOWED_IMPORTER], (
        "the legacy converter's authorized importer must be the exact module "
        f"{MIGRATION_ALLOWED_IMPORTER!r}. A package name here admits every module under it: "
        "`allowed_importers` treats a package as all of its descendants."
    )
    assert contract["protected_modules"] == ["graph_skill_runtime.migration"]


def test_indirect_migration_contract_keeps_indirect_checking_on() -> None:
    """`protected` is direct-only, so the indirect claim needs a second contract.

    Verified on import-linter 2.14: with the exact-module `allowed_importers`
    in place, an injected `sdk.py -> adapters.cli -> migration` chain still
    reported KEPT. Setting `allow_indirect_imports` on the contract below would
    reduce it to the direct check and re-open that hole.
    """
    contract = _contract(MIGRATION_INDIRECT_CONTRACT)
    assert contract["type"] == "forbidden"
    assert "allow_indirect_imports" not in contract, (
        "this contract exists precisely to catch INDIRECT reach into the legacy converter -- "
        "importing the SDK must not drag it in behind `adapters.cli`. Setting "
        "`allow_indirect_imports` silently reduces it to the direct-only check that the "
        "`protected` contract already performs."
    )
    assert contract["forbidden_modules"] == ["graph_skill_runtime.migration"]


def test_indirect_migration_contract_sources_stay_exhaustive() -> None:
    """A `forbidden` contract enumerates sources, so the list must track the package.

    Computed from disk: every top-level module plus every `adapters` submodule,
    minus `migration` itself and minus the two modules that ARE the converter
    boundary. Adding an adapter or a subpackage fails here until it is
    classified, so the enumeration cannot quietly stop covering new code.
    """
    contract = _contract(MIGRATION_INDIRECT_CONTRACT)
    listed = set(contract["source_modules"])

    expected = (
        (_top_level_module_names() | _submodule_names("adapters"))
        - {"graph_skill_runtime.migration", "graph_skill_runtime.adapters"}
        - MIGRATION_BOUNDARY_MODULES
    )

    assert listed == expected, (
        "the indirect-reach contract must list every module that is not part of the CLI converter "
        "boundary; anything missing can reach the legacy converter while the contract still "
        f"reports KEPT.\nmissing: {sorted(expected - listed)}"
        f"\nno longer exists: {sorted(listed - expected)}"
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
