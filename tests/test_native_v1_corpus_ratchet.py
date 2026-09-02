"""Ratchet: the legacy v0.3 converter must keep leaving the test corpus.

``AGENTS.md`` section 4 confines legacy v0.3 parsing to the explicit
``gskill migrate studio-skill`` converter boundary and forbids it from becoming
a fallback. A behavioral test that authors a v0.3 fixture and converts it before
exercising current runtime behavior breaks that rule in the direction the
sentence does not name: the converter is not a *fallback* there, it is the only
reader the test exercises, so a converter defect and an engine defect become
indistinguishable -- the bundle the engine sees is the converter's output rather
than the text the test author wrote. The fix is native portable gSkill v1
corpus, and this gate makes the remaining conversions monotonically decrease.

What is counted
---------------
One entry per **test module** (``test_*.py``) under ``tests/`` and outside
``tests/migration/`` whose imports reach the converter package, directly or
through any chain of modules elsewhere in this repository.

Counted population and traversal are deliberately different sets. Traversal
walks **every** ``.py`` in the repository except ``src/`` -- ``tests/**``,
``scripts/**``, ``tools/**``, helpers, ``conftest.py``, package ``__init__.py``
-- because those files are how a test reaches the converter without naming it.
Counting only what they carry keeps one entry per behavioral module, which is
what the pinned number means.

Division of labor with the import-linter contract
-------------------------------------------------
This gate owns everything OUTSIDE ``src/``. Forwarding *inside*
``src/graph_skill_runtime`` is owned by the import-linter contract, whose
``root_package`` is ``graph_skill_runtime``; a module there that re-exports the
converter is that contract's subject, not this one's. The two are complementary
and neither is a substitute: import-linter does not see ``tests/`` or
``scripts/``, and this gate does not police the runtime's internal layering.

Reaching the converter
----------------------
An import reaches the converter when it names ``graph_skill_runtime.migration``
or any submodule, through either route:

*Static* -- ``import a.b``, ``import a.b as c``, ``from a.b import x``,
``from a import b``.

*Dynamic* -- a call to ``importlib.import_module``, ``__import__`` or
``pytest.importorskip`` (by attribute or bare name). With a string-literal first
argument, the literal is matched like a module name. With a non-literal first
argument, the call counts when the module *also* contains any string constant
starting with the converter's dotted name.

That last rule is deliberately blunt. Deciding whether a computed argument
evaluates to the converter needs constant propagation across the module, and a
gate that attempts it becomes both slower and arguable. The asymmetry decides
it: a false positive is one named line in a diff that a reviewer can see and
argue with, while a false negative is a silent bypass of the whole gate -- which
is exactly how the two preceding versions of this file were defeated. Measured
against this repository the blunt rule costs nothing: 53 dynamic-import calls
across 16 modules outside ``src/``, zero of them counted.

Detection is by MODULE, never by the name of a function or of one particular
shim file. ``test_the_gate_survives_the_evasions_that_defeated_its_predecessors``
pins five evasions, each against the superseded rule that permitted it.

Baseline and arithmetic
-----------------------
On ``origin/main`` this counts **45** modules: 44 that imported
``tests/legacy_fixture_adapter.py`` -- the shim that migrated an authored v0.3
fixture into a temporary directory before calling the production API -- plus 1
that imported the converter package directly.

The first change of this series took that to 25. Its ``-20`` is **19 modules
made native plus 1 test relocated**: the relocated one carried a converter
assertion that had been living in ``tests/core/``, and moving it to
``tests/migration/`` returns converter subject matter to the converter's own
area. A relocation is not a behavioral module made native, so the two are
counted separately and the arithmetic cannot be read as "20 conversions".

Exemptions
----------
``tests/migration/`` is exempt wholesale: those tests own the converter, so a
v0.3 fixture is their subject rather than a stand-in for engine corpus.

One import FORM is exempt, and no file is: a plain
``from graph_skill_runtime.migration.studio_v030 import MigrationDiagnostic``
and/or ``MigrationErrorCode``, unaliased, imports the converter's error-code
types rather than its behavior. Any other name, any other submodule, any alias,
and any dynamic import counts as usual -- including in the same file. A file
that reads the enum today therefore starts counting the moment it also imports
``migrate_studio_skill``, with no pin to raise and no allowlist to edit.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent
LEGACY_ADAPTER = TESTS_ROOT / "legacy_fixture_adapter.py"

#: The converter package. Any module at or below it is legacy v0.3 parsing.
CONVERTER_PACKAGE = ("graph_skill_runtime", "migration")
CONVERTER_PREFIX = ".".join(CONVERTER_PACKAGE)

#: The converter's own tests; a v0.3 fixture is their subject.
CONVERTER_OWNED_DIRS = ("migration",)

#: Owned by the import-linter contract instead; see the module docstring.
IMPORT_LINTER_OWNED = ("src",)

#: Never source, so never a path to the converter.
UNSCANNED_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".worktrees",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
    }
)

#: Callables that import a module named at runtime.
DYNAMIC_IMPORT_CALLS = frozenset({"import_module", "__import__", "importorskip"})

#: The only converter names that are types rather than behavior.
VOCABULARY_MODULE = "graph_skill_runtime.migration.studio_v030"
VOCABULARY_NAMES = frozenset({"MigrationDiagnostic", "MigrationErrorCode"})

# Pinned current count. Only ever lower this, together with the conversion that
# earns it. See the module docstring for why raising it is a defect. The target
# is 0, at which point the shim is dead and must be deleted with it.
MAX_LEGACY_CORPUS_MODULES = 25

# The exact remaining modules, so removing one here while adding another
# elsewhere cannot keep the total flat and hide a regression.
EXPECTED_LEGACY_CORPUS_MODULES: frozenset[str] = frozenset(
    {
        "core/test_a_phase_says_how_it_ended.py",
        "core/test_a_phase_that_never_got_its_input.py",
        "core/test_agent_loop_iteration_is_per_execution.py",
        "core/test_agent_phase_input_delivery.py",
        "core/test_batch_item_isolation.py",
        "core/test_checkpoint_validity_red.py",
        "core/test_events_name_their_execution.py",
        "core/test_gamma2_child_graph_isolation.py",
        "core/test_gamma2_phase_outputs_flow.py",
        "core/test_gamma2_reference_reader_sandbox.py",
        "core/test_iterate_token_accounting.py",
        "core/test_llm_call_announces_its_start.py",
        "core/test_llm_step_closes_when_the_call_returns.py",
        "core/test_phase_spend_has_one_answer.py",
        "core/test_productization_run_by_artifact_red.py",
        "core/test_tool_call_history_integrity.py",
        "core/test_workspace_dir_contract_red.py",
        "core/test_ws_e1_io_runtime_red.py",
        "core/test_ws_e1_subgraph_io_contract_red.py",
        "core/test_ws_e5_checkpoint_inner_red.py",
        "core/test_ws_e8_exit_gate_red.py",
        "e2e/test_agent_node_observability.py",
        "e2e/test_tool_call_started_e2e.py",
        "e2e/test_ws_e1_create_agent_step1.py",
        "e2e/test_ws_e1_io_runtime.py",
    }
)


# --------------------------------------------------------------------------
# Source discovery
# --------------------------------------------------------------------------


def _scanned_files(repo_root: Path) -> Iterator[Path]:
    """Every ``.py`` this gate owns: the repository minus ``src/`` and caches."""

    def walk(directory: Path) -> Iterator[Path]:
        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if entry.name in UNSCANNED_DIRS or entry.name.startswith("."):
                    continue
                if entry.parent == repo_root and entry.name in IMPORT_LINTER_OWNED:
                    continue
                yield from walk(entry)
            elif entry.suffix == ".py":
                yield entry

    yield from walk(repo_root)


def _module_key(path: Path, repo_root: Path) -> tuple[str, ...]:
    """Dotted parts of an importable module, rooted at the repository."""

    relative = path.relative_to(repo_root).with_suffix("")
    if relative.name == "__init__":
        return relative.parts[:-1]
    return relative.parts


# --------------------------------------------------------------------------
# Import classification
# --------------------------------------------------------------------------


def _names_converter(dotted: str) -> bool:
    return tuple(dotted.split("."))[: len(CONVERTER_PACKAGE)] == CONVERTER_PACKAGE


def _is_vocabulary_only(node: ast.ImportFrom) -> bool:
    """True for an unaliased import of the converter's error-code types alone."""

    if node.module != VOCABULARY_MODULE or node.level:
        return False
    return all(
        alias.asname is None and alias.name in VOCABULARY_NAMES for alias in node.names
    )


