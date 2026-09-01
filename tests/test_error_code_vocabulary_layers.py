"""Every error code in this runtime belongs to exactly one declared layer.

Before this gate the repository carried three error-code vocabularies but
documented only one. ``ERROR_REGISTRY`` (the ``[F-v3-*]`` skill-diagnostics
catalog) had a mechanically checked bijection with
``docs/skill-spec/11-error-code-spec.md``; the eight ``RuntimeErrorCode``
members and the twenty-six ``GSKILL_MIGRATION_*`` converter codes appeared
nowhere in that catalog (``grep`` count 0), and the converter codes were bare
``str`` literals at 66 call sites, so a typo silently minted a twenty-seventh
code that no document, type, or test knew about.

The adjudication (D-T13) keeps the three vocabularies as three separate layers
rather than merging them into ``ERROR_REGISTRY``, because ``ERROR_REGISTRY``
membership is what makes a string a legal ``ErrorPayload.code`` — a compile
diagnostic. Admitting converter codes there would make the frozen v0.3
vocabulary constructible inside the current compile-diagnostics closed set,
which is exactly the boundary blur ``AGENTS.md`` §4 forbids. The layers are
therefore declared in ``11-error-code-spec.md`` §9, each with a named machine
mirror, and this test is the mechanical check that no fourth, undeclared
vocabulary can appear.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from graph_skill_runtime.core.error_registry import ERROR_REGISTRY
from graph_skill_runtime.core.exceptions import _EXTERNAL_ERROR_CODE_PREFIXES
from graph_skill_runtime.domain.models import RuntimeErrorCode
from graph_skill_runtime.migration.studio_v030 import (
    MigrationDiagnostic,
    MigrationErrorCode,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src" / "graph_skill_runtime"
ERROR_SPEC = REPO_ROOT / "docs" / "skill-spec" / "11-error-code-spec.md"

_LAYER_SECTION_RE = re.compile(r"(?m)^## 9\. .*$")
_DIAGNOSTIC_CODE_RE = re.compile(r"\[F-v3-[a-z0-9-]+\]")
_BOUNDARY_CODE_RE = re.compile(r"GSKILL_[A-Z0-9_]+")
_SPEC_ROW_CODE_RE = re.compile(r"(?m)^\| `(GSKILL_[A-Z0-9_]+)` \|")


def _layer_declaration_text() -> str:
    """Return only §9, the section that declares the layers."""

    text = ERROR_SPEC.read_text(encoding="utf-8")
    match = _LAYER_SECTION_RE.search(text)
    assert match is not None, "11-error-code-spec.md must declare the layer section §9"
    return text[match.start() :]


def _declared_boundary_codes() -> set[str]:
    return set(_SPEC_ROW_CODE_RE.findall(_layer_declaration_text()))


def _string_constants() -> list[tuple[Path, str]]:
    """Every string literal in the runtime source, with its owning file."""

    constants: list[tuple[Path, str]] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                constants.append((path, node.value))
    return constants


def test_migration_codes_are_a_closed_enumerable_layer() -> None:
    assert len(MigrationErrorCode) == 26
    assert all(code.value.startswith("GSKILL_MIGRATION_") for code in MigrationErrorCode)
    assert MigrationDiagnostic.model_fields["code"].annotation is MigrationErrorCode


def test_migration_diagnostic_rejects_an_unregistered_code() -> None:
    with pytest.raises(ValidationError):
        MigrationDiagnostic(code="GSKILL_MIGRATION_NOT_A_REAL_CODE", message="typo")


def test_runtime_boundary_codes_are_a_closed_enumerable_layer() -> None:
    assert len(RuntimeErrorCode) == 8
    assert all(
        code.value.startswith("GSKILL_") and not code.value.startswith("GSKILL_MIGRATION_")
        for code in RuntimeErrorCode
    )


def test_the_three_layers_are_pairwise_disjoint() -> None:
    diagnostics = set(ERROR_REGISTRY)
    boundary = {code.value for code in RuntimeErrorCode}
    migration = {code.value for code in MigrationErrorCode}

    assert diagnostics & boundary == set()
    assert diagnostics & migration == set()
    assert boundary & migration == set()


def test_layer_declaration_lists_exactly_the_mirrored_codes() -> None:
    declared = _declared_boundary_codes()
    boundary = {code.value for code in RuntimeErrorCode}
    migration = {code.value for code in MigrationErrorCode}

    assert declared == boundary | migration


def test_layer_declaration_does_not_restate_the_diagnostics_catalog() -> None:
    """§2-§7 own the ``[F-v3-*]`` rows; §9 must not fork a parallel copy."""

    section = _layer_declaration_text()
    rows = [line for line in section.splitlines() if line.startswith("| `[F-v3-")]

    assert rows == []


def test_reserved_external_prefix_is_declared_and_does_not_shadow_layer_one() -> None:
    """``[F-v3-gateway-*]`` is an external owner's prefix, not a fourth code set."""

    section = _layer_declaration_text()

    assert _EXTERNAL_ERROR_CODE_PREFIXES == ("[F-v3-gateway-",)
    for prefix in _EXTERNAL_ERROR_CODE_PREFIXES:
        assert prefix in section
        assert not any(code.startswith(prefix) for code in ERROR_REGISTRY)


def test_no_error_code_literal_escapes_the_declared_layers() -> None:
    """A code-shaped string literal must resolve to one declared layer.

    A failure here means one of two things: a new error code was introduced
    without registering it in ``ERROR_REGISTRY``, ``RuntimeErrorCode``, or
    ``MigrationErrorCode``; or a non-error string was given an error-code
    shape. Register the code in the layer that owns it, or rename the string.
    """

    known = (
        set(ERROR_REGISTRY)
        | {code.value for code in RuntimeErrorCode}
        | {code.value for code in MigrationErrorCode}
    )

    escaped: set[tuple[str, str]] = set()
    for path, value in _string_constants():
        found = _DIAGNOSTIC_CODE_RE.findall(value) + _BOUNDARY_CODE_RE.findall(value)
        for code in found:
            if code not in known:
                escaped.add((path.relative_to(REPO_ROOT).as_posix(), code))

    assert escaped == set()
