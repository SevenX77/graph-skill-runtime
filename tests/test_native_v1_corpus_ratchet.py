"""Ratchet: the legacy v0.3 converter must keep leaving the test corpus.

The runtime's contract cutover rule (`AGENTS.md` section 4) confines legacy v0.3
parsing to the explicit ``gskill migrate studio-skill`` boundary and forbids it
from becoming a fallback. A behavioral test that authors a v0.3 fixture and
converts it before exercising current runtime behavior puts that converter on
the hot path of engine coverage: a converter defect then silently reshapes the
corpus that is supposed to prove engine behavior, and the failure surfaces as an
engine failure. The fix is native portable gSkill v1 corpus, so this gate exists
to make the remaining conversions monotonically decrease.

Two entry points count as feeding corpus through the converter:

1. importing ``tests.legacy_fixture_adapter``, the shim that migrates an authored
   v0.3 fixture into a temporary directory before calling the production API;
2. calling ``migrate_studio_skill`` directly on a fixture the test authored.

``tests/migration/`` is exempt: those tests own the converter itself, and a v0.3
fixture is their legitimate input rather than a stand-in for engine corpus. A
test that merely names ``GRAPH.md`` to assert the current loader REJECTS it is
also not counted — it never reaches a legacy reader.

The pinned number may only go down. Lowering it is the point; raising it means a
new test was written against the retired format, which the cutover rule forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
LEGACY_ADAPTER = TESTS_ROOT / "legacy_fixture_adapter.py"

# Exempt: these tests own the converter, so a v0.3 fixture is their subject.
CONVERTER_OWNED_DIRS = ("migration",)

# Pinned current count. Only ever lower this, together with the conversion that
# earns it. See the module docstring for why raising it is a defect. The target
# is 0: at that point the shim below is dead and must be deleted with it.
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


def _is_converter_owned(path: Path) -> bool:
    relative = path.relative_to(TESTS_ROOT)
    return relative.parts[0] in CONVERTER_OWNED_DIRS


def _feeds_corpus_through_the_converter(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tests.legacy_fixture_adapter":
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == "tests.legacy_fixture_adapter" for alias in node.names):
                return True
        if isinstance(node, ast.Call):
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
            if name == "migrate_studio_skill":
                return True
    return False


def legacy_corpus_modules() -> frozenset[str]:
    """Return every test module outside the converter's own area that still feeds it."""

    found = set()
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if _is_converter_owned(path):
            continue
        if _feeds_corpus_through_the_converter(path):
            found.add(path.relative_to(TESTS_ROOT).as_posix())
    return frozenset(found)


def test_no_new_test_module_feeds_corpus_through_the_legacy_converter() -> None:
    modules = legacy_corpus_modules()
    added = sorted(modules - EXPECTED_LEGACY_CORPUS_MODULES)
    assert not added, (
        "these test modules newly author v0.3 corpus and convert it before exercising "
        "current runtime behavior; author native portable gSkill v1 fixtures instead "
        f"(see docs/skill-spec/01-PORTABLE-GSKILL-V1.md): {added}"
    )
    assert len(modules) <= MAX_LEGACY_CORPUS_MODULES, (
        f"{len(modules)} modules still feed the converter, above the pinned "
        f"{MAX_LEGACY_CORPUS_MODULES}"
    )


def test_the_pinned_expectation_matches_the_tree() -> None:
    """A conversion must lower the pin, so a stale pin is itself a defect."""

    modules = legacy_corpus_modules()
    converted = sorted(EXPECTED_LEGACY_CORPUS_MODULES - modules)
    assert not converted, (
        "these modules no longer feed the converter; remove them from "
        f"EXPECTED_LEGACY_CORPUS_MODULES and lower MAX_LEGACY_CORPUS_MODULES: {converted}"
    )
    assert len(EXPECTED_LEGACY_CORPUS_MODULES) == MAX_LEGACY_CORPUS_MODULES


def test_the_shim_is_gone_once_nothing_feeds_it() -> None:
    """The adapter is the migration path itself; at zero it must not survive."""

    if MAX_LEGACY_CORPUS_MODULES == 0:
        assert not LEGACY_ADAPTER.exists(), (
            "no test module feeds the legacy converter any more, so "
            f"{LEGACY_ADAPTER.name} is dead migration machinery and must be deleted"
        )