def _static_import_reaches_converter(node: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(node, ast.Import):
        return any(_names_converter(alias.name) for alias in node.names)
    if node.module is None or node.level:
        return False
    if _is_vocabulary_only(node):
        return False
    if _names_converter(node.module):
        return True
    # ``from graph_skill_runtime import migration`` names the package as a symbol.
    return tuple(node.module.split(".")) == CONVERTER_PACKAGE[:-1] and any(
        alias.name == CONVERTER_PACKAGE[-1] for alias in node.names
    )


def _dynamic_import_calls(tree: ast.AST) -> Iterator[ast.Call]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
        if name in DYNAMIC_IMPORT_CALLS:
            yield node


def _literal_first_argument(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _mentions_converter_literal(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(CONVERTER_PREFIX)
        for node in ast.walk(tree)
    )


def _dynamic_literal_names_converter(tree: ast.AST) -> bool:
    """A dynamic import whose first argument literally names the converter."""

    return any(
        (literal := _literal_first_argument(call)) is not None and _names_converter(literal)
        for call in _dynamic_import_calls(tree)
    )


def _dynamic_computed_may_name_converter(tree: ast.AST) -> bool:
    """The blunt rule: a computed argument plus a converter literal anywhere.

    Kept separate from the literal rule so the two can be told apart. Only this
    one trades precision for safety, so only this one has a cost to keep visible
    -- see ``test_the_blunt_dynamic_import_rule_costs_this_repository_nothing``.
    """

    computed = any(
        _literal_first_argument(call) is None for call in _dynamic_import_calls(tree)
    )
    return computed and _mentions_converter_literal(tree)


def _dynamic_imports_reach_converter(tree: ast.AST) -> bool:
    """See the module docstring for why a non-literal argument is blunt."""

    return _dynamic_literal_names_converter(tree) or _dynamic_computed_may_name_converter(
        tree
    )


def _local_import_targets(
    tree: ast.AST, *, own_key: tuple[str, ...]
) -> set[tuple[str, ...]]:
    """Module keys this file imports from elsewhere in the repository."""

    targets: set[tuple[str, ...]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(tuple(alias.name.split(".")))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = own_key[: max(len(own_key) - node.level, 0)]
                parts = (*base, *node.module.split(".")) if node.module else base
            elif node.module is None:
                continue
            else:
                parts = tuple(node.module.split("."))
            targets.add(parts)
            # ``from pkg import module`` also names ``pkg.module``.
            for alias in node.names:
                targets.add((*parts, alias.name))
    for call in _dynamic_import_calls(tree):
        literal = _literal_first_argument(call)
        if literal:
            targets.add(tuple(literal.split(".")))
    return targets


# --------------------------------------------------------------------------
# Reachability
# --------------------------------------------------------------------------


def _close_over_imports(
    direct: set[tuple[str, ...]], edges: dict[tuple[str, ...], set[tuple[str, ...]]]
) -> set[tuple[str, ...]]:
    """Everything that imports something already reaching the converter."""

    reaching = set(direct)
    changed = True
    while changed:
        changed = False
        for key, targets in edges.items():
            if key not in reaching and any(target in reaching for target in targets):
                reaching.add(key)
                changed = True
    return reaching


def _reaches_converter(repo_root: Path) -> set[tuple[str, ...]]:
    """Every module key under ``repo_root`` whose imports reach the converter."""

    direct: set[tuple[str, ...]] = set()
    edges: dict[tuple[str, ...], set[tuple[str, ...]]] = {}

    for path in _scanned_files(repo_root):
        key = _module_key(path, repo_root)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            _static_import_reaches_converter(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
        ) or _dynamic_imports_reach_converter(tree):
            direct.add(key)
        edges[key] = _local_import_targets(tree, own_key=key)

    return _close_over_imports(direct, edges)


def legacy_corpus_modules(repo_root: Path | None = None) -> frozenset[str]:
    """Test modules outside the converter's own area that still reach it."""

    root = repo_root or REPO_ROOT
    reaching = _reaches_converter(root)
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return frozenset()
    found = set()
    for path in sorted(tests_root.rglob("test_*.py")):
        relative = path.relative_to(tests_root)
        if relative.parts[0] in CONVERTER_OWNED_DIRS:
            continue
        if _module_key(path, root) in reaching:
            found.add(relative.as_posix())
    return frozenset(found)


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def test_no_new_test_module_feeds_corpus_through_the_legacy_converter() -> None:
    modules = legacy_corpus_modules()
    added = sorted(modules - EXPECTED_LEGACY_CORPUS_MODULES)
    assert not added, (
        "these test modules reach the legacy v0.3 converter; author native "
        "portable gSkill v1 fixtures instead "
        f"(see docs/skill-spec/01-PORTABLE-GSKILL-V1.md): {added}"
    )
    assert len(modules) <= MAX_LEGACY_CORPUS_MODULES, (
        f"{len(modules)} modules still reach the converter, above the pinned "
        f"{MAX_LEGACY_CORPUS_MODULES}"
    )


def test_the_pinned_expectation_matches_the_tree() -> None:
    """A conversion must lower the pin, so a stale pin is itself a defect."""

    modules = legacy_corpus_modules()
    converted = sorted(EXPECTED_LEGACY_CORPUS_MODULES - modules)
    assert not converted, (
        "these modules no longer reach the converter; remove them from "
        f"EXPECTED_LEGACY_CORPUS_MODULES and lower MAX_LEGACY_CORPUS_MODULES: {converted}"
    )
    assert len(EXPECTED_LEGACY_CORPUS_MODULES) == MAX_LEGACY_CORPUS_MODULES


def test_the_blunt_dynamic_import_rule_costs_this_repository_nothing() -> None:
    """A non-literal dynamic import counts only alongside a converter literal.

    That rule trades false positives for the absence of false negatives, so its
    price has to stay visible: every dynamic import already in this repository
    must remain uncounted, and a change that makes one count is a change the
    author has to see.
    """

    counted = []
    for path in _scanned_files(REPO_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not _dynamic_computed_may_name_converter(tree):
            continue
        # Anything the precise rules already catch is not this rule's cost.
        if _dynamic_literal_names_converter(tree):
            continue
        if any(
            _static_import_reaches_converter(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
        ):
            continue
        counted.append(path.relative_to(REPO_ROOT).as_posix())
    assert not counted, (
        "these modules are counted ONLY because a computed dynamic-import "
        "argument sits in a file that also mentions the converter by name; "
        f"confirm each really reaches the converter: {counted}"
    )


def test_the_shim_is_gone_once_nothing_feeds_it() -> None:
    """The adapter is the migration path itself; at zero it must not survive."""

    if MAX_LEGACY_CORPUS_MODULES == 0:
        assert not LEGACY_ADAPTER.exists(), (
            "no test module reaches the legacy converter any more, so "
            f"{LEGACY_ADAPTER.name} is dead migration machinery and must be deleted"
        )


# --------------------------------------------------------------------------
# Mutation table
# --------------------------------------------------------------------------
# Two rules preceded this one, and cross-review defeated each. Both are kept
# below as controls so every row proves BOTH halves: the evasion WAS permitted
# by the rule it defeated, and it is rejected now. A row that stops proving the
# first half fails too, so the table cannot rot into a tautology.
#
#   r0 -- matched two literal names: an import of `tests.legacy_fixture_adapter`,
#         or a call spelled `migrate_studio_skill`.
#   r1 -- matched the converter module, but only through static imports, and
#         only along chains inside `tests/`.


def _r0_name_based_rule(repo_root: Path) -> frozenset[str]:
    tests_root = repo_root / "tests"
    found = set()
    for path in sorted(tests_root.rglob("test_*.py")):
        relative = path.relative_to(tests_root)
        if relative.parts[0] in CONVERTER_OWNED_DIRS:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "tests.legacy_fixture_adapter":
                found.add(relative.as_posix())
            elif isinstance(node, ast.Import) and any(
                alias.name == "tests.legacy_fixture_adapter" for alias in node.names
            ):
                found.add(relative.as_posix())
            elif isinstance(node, ast.Call):
                callee = node.func
                name = (
                    callee.attr
                    if isinstance(callee, ast.Attribute)
                    else getattr(callee, "id", None)
                )
                if name == "migrate_studio_skill":
                    found.add(relative.as_posix())
    return frozenset(found)


def _r1_tests_only_static_rule(repo_root: Path) -> frozenset[str]:
    tests_root = repo_root / "tests"
    direct: set[tuple[str, ...]] = set()
    edges: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    for path in sorted(tests_root.rglob("*.py")):
        key = ("tests", *_module_key(path, tests_root))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        targets: set[tuple[str, ...]] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            if _static_import_reaches_converter(node):
                direct.add(key)
            targets.update(
                target
                for target in _local_import_targets(node, own_key=key)
                if target[:1] == ("tests",)
            )
        edges[key] = targets
    reaching = _close_over_imports(direct, edges)
    found = set()
    for path in sorted(tests_root.rglob("test_*.py")):
        relative = path.relative_to(tests_root)
        if relative.parts[0] in CONVERTER_OWNED_DIRS:
            continue
        if ("tests", *_module_key(path, tests_root)) in reaching:
            found.add(relative.as_posix())
    return frozenset(found)


_SHIM_BODY = """from graph_skill_runtime.migration import migrate_studio_skill


def portable_fixture_root(root):
    return migrate_studio_skill(root, root.parent / "out")
"""

_EVASIONS: dict[str, tuple[str, dict[str, str]]] = {
    # A helper re-exports the shim, so the test names neither the shim module
    # nor the converter function.
    "forwarding helper": (
        "r0",
        {
            "tests/legacy_fixture_adapter.py": _SHIM_BODY,
            "tests/corpus_helpers.py": (
                "from tests.legacy_fixture_adapter import portable_fixture_root\n"
            ),
            "tests/core/test_evasion.py": (
                "from tests.corpus_helpers import portable_fixture_root\n\n\n"
                "def test_evasion(tmp_path):\n"
                "    assert portable_fixture_root is not None\n"
            ),
        },
    ),
    # The shim is copied under a new filename, so a pinned module name misses.
    "renamed shim": (
        "r0",
        {
            "tests/corpus_bridge.py": _SHIM_BODY,
            "tests/core/test_evasion.py": (
                "from tests.corpus_bridge import portable_fixture_root\n\n\n"
                "def test_evasion(tmp_path):\n"
                "    assert portable_fixture_root is not None\n"
            ),
        },
    ),
    # The converter is aliased and reached through a second entry point, so no
    # call is spelled ``migrate_studio_skill``.
    "aliased converter import": (
        "r0",
        {
            "tests/core/test_evasion.py": (
                "import graph_skill_runtime.migration as legacy\n\n\n"
                "def test_evasion(tmp_path):\n"
                "    assert legacy.atomic_publish is not None\n"
            ),
        },
    ),
    # The bridge lives outside tests/, where a tests-only graph cannot see it.
    "scripts bridge": (
        "r1",
        {
            "scripts/corpus_bridge.py": _SHIM_BODY,
            "tests/core/test_evasion.py": (
                "from scripts.corpus_bridge import portable_fixture_root\n\n\n"
                "def test_evasion(tmp_path):\n"
                "    assert portable_fixture_root is not None\n"
            ),
        },
    ),
    # The converter name never appears in an import statement at all.
    "dynamic import": (
        "r1",
        {
            "tests/core/test_evasion.py": (
                "import importlib\n\n\n"
                "def test_evasion(tmp_path):\n"
                '    legacy = importlib.import_module("graph_skill_runtime.migration")\n'
                "    assert legacy.migrate_studio_skill is not None\n"
            ),
        },
    ),
}

_CONTROLS = {"r0": _r0_name_based_rule, "r1": _r1_tests_only_static_rule}


def _materialize(root: Path, files: dict[str, str]) -> None:
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")


def test_the_gate_survives_the_evasions_that_defeated_its_predecessors(
    tmp_path: Path,
) -> None:
    for label, (control_name, files) in _EVASIONS.items():
        root = tmp_path / label.replace(" ", "-")
        (root / "tests").mkdir(parents=True)
        _materialize(root, files)
        control = _CONTROLS[control_name]

        assert "core/test_evasion.py" not in control(root), (
            f"the {label} evasion was supposed to slip past {control_name}; if it "
            "no longer does, this row has stopped proving anything"
        )
        assert "core/test_evasion.py" in legacy_corpus_modules(root), (
            f"the {label} evasion reaches the converter but the gate missed it"
        )


def test_the_error_code_types_stay_importable_without_counting(tmp_path: Path) -> None:
    """The exemption is one import FORM, not a file.

    A module that reads the converter's error-code enum is not corpus. The same
    module starts counting the moment it imports anything else from the
    converter, so the exemption cannot be widened by adding a line.
    """

    root = tmp_path / "vocabulary"
    (root / "tests").mkdir(parents=True)
    vocabulary_only = (
        "from graph_skill_runtime.migration.studio_v030 import (\n"
        "    MigrationDiagnostic,\n"
        "    MigrationErrorCode,\n"
        ")\n\n\n"
        "def test_layers():\n"
        "    assert MigrationDiagnostic is not None\n"
        "    assert MigrationErrorCode is not None\n"
    )
    _materialize(root, {"tests/test_vocabulary.py": vocabulary_only})
    assert legacy_corpus_modules(root) == frozenset()

    _materialize(
        root,
        {
            "tests/test_vocabulary.py": vocabulary_only
            + "\n\nfrom graph_skill_runtime.migration import migrate_studio_skill\n"
        },
    )
    assert legacy_corpus_modules(root) == frozenset({"test_vocabulary.py"})

    _materialize(
        root,
        {
            "tests/test_vocabulary.py": (
                "from graph_skill_runtime.migration.studio_v030 import (\n"
                "    MigrationErrorCode as Codes,\n"
                ")\n\n\n"
                "def test_layers():\n"
                "    assert Codes is not None\n"
            )
        },
    )
    assert legacy_corpus_modules(root) == frozenset({"test_vocabulary.py"}), (
        "an alias hides which name was imported, so it is not the exempt form"
    )
