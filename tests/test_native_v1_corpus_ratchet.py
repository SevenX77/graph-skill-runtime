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
One entry per **test module** (``test_*.py``) outside ``tests/migration/`` whose
imports reach the converter package, directly or through any chain of other
modules inside ``tests/``.

Counted population and traversal are deliberately different sets. Traversal
walks **every** ``.py`` under ``tests/`` -- helpers, ``conftest.py``, package
``__init__.py`` -- because those files are how a test reaches the converter
without naming it. Counting only what they carry keeps one entry per behavioral
module, which is what the pinned number means.

Reaching the converter means importing ``graph_skill_runtime.migration`` or any
submodule, in any syntactic form: ``import a.b``, ``import a.b as c``,
``from a.b import x``, ``from a import b``. Detection is by MODULE, not by the
name of a function or of one particular shim file, because a name-based rule is
trivially evaded. ``test_the_gate_survives_the_evasions_that_defeat_a_name_based_rule``
pins three evasions that the name-based predecessor of this gate permitted.

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

``CONVERTER_VOCABULARY_ONLY`` names files that import converter *types* without
authoring or converting a fixture. Adding a name there is as visible in review
as raising the pin, and the set is asserted exact so an entry cannot be added
silently.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
LEGACY_ADAPTER = TESTS_ROOT / "legacy_fixture_adapter.py"

#: The converter package. Any module at or below it is legacy v0.3 parsing.
CONVERTER_PACKAGE = ("graph_skill_runtime", "migration")

#: The converter's own tests; a v0.3 fixture is their subject.
CONVERTER_OWNED_DIRS = ("migration",)

#: Files that import converter types but never author or convert a fixture.
#: ``test_error_code_vocabulary_layers.py`` imports ``MigrationErrorCode`` and
#: ``MigrationDiagnostic`` to assert that the converter's error vocabulary is a
#: layer separate from the runtime's. It reads the enum; it never writes a v0.3
#: bundle and never calls the converter, so it is not corpus.
CONVERTER_VOCABULARY_ONLY: frozenset[str] = frozenset(
    {"test_error_code_vocabulary_layers.py"}
)

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


