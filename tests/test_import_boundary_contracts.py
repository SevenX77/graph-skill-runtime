"""Gate on the gate: the import-linter module-boundary contracts stay real.

`lint-imports` (see `[tool.importlinter]` in `pyproject.toml`) is the machine
check for the layering in `docs/design/v1-alignment.md` section 3.1. A boundary
gate degrades in ways the tool itself cannot notice, so each one is asserted here.

This file has two layers and needs both. The CONFIGURATION tests (failure modes
1-6) read `pyproject.toml` and pin the shape each contract must keep. The
ENFORCEMENT tests (failure mode 7) copy the package into a temporary directory,
inject a real violating import, and run import-linter over that copy: a
configuration of the right shape still says nothing about what the tool does
with it.

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
7. The contracts do not actually reject the imports they name. Failure modes 1-6
   are all read from TOML, so they keep passing if import-linter changes what a
   field means, if a contract stops being wired to the code at all, or if an
   assumption about a field's semantics was simply wrong to begin with.
   Measured, not assumed: with a direct `adapters.mcp -> migration` import AND an
   indirect `sdk -> adapters.cli -> migration` chain both present in the tree,
   every assertion above still passed. The enforcement tests below close that gap
   by running the gate itself -- the pristine copy stays green, each injected
   violation turns the naming contract red, and one negative control shows the
   redness comes from the contract rather than from the harness.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_ROOT = REPO_ROOT / "src" / "graph_skill_runtime"

LAYERS_CONTRACT = "Layered module boundaries (v1-alignment 3.1)"
MIGRATION_DIRECT_CONTRACT = "Migration is imported only by the CLI converter module (v1-alignment 9, AGENTS.md 4)"
MIGRATION_INDIRECT_CONTRACT = (
    "Migration is not reachable indirectly from any runtime path (v1-alignment 9, AGENTS.md 4)"
)
PACKAGE_PRIVATE_CONTRACT = (
    "Package-private modules are imported only by their owner "
    "(PEP 8 underscore convention, corroborated by v1-alignment 3.2)"
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


# ---------------------------------------------------------------------------
# Enforcement layer: run the real contracts over an injected copy of the package
#
# The assertions above describe the gate; these ones execute it. Each test copies
# `src/graph_skill_runtime` into a temporary directory next to the repository's
# own `[tool.importlinter]` section, appends one import statement that a contract
# claims is illegal, and runs import-linter over the copy. Nothing under `src/`
# is touched, so a failing or interrupted test cannot leave a violation behind.
#
# Modelled on import-linter's own test suite, which tests contracts on two
# levels. Its unit tests build a synthetic in-memory grimp `ImportGraph`
# (`add_module` / `add_import`) and assert `contract.check(graph=...).kept`; its
# functional tests (`tests/functional/test_lint_imports.py`) run the real entry
# point over a real package directory with a real config file, using `os.chdir`
# plus `sys.path` edits to make the assets importable, and assert
# `cli.EXIT_STATUS_SUCCESS == cli.lint_imports()`.
#
# Borrowed: the functional level. A synthetic graph would prove that a contract
# type works -- which is upstream's job, not ours -- while saying nothing about
# whether THIS repository's contracts still cover THIS package, which is the
# defect these tests exist to catch.
#
# Rejected: doing it in-process, because upstream's precondition does not hold
# here. Its asset packages are not imported by the test session; ours is. grimp
# locates the package under analysis through `importlib.util.find_spec`
# (grimp/adaptors/packagefinder.py:21), and `find_spec` returns `sys.modules`'
# entry when the name is already imported. Measured: after `import
# graph_skill_runtime`, putting a copy first on `sys.path` still resolved to the
# real `src/graph_skill_runtime`. A subprocess with `PYTHONPATH` pointing at the
# copy is the form that actually analyses the copy, and it additionally keeps
# `os.chdir` and `lint_imports`'s own `sys.path.insert(0, os.getcwd())` out of a
# 1700-test session.
# ---------------------------------------------------------------------------

# The interpreter running the tests already has import-linter installed, and
# `importlinter.cli.lint_imports` is exactly what the `lint-imports` console
# script calls (see its `_run_check`). Going through `sys.executable` avoids
# locating a platform-specific script name (`lint-imports.exe` on Windows).
_LINT_RUNNER = (
    "import sys;"
    "from importlinter.cli import lint_imports;"
    "sys.exit(lint_imports(config_filename=sys.argv[1], no_cache=True, no_logo=True))"
)

# import-linter renders through `rich`, which hard-wraps at 80 columns when
# stdout is not a terminal -- long contract names then break across lines and
# even lose the space before their verdict ("...(v1-alignment 3.1)KEPT",
# observed on 2.14). `COLUMNS` is how `rich` is told otherwise.
_WIDE_ENOUGH_TO_NEVER_WRAP = "2000"

_ANALYZED_LINE = re.compile(r"^Analyzed \d+ files, \d+ dependencies\.$")
_SUMMARY_LINE = re.compile(r"^Contracts: (?P<kept>\d+) kept, (?P<broken>\d+) broken\.$")
_RESULT_LINE = re.compile(r"^(?P<name>.+?) (?P<verdict>KEPT|BROKEN)(?: \([^)]*\))?$")

# Modules used as injection sites, relative to the package root. `adapters.mcp`
# is the module the direct-migration contract exists to keep out of the legacy
# converter, and it is foreign to `core`, so it also serves as the outsider
# reaching into a package-private module.
_MCP_MODULE = ("adapters", "mcp.py")
_SDK_MODULE = ("sdk.py",)

_IMPORTS_MIGRATION_DIRECTLY = "from graph_skill_runtime import migration as _boundary_probe"
_IMPORTS_THE_CLI_CONVERTER = "from graph_skill_runtime.adapters import cli as _boundary_probe"
_IMPORTS_A_PRIVATE_MODULE = (
    "from graph_skill_runtime.core import _predict_internal as _boundary_probe"
)

# Anchor for the negative control below. It is the last line of the indirect
# migration contract, and `allow_indirect_imports` is the one option that would
# reduce that contract to the direct check `protected` already performs.
_INDIRECT_CONTRACT_ANCHOR = 'forbidden_modules = ["graph_skill_runtime.migration"]'


@dataclass(frozen=True)
class LintRun:
    """One `lint-imports` execution: its exit status and per-contract verdicts."""

    exit_code: int
    output: str
    verdicts: dict[str, str]

    @property
    def broken(self) -> set[str]:
        return {name for name, verdict in self.verdicts.items() if verdict == "BROKEN"}


class ImportLinterSandbox:
    """A copy of the package plus the repository's real contracts, safe to break."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.package = root / "src" / "graph_skill_runtime"

    def run(self, config_filename: str = "pyproject.toml") -> LintRun:
        environment = dict(os.environ)
        environment.update(
            {
                # First on the child's `sys.path`, so `graph_skill_runtime`
                # resolves to this copy rather than to the editable install of
                # the real `src/` that site-packages appends.
                "PYTHONPATH": str(self.root / "src"),
                "COLUMNS": _WIDE_ENOUGH_TO_NEVER_WRAP,
                # `rich` writes its progress spinner as U+2219, which a Windows
                # child inheriting an ANSI code page cannot encode -- observed
                # here as `UnicodeEncodeError: 'gbk' codec` under CP936. The
                # report is then lost entirely, so the child's text I/O is
                # pinned to UTF-8 rather than left to the active code page.
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        completed = subprocess.run(
            [sys.executable, "-c", _LINT_RUNNER, config_filename],
            cwd=self.root,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        output = completed.stdout + completed.stderr
        return LintRun(completed.returncode, output, _parse_verdicts(output))

    @contextlib.contextmanager
    def injected(self, module: tuple[str, ...], statement: str) -> Iterator[None]:
        """Append one import statement to a copied module, then restore it."""
        target = self.package.joinpath(*module)
        original = target.read_bytes()
        try:
            target.write_bytes(original + f"\n{statement}  # injected by the boundary gate test\n".encode())
            yield
        finally:
            target.write_bytes(original)


def _importlinter_section_text() -> str:
    """Return the `[tool.importlinter]` section of `pyproject.toml` verbatim.

    Sliced as text rather than re-serialized from the parsed dict: the sandbox
    must run the same configuration the real gate reads, and there is no TOML
    writer in the dependency set to round-trip through. Fidelity is then proven
    mechanically -- the slice is parsed back and compared to the live config.
    """
    lines = PYPROJECT.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == "[tool.importlinter]"),
        None,
    )
    assert start is not None, "pyproject.toml has no [tool.importlinter] section"

    end = len(lines)
    for index, line in enumerate(lines[start + 1 :], start=start + 1):
        # Only a table header starts a line with "[": array elements are indented
        # and closing brackets are "]".
        if line.startswith("[") and not line.startswith(("[tool.importlinter]", "[[tool.importlinter.")):
            end = index
            break

    section = "".join(lines[start:end])
    assert tomllib.loads(section)["tool"]["importlinter"] == _importlinter_config(), (
        "the extracted [tool.importlinter] section does not parse back to the live configuration, "
        "so the sandbox would be linting something other than the real contracts"
    )
    return section


def _parse_verdicts(output: str) -> dict[str, str]:
    """Read the per-contract KEPT/BROKEN verdicts out of an import-linter report."""
    lines = [line.strip() for line in output.splitlines()]
    start = next((index for index, line in enumerate(lines) if _ANALYZED_LINE.match(line)), None)
    assert start is not None, f"import-linter produced no contract results:\n{output}"

    verdicts: dict[str, str] = {}
    summary: tuple[int, int] | None = None
    for line in lines[start + 1 :]:
        summary_match = _SUMMARY_LINE.match(line)
        if summary_match:
            summary = (int(summary_match["kept"]), int(summary_match["broken"]))
            break
        result_match = _RESULT_LINE.match(line)
        if result_match:
            verdicts[result_match["name"]] = result_match["verdict"]

    assert summary is not None, f"import-linter printed no result summary:\n{output}"
    kept = sum(1 for verdict in verdicts.values() if verdict == "KEPT")
    assert (kept, len(verdicts) - kept) == summary, (
        "this test's report parser and import-linter's own summary disagree about how many "
        f"contracts were checked, so a verdict is being missed or invented:\n{output}"
    )

    declared = {contract["name"] for contract in _contracts()}
    assert set(verdicts) == declared, (
        "every declared contract must appear in the report with a verdict; a missing one would be "
        f"silently unchecked.\nmissing: {sorted(declared - set(verdicts))}"
        f"\nunexpected: {sorted(set(verdicts) - declared)}\n{output}"
    )
    return verdicts


@pytest.fixture(scope="module")
def import_linter_sandbox(tmp_path_factory: pytest.TempPathFactory) -> ImportLinterSandbox:
    """Copy the package and the real contracts once for this module's tests.

    Module-scoped because the copy costs a directory walk and every test restores
    its injection through `injected()`, so no test can observe another's edit.
    """
    root = tmp_path_factory.mktemp("import-boundary")
    (root / "src").mkdir()
    shutil.copytree(
        PACKAGE_ROOT,
        root / "src" / "graph_skill_runtime",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (root / "pyproject.toml").write_text(_importlinter_section_text(), encoding="utf-8", newline="\n")
    return ImportLinterSandbox(root)


def test_the_authorized_cli_converter_import_stays_kept(
    import_linter_sandbox: ImportLinterSandbox,
) -> None:
    """The legal owner keeps its import, and the untouched copy is green.

    Two claims in one run. First, `adapters.cli` -- the module AGENTS.md section 4
    authorizes -- really does import the legacy converter, so the two migration
    contracts are being exercised rather than passing vacuously over a package
    where nothing imports migration at all. Second, the pristine copy reproduces
    the repository's own green result, which is what makes a red verdict in the
    tests below attributable to the injected import instead of to the harness.
    """
    cli_source = (import_linter_sandbox.package / "adapters" / "cli.py").read_text(encoding="utf-8")
    assert "from graph_skill_runtime.migration import" in cli_source, (
        "the CLI converter module no longer imports migration, so 'migration stays KEPT' would "
        "prove nothing. If the converter moved, move this contract's `allowed_importers` with it."
    )

    result = import_linter_sandbox.run()

    assert result.exit_code == 0, f"the untouched package copy must satisfy every contract:\n{result.output}"
    assert result.broken == set()
    assert result.verdicts[MIGRATION_DIRECT_CONTRACT] == "KEPT"
    assert result.verdicts[MIGRATION_INDIRECT_CONTRACT] == "KEPT"


def test_a_direct_import_of_the_legacy_converter_is_rejected(
    import_linter_sandbox: ImportLinterSandbox,
) -> None:
    """`adapters.mcp -> migration`: the exact import the direct contract names.

    AGENTS.md section 4 confines legacy v0.3 parsing to the `gskill migrate
    studio-skill` converter boundary. `adapters.mcp` is the neighbour that a
    package-wide `allowed_importers` would have admitted.
    """
    with import_linter_sandbox.injected(_MCP_MODULE, _IMPORTS_MIGRATION_DIRECTLY):
        result = import_linter_sandbox.run()

    assert result.verdicts[MIGRATION_DIRECT_CONTRACT] == "BROKEN", (
        "a transport adapter importing the legacy converter must break the direct contract; it "
        f"reported KEPT, so `allowed_importers` is admitting more than `adapters.cli`:\n{result.output}"
    )
    # The indirect contract lists `adapters.mcp` among its sources, so a direct
    # import is also the shortest illegal chain and breaks it too.
    assert result.broken == {MIGRATION_DIRECT_CONTRACT, MIGRATION_INDIRECT_CONTRACT}
    assert result.exit_code == 1
    # No such import exists in `src/`, where the gate is green: seeing it reported
    # proves the injected COPY was analysed, not the installed package.
    assert "graph_skill_runtime.adapters.mcp -> graph_skill_runtime.migration" in result.output


def test_reaching_the_legacy_converter_through_the_cli_module_is_rejected(
    import_linter_sandbox: ImportLinterSandbox,
) -> None:
    """`sdk -> adapters.cli -> migration`: legal hop, illegal destination.

    Every edge in this chain is individually allowed -- `adapters.cli` is the one
    module authorized to import migration -- yet importing the SDK now drags the
    legacy converter in behind it, which is what "confined to the converter
    boundary" forbids.
    """
    with import_linter_sandbox.injected(_SDK_MODULE, _IMPORTS_THE_CLI_CONVERTER):
        result = import_linter_sandbox.run()

    assert result.verdicts[MIGRATION_INDIRECT_CONTRACT] == "BROKEN", (
        "importing the SDK must not reach the legacy converter through `adapters.cli`. This "
        f"contract is the only one that can catch that chain:\n{result.output}"
    )
    assert result.verdicts[MIGRATION_DIRECT_CONTRACT] == "KEPT", (
        "the `protected` contract checks DIRECT importers only, which is why the indirect claim "
        "needs its own contract. If import-linter has changed and `protected` now follows chains, "
        "re-decide whether two contracts are still warranted instead of relaxing this assertion."
    )
    assert result.broken == {MIGRATION_INDIRECT_CONTRACT}
    assert result.exit_code == 1
    assert "graph_skill_runtime.sdk -> graph_skill_runtime.adapters.cli" in result.output


def test_weakening_the_indirect_contract_hides_that_chain(
    import_linter_sandbox: ImportLinterSandbox,
) -> None:
    """Negative control: the red above comes from the contract, not the harness.

    The same injected chain is linted against a config that differs by one line --
    `allow_indirect_imports = true` on the indirect contract -- and goes green.
    That is the mutation the pyproject comment warns against, so this test both
    proves the previous test has causal power and shows what the option costs.
    """
    section = _importlinter_section_text()
    assert "allow_indirect_imports" not in _contract(MIGRATION_INDIRECT_CONTRACT), (
        "the live contract already sets `allow_indirect_imports`, so there is nothing left for this "
        "control to weaken -- and the contract has already lost its indirect check"
    )
    assert section.count(_INDIRECT_CONTRACT_ANCHOR) == 1, (
        f"expected exactly one {_INDIRECT_CONTRACT_ANCHOR!r} line to weaken; the mutation is only "
        "meaningful if it lands on the indirect migration contract"
    )
    weakened = section.replace(
        _INDIRECT_CONTRACT_ANCHOR,
        f"{_INDIRECT_CONTRACT_ANCHOR}\nallow_indirect_imports = true",
    )
    (import_linter_sandbox.root / "weakened.toml").write_text(weakened, encoding="utf-8", newline="\n")

    with import_linter_sandbox.injected(_SDK_MODULE, _IMPORTS_THE_CLI_CONVERTER):
        result = import_linter_sandbox.run("weakened.toml")

    assert result.verdicts[MIGRATION_INDIRECT_CONTRACT] == "KEPT", (
        "with `allow_indirect_imports` set, the injected chain must slip through -- that is the "
        f"whole reason the option is left off:\n{result.output}"
    )
    assert result.exit_code == 0


def test_reaching_into_a_package_private_module_is_rejected(
    import_linter_sandbox: ImportLinterSandbox,
) -> None:
    """`adapters.mcp -> core._predict_internal`: an outsider inside `core`.

    PEP 8's leading underscore makes `_predict_internal` package-private, so only
    `core` may import it. `adapters.mcp` is foreign to `core` and reaching the
    private module directly, which is the shape the contract forbids.
    """
    with import_linter_sandbox.injected(_MCP_MODULE, _IMPORTS_A_PRIVATE_MODULE):
        result = import_linter_sandbox.run()

    assert result.broken == {PACKAGE_PRIVATE_CONTRACT}, (
        "an outside package importing `core._predict_internal` must break exactly the "
        f"package-private contract:\n{result.output}"
    )
    assert result.exit_code == 1
    assert (
        "graph_skill_runtime.adapters.mcp -> graph_skill_runtime.core._predict_internal"
        in result.output
    )
