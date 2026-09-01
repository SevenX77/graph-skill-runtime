"""Public compiler for portable gSkill directories."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graph_skill_runtime.core.cache import compute_cache_key, load_from_cache, save_to_cache
from graph_skill_runtime.core.loader import CompiledSkill, SkillLoader
from graph_skill_runtime.core.local_workspace_resolver import default_local_resolver_for_skill
from graph_skill_runtime.core.skill_resolver_protocol import (
    SkillResolverProtocol,
    require_skill_resolver,
)

#: Identity of the compile RULES, as opposed to the sources they read.
#:
#: The cache key already covers the skill files, the Python version and the
#: package version — every INPUT. None of those move when a rule changes what it
#: means: the tree on disk is untouched, and the package version is pinned across
#: pre-release (every rule change so far shipped under `0.1.0a1`, and a rule
#: change need not ship a release at all). So an entry minted before a rule
#: existed stayed reachable, and `cache=True` replayed its "this skill compiles"
#: verdict against rules that reject the skill.
#:
#: Borrowed from pytest's version-stamped cache directory and rustc's
#: `-Cmetadata`/SVH: a compilation cache key must cover the COMPILER's identity,
#: not only the inputs it consumed. Rejected: hashing the loader's source, which
#: churns on comments and refactors — it would keep throwing the cache away
#: while still not saying which change was semantic; and leaning on the package
#: version, which is the thing that does not move here.
#:
#: BUMP THIS in the same change as any compile-rule semantics change. What it
#: buys is a fence, not a full guarantee: it separates entries by rule version,
#: it does not make two compiles of the same version with different arguments
#: distinguishable (`allowed_roles` is still absent from the key — a separate
#: pre-existing defect, tracked on its own).
#:
#: 1 — user ruling 2026-08-31: an AGENT phase resolving no `llm_role` is a
#:     compile error ([F-v3-agent-llm-role-missing]). Entries minted before it
#:     recorded a SUCCESS for exactly that shape.
CACHE_SCHEMA_VERSION = 1


@dataclass
class CompileIssue:
    """One compile diagnostic with explicit location axes.

    ``source_path`` is skill-relative (posix separators), ``line`` is the
    1-based line inside that file, ``field_path`` is the engine's nearest-field
    locator (e.g. ``"<phase>.depends_on"``) — consumers project these axes
    directly instead of parsing a location string.

    ``conflicting_phase`` names the OTHER phase, for the rules whose whole
    subject is a relationship between two of them: the field at ``field_path``
    in the phase at ``source_path`` collides with a declaration in this one.
    Most rules are about a single phase and leave it ``None``; a rule that has
    a second participant must not leave it findable only inside ``message``.
    """

    rule_id: str
    severity: str
    source_path: str | None
    line: int | None
    field_path: str | None
    message: str
    conflicting_phase: str | None = None


@dataclass
class CompileResult:
    """Aggregated compile diagnostics container (rides on the exception seam)."""

    issues: list[CompileIssue] = field(default_factory=list)

    @property
    def fatals(self) -> list[CompileIssue]:
        return [issue for issue in self.issues if issue.severity == "FATAL"]

    @property
    def warnings(self) -> list[CompileIssue]:
        return [issue for issue in self.issues if issue.severity == "WARNING"]

    @property
    def passed(self) -> bool:
        return not self.fatals


def compile_skill(
    root: str | Path,
    *,
    chat_model: Any = None,
    cache: bool = True,
    skill_resolver: SkillResolverProtocol | None = None,
    runtime_input_fields: dict[str, set[str]] | None = None,
    allowed_roles: set[str] | None = None,
) -> CompiledSkill:
    """Compile a portable gSkill root into a ``CompiledSkill``.

    ``chat_model`` is accepted for the stable T1.5 public signature; compilation itself
    is model-free. LangGraph assembly receives the model separately.
    """

    del chat_model
    skill_root = Path(root)
    resolver = require_skill_resolver(
        skill_resolver or default_local_resolver_for_skill(skill_root),
        caller="compile_skill",
    )
    if runtime_input_fields is not None:
        cache = False
    if cache:
        key = compute_cache_key(skill_root, schema_version=CACHE_SCHEMA_VERSION)
        cached = load_from_cache(key, skill_root)
        if cached is not None:
            return cached

    compiled = SkillLoader().compile_skill(
        skill_root,
        skill_resolver=resolver,
        runtime_input_fields=runtime_input_fields,
        allowed_roles=allowed_roles,
    )
    if cache:
        save_to_cache(compute_cache_key(skill_root, schema_version=CACHE_SCHEMA_VERSION), compiled)
    return compiled


__all__ = ["CACHE_SCHEMA_VERSION", "CompileIssue", "CompileResult", "compile_skill"]