def _module_key(path: Path, tests_root: Path) -> tuple[str, ...]:
    """Dotted parts of an importable module, rooted at the ``tests`` package."""

    relative = path.relative_to(tests_root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ("tests", *parts)


def _imports_the_converter(node: ast.Import | ast.ImportFrom) -> bool:
    """True when this statement names the converter package in any form."""

    depth = len(CONVERTER_PACKAGE)
    if isinstance(node, ast.Import):
        return any(
            tuple(alias.name.split("."))[:depth] == CONVERTER_PACKAGE
            for alias in node.names
        )
    if node.module is None:
        return False
    parts = tuple(node.module.split("."))
    if parts[:depth] == CONVERTER_PACKAGE:
        return True
    # ``from graph_skill_runtime import migration`` names the package as a symbol.
    return parts == CONVERTER_PACKAGE[:-1] and any(
        alias.name == CONVERTER_PACKAGE[-1] for alias in node.names
    )


def _local_imports(
    node: ast.Import | ast.ImportFrom, *, own_key: tuple[str, ...]
) -> Iterator[tuple[str, ...]]:
    """Module keys this statement imports from inside the ``tests`` package."""

    if isinstance(node, ast.Import):
        for alias in node.names:
            parts = tuple(alias.name.split("."))
            if parts[:1] == ("tests",):
                yield parts
        return
    if node.level:
        base = own_key[: len(own_key) - node.level]
        parts = (*base, *node.module.split(".")) if node.module else base
    elif node.module is None:
        return
    else:
        parts = tuple(node.module.split("."))
    if parts[:1] != ("tests",):
        return
    yield parts
    # ``from tests.pkg import module`` also names ``tests.pkg.module``.
    for alias in node.names:
        yield (*parts, alias.name)


def _reaches_converter(tests_root: Path) -> set[tuple[str, ...]]:
    """Every module key under ``tests_root`` whose imports reach the converter."""

    direct: set[tuple[str, ...]] = set()
    edges: dict[tuple[str, ...], set[tuple[str, ...]]] = {}

    for path in sorted(tests_root.rglob("*.py")):
        key = _module_key(path, tests_root)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        targets: set[tuple[str, ...]] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            if _imports_the_converter(node):
                direct.add(key)
            targets.update(_local_imports(node, own_key=key))
        edges[key] = targets

    reaching = set(direct)
    changed = True
    while changed:
        changed = False
        for key, targets in edges.items():
            if key not in reaching and any(target in reaching for target in targets):
                reaching.add(key)
                changed = True
    return reaching


def legacy_corpus_modules(tests_root: Path | None = None) -> frozenset[str]:
    """Test modules outside the converter's own area that still reach it."""

    root = tests_root or TESTS_ROOT
    reaching = _reaches_converter(root)
    found = set()
    for path in sorted(root.rglob("test_*.py")):
        relative = path.relative_to(root)
        if relative.parts[0] in CONVERTER_OWNED_DIRS:
            continue
        if relative.as_posix() in CONVERTER_VOCABULARY_ONLY:
            continue
        if _module_key(path, root) in reaching:
            found.add(relative.as_posix())
    return frozenset(found)


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


def test_the_vocabulary_exemption_stays_exactly_what_review_approved() -> None:
    """An exemption must be as visible in review as raising the pin."""

    present = {
        path.relative_to(TESTS_ROOT).as_posix()
        for path in TESTS_ROOT.rglob("test_*.py")
        if path.relative_to(TESTS_ROOT).as_posix() in CONVERTER_VOCABULARY_ONLY
    }
    assert present == set(CONVERTER_VOCABULARY_ONLY), (
        "CONVERTER_VOCABULARY_ONLY names a file that does not exist; "
        f"tree has {sorted(present)}, pin has {sorted(CONVERTER_VOCABULARY_ONLY)}"
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
# The predecessor of this gate matched two literal names: an import of
# ``tests.legacy_fixture_adapter``, or a call whose callee was spelled
# ``migrate_studio_skill``. Cross-review demonstrated that a forwarding helper
# defeats it. Each row below is a synthetic tests/ tree that reaches the real
# converter; the old rule is reproduced verbatim so every row proves BOTH that
# it was permitted and that it is now rejected.


def _old_name_based_rule(tests_root: Path) -> frozenset[str]:
    """The superseded detector, kept only as the mutation table's control."""

    found = set()
    for path in sorted(tests_root.rglob("test_*.py")):
        relative = path.relative_to(tests_root)
        if relative.parts[0] in CONVERTER_OWNED_DIRS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "tests.legacy_fixture_adapter":
                found.add(relative.as_posix())
            elif isinstance(node, ast.Import) and any(
                alias.name == "tests.legacy_fixture_adapter" for alias in node.names
            ):
                found.add(relative.as_posix())
            elif isinstance(node, ast.Call):
                callee = node.func
                name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
                if name == "migrate_studio_skill":
                    found.add(relative.as_posix())
    return frozenset(found)


_SHIM_BODY = """from graph_skill_runtime.migration import migrate_studio_skill


def portable_fixture_root(root):
    return migrate_studio_skill(root, root.parent / "out")
"""

_EVASIONS: dict[str, dict[str, str]] = {
    # A helper re-exports the shim, so the test names neither the shim module
    # nor the converter function.
    "forwarding helper": {
        "legacy_fixture_adapter.py": _SHIM_BODY,
        "corpus_helpers.py": "from tests.legacy_fixture_adapter import portable_fixture_root\n",
        "core/test_evasion.py": (
            "from tests.corpus_helpers import portable_fixture_root\n\n\n"
            "def test_evasion(tmp_path):\n"
            "    assert portable_fixture_root is not None\n"
        ),
    },
    # The shim is copied under a new filename, so the pinned module name misses.
    "renamed shim": {
        "corpus_bridge.py": _SHIM_BODY,
        "core/test_evasion.py": (
            "from tests.corpus_bridge import portable_fixture_root\n\n\n"
            "def test_evasion(tmp_path):\n"
            "    assert portable_fixture_root is not None\n"
        ),
    },
    # The converter is imported under an alias and reached through a second
    # entry point, so no call is spelled ``migrate_studio_skill``.
    "aliased converter import": {
        "core/test_evasion.py": (
            "import graph_skill_runtime.migration as legacy\n\n\n"
            "def test_evasion(tmp_path):\n"
            "    assert legacy.atomic_publish is not None\n"
        ),
    },
}


def _materialize(root: Path, files: dict[str, str]) -> None:
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")


def test_the_gate_survives_the_evasions_that_defeat_a_name_based_rule(
    tmp_path: Path,
) -> None:
    for label, files in _EVASIONS.items():
        root = tmp_path / label.replace(" ", "-")
        root.mkdir()
        _materialize(root, files)

        assert "core/test_evasion.py" not in _old_name_based_rule(root), (
            f"the {label} evasion was supposed to slip past the old name-based "
            "rule; if it no longer does, this row has stopped proving anything"
        )
        assert "core/test_evasion.py" in legacy_corpus_modules(root), (
            f"the {label} evasion reaches the converter but the gate missed it"
        )
