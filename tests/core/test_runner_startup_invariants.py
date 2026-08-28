"""Keep the embedded runner free of process-global startup side effects.

The only supported process adapter is ``graph_skill_runtime.adapters.cli`` via
the installed ``gskill`` command. Core execution must not grow a second CLI or
mutate interpreter-global environment, import paths, or module state.
"""

from __future__ import annotations

import re
from pathlib import Path

from graph_skill_runtime.core import runner as runner_module

SRC_RUNNER = Path(runner_module.__file__)
SRC_CORE_INIT = SRC_RUNNER.parent / "__init__.py"


# Pattern intentionally rejects bare uses (``os.environ.get``,
# ``sys.path.append``, ``sys.modules[...] = ...``); a comment or
# docstring referencing the symbol is fine because we anchor on the
# preceding ``=`` / ``.`` punctuation rather than the bare token.
_HACK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("os.environ assignment / mutation", re.compile(r"\bos\.environ\s*\[")),
    ("os.environ method call", re.compile(r"\bos\.environ\.\w+\s*\(")),
    ("sys.path mutation", re.compile(r"\bsys\.path\.\w+\s*\(")),
    ("sys.path subscript assignment", re.compile(r"\bsys\.path\s*\[")),
    ("sys.modules subscript", re.compile(r"\bsys\.modules\s*\[")),
]


def _scan_for_hacks(path: Path) -> list[tuple[str, int, str]]:
    """Return (pattern_label, line_no, line_text) for each match."""
    findings: list[tuple[str, int, str]] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        # Strip inline comments before pattern check so docstring/comment
        # mentions of the symbols don't trigger a false positive.
        code_segment = line.split("#", 1)[0]
        for label, pattern in _HACK_PATTERNS:
            if pattern.search(code_segment):
                findings.append((label, line_no, line.strip()))
    return findings


class TestRunnerStartupInvariants:
    def test_runner_py_has_no_direct_environ_or_sys_hacks(self) -> None:
        findings = _scan_for_hacks(SRC_RUNNER)

        assert findings == [], (
            "runner.py must route startup side-effects through Bootstrap; "
            f"found direct hacks: {findings!r}"
        )

    def test_core_init_py_has_no_direct_environ_or_sys_hacks(self) -> None:
        findings = _scan_for_hacks(SRC_CORE_INIT)

        assert findings == [], (
            "core/__init__.py must stay a pure re-export module — no "
            f"startup side-effects; found: {findings!r}"
        )
