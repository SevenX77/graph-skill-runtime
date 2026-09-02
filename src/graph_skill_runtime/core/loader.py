"""Portable gSkill loader for root Agent Skills metadata and graph bundles."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import logging
import re
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Literal, NoReturn, TypeVar, get_origin

import yaml
from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator
from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML as RuamelYAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError

from graph_skill_runtime.core.actions import ActionDef, ActionRegistry, ToolDef, ToolRegistry
from graph_skill_runtime.core.authored_text import read_authored_text
from graph_skill_runtime.core.exceptions import GraphAgentFatalError, SkillLoadError, make_error_payload
from graph_skill_runtime.core.local_workspace_resolver import default_local_resolver_for_skill
from graph_skill_runtime.core.manifest import (
    GRAPH_ID_PATTERN,
    AgentNodeAST,
    GraphManifest,
    GraphPhaseRef,
    IterateSpec,
    LogicNodeAST,
    PhaseIOSchema,
    RootSkillManifest,
    SubgraphNodeAST,
    effective_llm_role,
)
from graph_skill_runtime.core.mentions import first_broken_mention, scan_mentions
from graph_skill_runtime.core.parser import (
    extract_raw_blocks,
    locate_line_for_pydantic_loc,
    parse_markdown_parts,
    scan_forbidden_topology_tags,
)
from graph_skill_runtime.core.purity import scan_python_purity, scan_tool_imports_context
from graph_skill_runtime.core.skill_resolver_protocol import (
    SkillResolverProtocol,
    require_skill_resolver,
    resolve_skill_root,
)
from graph_skill_runtime.core.subagents import build_subagent_input_model, build_subagent_tool_args_model

logger = logging.getLogger(__name__)

RouteKind = Literal["graph", "logic", "subgraph", "agent"]
PhaseAST = LogicNodeAST | SubgraphNodeAST | AgentNodeAST

_PHASE_FILE_TO_MODE: dict[str, str] = {
    "LOGIC.md": "logic",
    "SUBGRAPH.md": "subgraph",
    "AGENT.md": "agent",
}


@dataclass(frozen=True)
class PhaseDocument:
    """One routed portable phase document plus its typed AST."""

    phase_name: str
    path: Path
    mode: str
    frontmatter: dict[str, Any]
    raw_blocks: dict[str, str]
    ast: PhaseAST


@dataclass(frozen=True)
class CompiledSkill:
    """One compiled graph plus the business skill's flat graph registry."""

    raw: dict[str, Any]
    manifest: GraphManifest
    nodes: list[PhaseDocument] = field(default_factory=list)
    actions: ActionRegistry = field(default_factory=ActionRegistry.empty)
    tools: ToolRegistry = field(default_factory=ToolRegistry.empty)
    subagents_by_phase: dict[str, list[CompiledSubagent]] = field(default_factory=dict)
    phase_tokens: dict[str, PhaseTokenInfo] = field(default_factory=dict)
    skill_manifest: RootSkillManifest | None = None
    skill_root: Path = Path(".")
    graph_root: Path = Path(".")
    graph_registry: dict[str, CompiledSkill] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class CompiledSubagent:
    """Resolved external Agent Skill metadata declared on a parent AGENT phase."""

    parent_phase_id: str
    name: str
    target_skill: str
    description: str
    root: Path
    input_schema: dict[str, Any]
    input_model: type[BaseModel] = field(compare=False)
    expected_schema: dict[str, Any]


@dataclass(frozen=True)
class PhaseTokenInfo:
    """Portable source metadata for one ``graph.yaml`` phase entry."""

    phase_id: str
    raw_text: str
    line_start: int
    line_end: int
    attrs: dict[str, str]


@dataclass(frozen=True)
class PhaseTopologyRef:
    """Normalized topology declaration from one ``graph.yaml`` phase entry.

    Diagnostics locate a phase by ``token.line_start``, the file-absolute
    ``graph.yaml`` line of its ``- id:`` entry. A portable v1 graph declares its
    topology only in ``graph.yaml``, so there is one line coordinate per phase;
    the separate body-relative coordinate that schema-1.x needed for ``<phase>``
    tags inside a markdown ``GRAPH.md`` body no longer has a second carrier to
    disagree with.
    """

    name: str
    depends_on: tuple[str, ...]
    output: bool
    token: PhaseTokenInfo


class SkillLoader:
    """Compile a portable business gSkill and its flat graph registry."""

    def __init__(
        self,
        *args: Any,
        validate_context_writes: bool = True,
        **kwargs: Any,
    ) -> None:
        del args, kwargs
        self.validate_context_writes = validate_context_writes

    def compile_skill(
        self,
        skill_root: str | Path,
        *,
        skill_resolver: SkillResolverProtocol | None = None,
        runtime_input_fields: dict[str, set[str]] | None = None,
        _loading_stack: tuple[str, ...] = (),
        _compilation_cache: dict[str, CompiledSkill] | None = None,
        allowed_roles: set[str] | None = None,
    ) -> CompiledSkill:
        """Compile one skill root, with every diagnostic located against THAT root.

        The boundary owns the rendering of ``source_path`` because the root is
        what makes a relative path mean anything, and this call is the only
        place that knows it. Diagnostics are carried as absolute paths inside,
        and rebased once on the way out — the deeper helpers must not each guess
        (guessing is what produced the defect this seam replaces).
        """
        root = Path(skill_root)
        try:
            return self._compile_skill_from_root(
                root,
                skill_resolver=skill_resolver,
                runtime_input_fields=runtime_input_fields,
                _loading_stack=_loading_stack,
                _compilation_cache=_compilation_cache,
                allowed_roles=allowed_roles,
            )
        except SkillLoadError as exc:
            _relocate_diagnostics_to_root(exc, root)
            raise

    def _compile_skill_from_root(
        self,
        root: Path,
        *,
        skill_resolver: SkillResolverProtocol | None,
        runtime_input_fields: dict[str, set[str]] | None,
        _loading_stack: tuple[str, ...],
        _compilation_cache: dict[str, CompiledSkill] | None,
        allowed_roles: set[str] | None,
    ) -> CompiledSkill:
        _guard_portable_skill_root(root)
        skill_manifest, skill_diags = _load_root_skill_manifest(root)

        graph_roots = [root]
        graphs_dir = root / "graphs"
        if graphs_dir.exists():
            graph_roots.extend(sorted(path for path in graphs_dir.iterdir() if path.is_dir()))
        registry_slots = {path.name for path in graph_roots[1:]}

        graph_registry: dict[str, CompiledSkill] = {}
        compiled_graphs: list[CompiledSkill] = []
        errors: list[SkillLoadError] = []
        # Root metadata first, so a defective SKILL.md keeps its identity as the
        # primary error while the graph batch below still contributes its own
        # defects to the same aggregated CompileResult.
        if skill_diags:
            errors.append(_diags_error(skill_diags))
        for graph_root in graph_roots:
            try:
                compiled_graphs.append(
                    self._compile_graph_from_root(
                        graph_root,
                        business_root=root,
                        skill_manifest=skill_manifest,
                        graph_registry=graph_registry,
                        skill_resolver=skill_resolver,
                        runtime_input_fields=runtime_input_fields,
                        _loading_stack=_loading_stack,
                        _compilation_cache=_compilation_cache,
                        allowed_roles=allowed_roles,
                    )
                )
            except SkillLoadError as exc:
                errors.append(exc)
        registry_diags = (
            _validate_graph_registry(
                root,
                compiled_graphs,
                registry_slots=registry_slots,
            )
            if compiled_graphs
            else []
        )
        if registry_diags:
            errors.append(_diags_error(registry_diags))
        if errors:
            _raise_collected_errors(errors)

        graph_registry.update({graph.manifest.graph_id: graph for graph in compiled_graphs})
        return compiled_graphs[0]

    def _compile_graph_from_root(
        self,
        root: Path,
        *,
        business_root: Path,
        skill_manifest: RootSkillManifest,
        graph_registry: dict[str, CompiledSkill],
        skill_resolver: SkillResolverProtocol | None,
        runtime_input_fields: dict[str, set[str]] | None,
        _loading_stack: tuple[str, ...],
        _compilation_cache: dict[str, CompiledSkill] | None,
        allowed_roles: set[str] | None,
    ) -> CompiledSkill:
        resolver = skill_resolver or default_local_resolver_for_skill(business_root)
        root_key = str(root.resolve())
        if root_key in _loading_stack:
            detail = f"recursive skill compilation cycle detected at {root_key}"
            raise SkillLoadError(
                detail,
                payload=make_error_payload(
                    "[F-v3-compile-recursion-cycle]",
                    detail,
                    source_path=_payload_source_path(root / "graph.yaml"),
                ),
            )
        if len(_loading_stack) >= 20:
            detail = f"recursive skill compilation depth exceeded at {root_key}"
            raise SkillLoadError(
                detail,
                payload=make_error_payload(
                    "[F-v3-compile-depth-exceeded]",
                    detail,
                    source_path=_payload_source_path(root / "graph.yaml"),
                ),
            )
        if _compilation_cache is None:
            _compilation_cache = {}
        if root_key in _compilation_cache:
            return _compilation_cache[root_key]
        loading_stack = (*_loading_stack, root_key)
        _guard_graph_root(root)

        graph_path = root / "graph.yaml"
        graph_frontmatter = _read_graph_yaml(graph_path)
        _reject_deprecated_physical_io(root)
        manifest, fm_diags, manifest_poisoned = _build_graph_manifest(graph_path, graph_frontmatter)
        phase_refs = [] if manifest_poisoned else _phase_refs_from_manifest(graph_path, manifest)
        phase_tokens: dict[str, PhaseTokenInfo] = {ref.name: ref.token for ref in phase_refs}

        batch_errors: list[SkillLoadError] = []
        if fm_diags:
            batch_errors.append(_diags_error(fm_diags))

        # R3.1 llm_role check
        if allowed_roles is not None:
            if manifest.llm_role is not None and manifest.llm_role not in allowed_roles:
                graph_role_line = _frontmatter_key_line(graph_path, "llm_role")
                batch_errors.append(
                    _diags_error(
                        [
                            _Diag(
                                graph_path,
                                graph_role_line,
                                "[F-v3-graph-llm-role-unknown]",
                                f"Graph default LLM role {manifest.llm_role!r} "
                                "is not declared in the host allowed roles set",
                                field_path="llm_role",
                            )
                        ]
                    )
                )

        graph_diags: list[_Diag] = []
        graph_topology = {}
        if not manifest_poisoned:
            graph_topology = _validate_graph_topology(
                graph_path,
                [phase.id for phase in manifest.phases],
                phase_refs,
                root,
                graph_diags,
            )
            if graph_diags:
                batch_errors.append(_diags_error(graph_diags))

        io_inputs: dict[str, Any] = {}
        io_outputs: dict[str, Any] = {}
        if not manifest_poisoned:
            try:
                io_inputs = _validate_inline_io_schema(graph_path, manifest.io.inputs, "input")
                io_outputs = _validate_inline_io_schema(graph_path, manifest.io.outputs, "output")
            except SkillLoadError as exc:
                batch_errors.append(exc)

        discovered: list[tuple[str, Path, str]] = []
        try:
            discovered = _discover_phase_files(root)
        except SkillLoadError as exc:
            batch_errors.append(exc)

        phase_docs: list[PhaseDocument] = []
        poisoned_phases: set[str] = set()
        for phase_name, phase_file, mode in discovered:
            try:
                frontmatter, body, _ = parse_markdown_parts(phase_file)
                _reject_phase_forbidden_metadata(phase_file, frontmatter)
                scan_forbidden_topology_tags(phase_file, body)
                doc = build_phase_document(phase_name, phase_file, mode, frontmatter, body)
                phase_docs.append(doc)

                # Two DIFFERENT questions about an Agent phase's role, so two
                # checks with two different preconditions.
                #
                # "Is there a role name at all?" is answered by the portable
                # source alone, so it runs UNCONDITIONALLY on every compile path
                # — SDK, CLI, MCP, inspect, predict. User ruling 2026-08-31:
                # the default role is empty, a role must be set explicitly, and
                # a skill that sets none fails at COMPILE time. The runtime
                # invents no fallback name, so a phase nobody gave a role to
                # must fail HERE and not at run time inside a route lookup.
                # Gating this on injected `allowed_roles` would have made the
                # rule unreachable: no production entry point injects that
                # parameter (adapters/engine.py compile/inspect), so a role-less
                # skill would still have compiled green through the whole public
                # surface.
                #
                # "Can THIS host route that name?" is a different question, and
                # only a host can answer it — it stays gated on `allowed_roles`.
                if isinstance(doc.ast, AgentNodeAST):
                    if effective_llm_role(doc.ast, manifest.llm_role) is None:
                        batch_errors.append(
                            _diags_error(
                                [
                                    _Diag(
                                        doc.path,
                                        _frontmatter_key_line(doc.path, "llm_role"),
                                        "[F-v3-agent-llm-role-missing]",
                                        f"Agent phase {doc.phase_name!r} resolves no LLM role: set "
                                        "`llm_role` in this phase's frontmatter or a graph default "
                                        "`llm_role` in this graph's graph.yaml (a registry graph "
                                        "declares its own default; the calling graph's does not "
                                        "reach inside it)",
                                        field_path="llm_role",
                                    )
                                ]
                            )
                        )
                    # R3.1 check node-level role against the host's role truth
                    if (
                        allowed_roles is not None
                        and doc.ast.llm_role is not None
                        and doc.ast.llm_role not in allowed_roles
                    ):
                        agent_role_line = _frontmatter_key_line(doc.path, "llm_role")
                        batch_errors.append(
                            _diags_error(
                                [
                                    _Diag(
                                        doc.path,
                                        agent_role_line,
                                        "[F-v3-agent-llm-role-unknown]",
                                        f"Agent node LLM role {doc.ast.llm_role!r} in phase {doc.phase_name!r} "
                                        "is not declared in the host allowed roles set",
                                        field_path="llm_role",
                                    )
                                ]
                            )
                        )

                # R3.2 check validator.py statically
                if isinstance(doc.ast, LogicNodeAST) and doc.ast.validator:
                    validator_file = doc.path.parent / "validator.py"
                    if not validator_file.exists():
                        batch_errors.append(
                            _diags_error(
                                [
                                    _Diag(
                                        doc.path,
                                        _frontmatter_key_line(doc.path, "validator"),
                                        "[F-v3-logic-validator-missing]",
                                        f"validator is set to true in logic phase {doc.phase_name!r} "
                                        "but validator.py is missing",
                                        field_path="validator",
                                    )
                                ]
                            )
                        )
                    else:
                        try:
                            content = read_authored_text(validator_file)
                            tree = ast.parse(content, filename=str(validator_file))
                            has_validate = False
                            for node in tree.body:
                                if isinstance(node, ast.FunctionDef) and node.name == "validate":
                                    has_validate = True
                                    break
                            if not has_validate:
                                batch_errors.append(
                                    _diags_error(
                                        [
                                            _Diag(
                                                doc.path,
                                                _frontmatter_key_line(doc.path, "validator"),
                                                "[F-v3-logic-validator-entrypoint-missing]",
                                                f"validator.py in logic phase {doc.phase_name!r} "
                                                "does not define a top-level 'validate' function",
                                                field_path="validator",
                                            )
                                        ]
                                    )
                                )
                        except SyntaxError as exc:
                            batch_errors.append(
                                _diags_error(
                                    [
                                        _Diag(
                                            doc.path,
                                            _frontmatter_key_line(doc.path, "validator"),
                                            "[F-v3-logic-validator-entrypoint-missing]",
                                            f"validator.py in logic phase {doc.phase_name!r} has syntax error: {exc}",
                                            field_path="validator",
                                        )
                                    ]
                                )
                            )
                        except Exception as exc:
                            batch_errors.append(
                                _diags_error(
                                    [
                                        _Diag(
                                            doc.path,
                                            _frontmatter_key_line(doc.path, "validator"),
                                            "[F-v3-logic-validator-missing]",
                                            f"validator.py in logic phase {doc.phase_name!r} could not be read: {exc}",
                                            field_path="validator",
                                        )
                                    ]
                                )
                            )
            except SkillLoadError as exc:
                batch_errors.append(exc)
                poisoned_phases.add(phase_name)

        if batch_errors:
            _raise_collected_errors(batch_errors)

        input_schema_keys = _extract_output_schema_keys(io_inputs)
        output_schema_keys = _extract_output_schema_keys(io_outputs)

        post_diags: list[_Diag] = []

        _validate_agent_resource_paths(business_root, phase_docs, post_diags)
        _validate_iterate_compile_contracts(phase_docs, post_diags)
        _validate_static_dataflow(
            graph_path,
            graph_topology,
            phase_docs,
            io_inputs,
            io_outputs,
            manifest.iterate,
            runtime_input_fields=runtime_input_fields,
            diags=post_diags,
            poisoned_phases=poisoned_phases,
        )
        _validate_sequential_overwrites(graph_path, phase_refs, phase_docs, post_diags)
        _validate_parallel_writers(graph_path, phase_refs, phase_docs, post_diags)

        discovery_failed = False
        subagent_failed = False
        injection_failed = False
        actions = ActionRegistry.empty()
        tools = ToolRegistry.empty()
        subagents_by_phase: dict[str, list[CompiledSubagent]] = {}

        try:
            actions, tools = _discover_actions_and_tools(business_root, phase_docs)
        except SkillLoadError as exc:
            _append_issues_as_diags(post_diags, exc)
            discovery_failed = True

        if not discovery_failed:
            try:
                subagents_by_phase = _compile_subagent_metadata(
                    phase_docs,
                    skill_resolver=resolver,
                    _loading_stack=loading_stack,
                    _compilation_cache=_compilation_cache,
                )
            except SkillLoadError as exc:
                _append_issues_as_diags(post_diags, exc)
                subagent_failed = True

        if not discovery_failed and not subagent_failed:
            try:
                tools = _inject_subagent_tools(tools, subagents_by_phase)
            except SkillLoadError as exc:
                _append_issues_as_diags(post_diags, exc)
                injection_failed = True

        if not discovery_failed and not subagent_failed and not injection_failed:
            _validate_agent_declared_tools(phase_docs, tools, post_diags)
        if not discovery_failed:
            _validate_logic_action_return_keys(
                phase_docs,
                actions,
                input_schema_keys,
                output_schema_keys,
                validate_context_writes=self.validate_context_writes,
                diags=post_diags,
            )

        if post_diags:
            _raise_diags(post_diags)

        raw = {
            "graph": {"frontmatter": graph_frontmatter},
            "graph_topology": graph_topology,
            "io": {
                "inputs": io_inputs,
                "outputs": io_outputs,
                "output_schema_keys": sorted(output_schema_keys) if output_schema_keys is not None else None,
            },
            "phases": [
                {
                    "phase_name": doc.phase_name,
                    "path": str(doc.path),
                    "mode": doc.mode,
                    "frontmatter": doc.frontmatter,
                    "raw_blocks": doc.raw_blocks,
                }
                for doc in phase_docs
            ],
        }
        safe_root = root_key.replace("\r", "").replace("\n", "")
        logger.info("Compiled portable graph root=%s phases=%d", safe_root, len(phase_docs))
        compiled = CompiledSkill(
            raw=raw,
            manifest=manifest,
            nodes=phase_docs,
            actions=actions,
            tools=tools,
            subagents_by_phase=subagents_by_phase,
            phase_tokens=phase_tokens,
            skill_manifest=skill_manifest,
            skill_root=business_root.resolve(),
            graph_root=root.resolve(),
            graph_registry=graph_registry,
        )
        _compilation_cache[root_key] = compiled
        return compiled


_CODE_PREFIX_RE = re.compile(r"^\[(F-v3-[a-z0-9-]+)\]\s*(.*)$", re.DOTALL)


def _split_code_message(code: str, message: str) -> tuple[str, str]:
    match = _CODE_PREFIX_RE.match(message)
    if match is None:
        return code, message
    return f"[{match.group(1)}]", match.group(2)


def _fatal(
    path: Path,
    line: int,
    message: str,
    *,
    code: str = "[F-v3-graph-root-missing]",
    field_path: str | None = None,
) -> NoReturn:
    code, clean = _split_code_message(code, message)
    detail = f"{path}:{line} {clean}"
    raise SkillLoadError(
        detail,
        payload=make_error_payload(
            code,
            detail,
            field_path=field_path,
            source_path=_payload_source_path(path),
        ),
    )


def _io_fatal(
    path: Path,
    line: int,
    message: str,
    *,
    field_path: str | None = None,
    code: str = "[F-v3-graph-io-schema-invalid]",
) -> NoReturn:
    code, clean = _split_code_message(code, message)
    detail = f"{path}:{line} {clean}"
    raise SkillLoadError(
        detail,
        payload=make_error_payload(
            code,
            detail,
            field_path=field_path,
            source_path=_payload_source_path(path),
        ),
    )


# --------------------------------------------------------------------------- #
# Collect-all diagnostics (compile/lint is static analysis, not a run): gather  #
# every independent defect in one pass instead of aborting at the first         #
# ``_fatal``. Structural failures that make further parsing impossible still    #
# abort (an unreadable or absent graph.yaml); the root SKILL.md metadata, the   #
# topology stage, IO schema, and per-node content checks all accumulate — a     #
# defect in one of them must never hide the others. The full set rides on       #
# ``exc.compile_result.issues`` — the ONE seam every Studio consumer (compile   #
# drawer AND realtime lint) projects; the primary ``payload`` stays the first   #
# defect only as the exception's identity.                                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Diag:
    """One independent compile defect, line-located in its source file."""

    path: Path
    line: int
    code: str
    message: str
    field_path: str | None = None
    conflicting_phase: str | None = None


def _make_diag(path: Path, line: int, raw_message: str, *, field_path: str | None = None) -> _Diag:
    code, clean = _split_code_message("[F-v3-graph-root-missing]", raw_message)
    return _Diag(path, line, code, clean, field_path)


def _compile_result(diags: list[_Diag]) -> Any:
    """Build the ``CompileResult`` container every Studio consumer projects.

    ``source_path`` uses the skill-relative posix path (never the absolute
    path) so consumers are not tripped by a Windows drive-letter colon.
    """
    from graph_skill_runtime.core.compiler import CompileIssue, CompileResult

    return CompileResult(
        issues=[
            CompileIssue(
                rule_id=d.code,
                severity="FATAL",
                source_path=_payload_source_path(d.path),
                line=d.line,
                field_path=d.field_path,
                message=d.message,
                conflicting_phase=d.conflicting_phase,
            )
            for d in diags
        ]
    )


def _diags_error(diags: list[_Diag]) -> SkillLoadError:
    """Build one error carrying every collected defect; primary = the first."""
    first = diags[0]
    detail = f"{first.path}:{first.line} {first.message}"
    error = SkillLoadError(
        detail,
        payload=make_error_payload(
            first.code,
            detail,
            field_path=first.field_path,
            source_path=_payload_source_path(first.path),
        ),
    )
    error.compile_result = _compile_result(diags)  # type: ignore[attr-defined]
    return error


def _raise_diags(diags: list[_Diag]) -> NoReturn:
    """Raise one error carrying every collected defect; primary = the first."""
    raise _diags_error(diags)


def _issues_of(exc: SkillLoadError) -> list[Any]:
    """Extract this error's CompileIssue list (its own, or one from its payload)."""
    from graph_skill_runtime.core.compiler import CompileIssue, CompileResult

    existing = getattr(exc, "compile_result", None)
    if isinstance(existing, CompileResult) and existing.issues:
        return list(existing.issues)
    payload = exc.payload
    code = payload.code if payload is not None else "[F-v3-graph-root-missing]"
    source = payload.source_path if payload is not None else None
    field_path = payload.field_path if payload is not None else None
    match = re.search(r":(\d+)(?:\s|$)", str(exc))
    line = int(match.group(1)) if match else None
    return [
        CompileIssue(
            rule_id=code,
            severity="FATAL",
            source_path=source,
            line=line,
            field_path=field_path,
            message=str(exc),
        )
    ]


def _append_issues_as_diags(diags: list[_Diag], exc: SkillLoadError) -> None:
    for issue in _issues_of(exc):
        source_path = getattr(issue, "source_path", None)
        line = getattr(issue, "line", None)
        rule_id = getattr(issue, "rule_id", getattr(issue, "code", None))
        message = getattr(issue, "message", str(exc))
        field_path = getattr(issue, "field_path", None)
        diags.append(
            _Diag(
                Path(str(source_path)) if source_path else Path("graph.yaml"),
                line if isinstance(line, int) else 1,
                str(rule_id or "[F-v3-graph-root-missing]"),
                str(message),
                field_path=str(field_path) if field_path is not None else None,
            )
        )


def _raise_collected_errors(errors: list[SkillLoadError]) -> NoReturn:
    """Re-raise the first error verbatim, with every error's defects merged.

    The first error keeps its identity/payload/attributes (so existing
    assertions on the primary are untouched); ``compile_result`` is widened to
    carry the whole batch for every diagnostics consumer.
    """
    from graph_skill_runtime.core.compiler import CompileResult

    primary = errors[0]
    issues = [issue for exc in errors for issue in _issues_of(exc)]
    primary.compile_result = CompileResult(issues=issues)  # type: ignore[attr-defined]
    raise primary


def _graph_fatal(path: Path, line: int, message: str, *, field_path: str | None = None) -> NoReturn:
    code, clean = _split_code_message("[F-v3-graph-schema-unknown-field]", message)
    detail = f"{path}:{line} {clean}"
    raise SkillLoadError(
        detail,
        payload=make_error_payload(
            code,
            detail,
            field_path=field_path,
            source_path=_payload_source_path(path),
        ),
    )


def _actions_fatal(
    path: Path,
    line: int,
    message: str,
    *,
    code: str = "[F-v3-logic-action-not-found]",
    field_path: str | None = None,
) -> NoReturn:
    code, clean = _split_code_message(code, message)
    detail = f"{path}:{line} {clean}"
    raise SkillLoadError(
        detail,
        payload=make_error_payload(
            code,
            detail,
            field_path=field_path,
            source_path=_payload_source_path(path),
        ),
    )


def _actions_keys_fatal(path: Path, line: int, message: str) -> None:
    detail = f"{path}:{line} {message}"
    raise GraphAgentFatalError(
        detail,
        payload=make_error_payload(
            "[F-v3-logic-output-field-undeclared]",
            detail,
            source_path=_payload_source_path(path),
        ),
    )


def _purity_fatal(path: Path, line: int, message: str) -> None:
    detail = f"{path}:{line} {message}"
    raise SkillLoadError(
        detail,
        payload=make_error_payload(
            "[F-v3-logic-action-purity-violation]",
            detail,
            source_path=_payload_source_path(path),
        ),
    )


def _payload_source_path(path: Path) -> str:
    """Carry the diagnostic's file as an unambiguous absolute posix path.

    A path only becomes skill-relative against a stated root, and the helpers
    that raise diagnostics do not know which root the caller is compiling — a
    subgraph phase file is reached during BOTH the child's own compile and its
    parent's. So they keep the whole path, and
    ``SkillLoader.compile_skill`` renders it relative to the root it owns.
    """
    return path.as_posix()


def _relocate_diagnostics_to_root(exc: SkillLoadError, root: Path) -> None:
    """Render this error's file locations relative to ``root``, in place.

    Studio projects ``source_path`` straight onto files and nodes, so the axis
    has to name the file the defect is actually in. A path outside ``root``
    (a subgraph linked from elsewhere) has no relative form and stays absolute
    rather than being bent into a wrong one.
    """
    resolved_root = root.resolve()

    def relocate(source_path: str | None) -> str | None:
        if not source_path:
            return source_path
        candidate = Path(source_path)
        if not candidate.is_absolute():
            return candidate.as_posix()
        try:
            return candidate.resolve().relative_to(resolved_root).as_posix()
        except ValueError:
            return candidate.as_posix()

    compile_result = getattr(exc, "compile_result", None)
    for issue in getattr(compile_result, "issues", []) or []:
        issue.source_path = relocate(issue.source_path)

    payload = exc.payload
    if payload is not None:
        payload.source_path = relocate(payload.source_path)
        exc.source_path = payload.source_path
        exc.skill_path = Path(payload.source_path) if payload.source_path else None
        exc.error_payload = payload.model_dump(mode="json")


def _first_validation_loc(exc: ValidationError) -> tuple[Any, ...]:
    errors = exc.errors()
    if not errors:
        return ()
    loc = errors[0].get("loc", ())
    return tuple(loc) if isinstance(loc, (list, tuple)) else ()


def _field_path_from_loc(loc: tuple[Any, ...]) -> str | None:
    if not loc:
        return None
    return ".".join(str(segment) for segment in loc)


def _frontmatter_loc_line(path: Path, frontmatter: dict[str, Any], loc: tuple[Any, ...]) -> int:
    line = locate_line_for_pydantic_loc(frontmatter, loc)
    if line is not None:
        return line
    first = loc[0] if loc else None
    if isinstance(first, str):
        return _frontmatter_key_line(path, first)
    return 1


def _guard_portable_skill_root(skill_root: Path) -> None:
    if skill_root.exists() and not skill_root.is_dir():
        _fatal(
            skill_root,
            1,
            "compile_skill expects a portable gSkill root directory",
            code="[F-v3-graph-root-missing]",
        )
    diags: list[_Diag] = []
    root_skill = skill_root / "SKILL.md"
    if not root_skill.is_file():
        diags.append(
            _Diag(root_skill, 1, "[F-v3-skill-entry-missing]", "missing required root SKILL.md")
        )
    root_graph = skill_root / "graph.yaml"
    if not root_graph.is_file():
        diags.append(
            _Diag(root_graph, 1, "[F-v3-graph-root-missing]", "missing required root graph.yaml")
        )
    legacy_graph = skill_root / "GRAPH.md"
    if legacy_graph.exists():
        diags.append(
            _Diag(
                legacy_graph,
                1,
                "[F-v3-graph-root-missing]",
                "legacy GRAPH.md is not accepted; run gskill migrate studio-skill",
            )
        )
    nested_entries = (
        sorted(path for path in skill_root.rglob("SKILL.md") if path != root_skill)
        if skill_root.is_dir()
        else []
    )
    if nested_entries:
        diags.extend(
            _Diag(
                entry,
                1,
                "[F-v3-skill-entry-nested]",
                "only the business skill root may contain SKILL.md; internal agent phases use AGENT.md",
            )
            for entry in nested_entries
        )
    graphs_dir = skill_root / "graphs"
    if graphs_dir.exists() and not graphs_dir.is_dir():
        diags.append(
            _Diag(
                graphs_dir,
                1,
                "[F-v3-graph-registry-invalid]",
                "graphs must be a directory",
            )
        )
    elif graphs_dir.is_dir():
        for entry in sorted(graphs_dir.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                diags.append(
                    _Diag(
                        entry,
                        1,
                        "[F-v3-graph-registry-invalid]",
                        "every direct graphs/ entry must be a real registry graph directory",
                    )
                )
                continue
            if re.fullmatch(GRAPH_ID_PATTERN, entry.name) is None:
                diags.append(
                    _Diag(
                        entry,
                        1,
                        "[F-v3-graph-registry-invalid]",
                        "registry graph directory names must be valid graph ids",
                    )
                )
            nested_registry = entry / "graphs"
            if nested_registry.exists():
                diags.append(
                    _Diag(
                        nested_registry,
                        1,
                        "[F-v3-graph-registry-invalid]",
                        "registry graph directories cannot contain another graphs/ registry",
                    )
                )
        for nested_graph in sorted(graphs_dir.rglob("graph.yaml")):
            if nested_graph.parent.parent != graphs_dir:
                diags.append(
                    _Diag(
                        nested_graph,
                        1,
                        "[F-v3-graph-registry-invalid]",
                        "registry graphs must be flat at graphs/<graph_id>/graph.yaml",
                    )
                )
    if diags:
        _raise_diags(diags)


def _load_root_skill_manifest(skill_root: Path) -> tuple[RootSkillManifest, list[_Diag]]:
    """Parse the root Agent Skills metadata, collecting its defects.

    Root ``SKILL.md`` metadata and the bundle's graph topology are independent
    facts, so one compile must report both: an unusable ``name`` must not hide a
    broken DAG, or fixing the name would only "reveal" the next defect on the
    next compile — the collect-all rule this module's header states. This
    mirrors ``_guard_portable_skill_root``, which already accumulates instead of
    aborting, so the root stage runs one discipline rather than two.

    When validation fails, the returned manifest is a placeholder that exists
    only to let the graph batch reach its own diagnostics; the caller raises at
    the collect-all barrier, so no consumer of a successful compile can see it.
    """
    skill_path = skill_root / "SKILL.md"
    frontmatter: dict[str, Any] = {}
    try:
        frontmatter, _body, _line_meta = parse_markdown_parts(skill_path)
        manifest = RootSkillManifest.model_validate(frontmatter)
    except ValidationError as exc:
        loc = _first_validation_loc(exc)
        diag = _Diag(
            skill_path,
            _frontmatter_loc_line(skill_path, frontmatter, loc),
            "[F-v3-skill-metadata-invalid]",
            f"invalid Agent Skills metadata: {exc}",
            field_path=_field_path_from_loc(loc),
        )
        placeholder = RootSkillManifest.model_construct(
            name=skill_root.name,
            description="",
            license=None,
            compatibility=None,
            metadata={},
            allowed_tools=None,
        )
        return placeholder, [diag]
    if manifest.name != skill_root.name:
        return manifest, [
            _Diag(
                skill_path,
                _frontmatter_key_line(skill_path, "name"),
                "[F-v3-skill-name-directory-mismatch]",
                f"Agent Skills name {manifest.name!r} must match directory {skill_root.name!r}",
                field_path="name",
            )
        ]
    return manifest, []


def _guard_graph_root(graph_root: Path) -> None:
    diags: list[_Diag] = []
    graph = graph_root / "graph.yaml"
    if not graph.is_file():
        diags.append(_Diag(graph, 1, "[F-v3-graph-root-missing]", "missing required graph.yaml"))

    phases = graph_root / "phases"
    if not phases.is_dir() or not any(p.is_dir() for p in phases.iterdir()):
        diags.append(
            _Diag(
                phases,
                1,
                "[F-v3-graph-phases-dir-missing]",
                "missing phases directory or phase entries",
            )
        )
    if (graph_root / "actions").exists():
        diags.append(
            _Diag(
                graph_root / "actions",
                1,
                "[F-v3-logic-action-dir-missing]",
                "graph-level actions/ is not allowed",
            )
        )
    if diags:
        _raise_diags(diags)


def _read_graph_yaml(path: Path) -> dict[str, Any]:
    try:
        yaml_reader = RuamelYAML(typ="safe")
        yaml_reader.allow_duplicate_keys = False
        loaded = yaml_reader.load(read_authored_text(path))
    except RuamelYAMLError as exc:
        _graph_fatal(
            path,
            getattr(getattr(exc, "problem_mark", None), "line", 0) + 1,
            f"[F-v3-graph-schema-unknown-field] invalid graph.yaml: {exc}",
        )
    if not isinstance(loaded, dict):
        _graph_fatal(
            path,
            1,
            "[F-v3-graph-schema-unknown-field] graph.yaml must contain one mapping",
        )
    return loaded


def _discover_phase_files(skill_root: Path) -> list[tuple[str, Path, str]]:
    phases_root = skill_root / "phases"
    discovered: list[tuple[str, Path, str]] = []
    diags: list[_Diag] = []
    for phase_dir in sorted(p for p in phases_root.iterdir() if p.is_dir()):
        nested_graph = phase_dir / "graph.yaml"
        if nested_graph.exists():
            diags.append(
                _Diag(
                    nested_graph,
                    1,
                    "[F-v3-graph-root-missing]",
                    "graph.yaml is only allowed at a root or graphs/<graph_id> directory",
                )
            )
        legacy_agent = phase_dir / "SKILL.md"
        if legacy_agent.exists():
            diags.append(
                _Diag(
                    legacy_agent,
                    1,
                    "[F-v3-graph-phase-node-missing]",
                    "phase SKILL.md is not accepted; internal agent phases use AGENT.md",
                )
            )

        phase_files = [phase_dir / name for name in _PHASE_FILE_TO_MODE if (phase_dir / name).exists()]
        if len(phase_files) > 1:
            names = ", ".join(path.name for path in phase_files)
            diags.append(
                _Diag(
                    phase_files[1],
                    1,
                    "[F-v3-graph-phase-mode-ambiguous]",
                    f"phase directory contains multiple node files: {names}",
                )
            )
            continue
        if not phase_files:
            diags.append(
                _Diag(
                    phase_dir,
                    1,
                    "[F-v3-graph-phase-node-missing]",
                    "phase directory must contain LOGIC.md, SUBGRAPH.md, or AGENT.md",
                )
            )
            continue

        phase_file = phase_files[0]
        discovered.append((phase_dir.name, phase_file, _PHASE_FILE_TO_MODE[phase_file.name]))

    if diags:
        _raise_diags(diags)
    return discovered


def _discover_actions_and_tools(
    skill_root: Path,
    phase_docs: list[PhaseDocument],
) -> tuple[ActionRegistry, ToolRegistry]:
    actions_by_phase: dict[str, dict[str, ActionDef]] = {}
    tools_by_phase: dict[str, list[ToolDef]] = {}
    root_tools = _load_tool_dir(skill_root / "tools", phase_id=None) if (skill_root / "tools").exists() else []

    for doc in phase_docs:
        phase_id, mode = doc.phase_name, doc.mode
        phase_dir = doc.path.parent
        actions_dir = phase_dir / "actions"
        tools_dir = phase_dir / "tools"

        if isinstance(doc.ast, LogicNodeAST):
            if tools_dir.exists():
                _actions_fatal(
                    tools_dir,
                    1,
                    "tools/ is only allowed for AGENT phases",
                    code="[F-v3-agent-tool-unknown]",
                )
            if actions_dir.exists():
                actions_by_phase[phase_id] = _load_action_dir(
                    actions_dir, phase_id, doc.ast.actions
                )
        elif mode == "agent":
            if actions_dir.exists():
                _actions_fatal(
                    actions_dir,
                    1,
                    "actions/ is only allowed for LOGIC phases",
                    code="[F-v3-logic-action-dir-missing]",
                )
            if tools_dir.exists():
                tools_by_phase[phase_id] = _load_tool_dir(tools_dir, phase_id=phase_id)
        else:
            if actions_dir.exists():
                _actions_fatal(
                    actions_dir,
                    1,
                    "actions/ is not allowed for SUBGRAPH phases",
                    code="[F-v3-logic-action-dir-missing]",
                )
            if tools_dir.exists():
                _actions_fatal(
                    tools_dir,
                    1,
                    "tools/ is not allowed for SUBGRAPH phases",
                    code="[F-v3-agent-tool-unknown]",
                )

    return ActionRegistry(actions_by_phase), ToolRegistry(root_tools=root_tools, by_phase=tools_by_phase)


def _reject_deprecated_physical_io(skill_root: Path) -> None:
    for relative in ("io/inputs.json", "io/outputs.json"):
        path = skill_root / relative
        if path.exists():
            _io_fatal(
                path,
                1,
                f"[F-v3-graph-io-physical-file-deprecated] physical root IO file {relative!r} is not supported",
            )


def _validate_graph_registry(
    skill_root: Path,
    graphs: list[CompiledSkill],
    *,
    registry_slots: set[str],
) -> list[_Diag]:
    """Validate the business skill's flat graph registry and explicit call graph."""

    diags: list[_Diag] = []
    by_id: dict[str, CompiledSkill] = {}
    for graph in graphs:
        graph_id = graph.manifest.graph_id
        existing = by_id.get(graph_id)
        if existing is not None:
            diags.append(
                _Diag(
                    graph.graph_root / "graph.yaml",
                    _frontmatter_key_line(graph.graph_root / "graph.yaml", "graph_id"),
                    "[F-v3-graph-id-duplicate]",
                    f"graph_id {graph_id!r} is also declared by {existing.graph_root}",
                    field_path="graph_id",
                )
            )
        else:
            by_id[graph_id] = graph

        if graph.graph_root != skill_root.resolve() and graph.graph_root.name != graph_id:
            diags.append(
                _Diag(
                    graph.graph_root / "graph.yaml",
                    _frontmatter_key_line(graph.graph_root / "graph.yaml", "graph_id"),
                    "[F-v3-graph-id-directory-mismatch]",
                    f"registry directory {graph.graph_root.name!r} must equal graph_id {graph_id!r}",
                    field_path="graph_id",
                )
            )
        if graph.graph_root != skill_root.resolve() and graph.manifest.artifacts:
            diags.append(
                _Diag(
                    graph.graph_root / "graph.yaml",
                    _frontmatter_key_line(graph.graph_root / "graph.yaml", "artifacts"),
                    "[F-v3-artifact-declaration-invalid]",
                    "artifacts may be declared only by the root graph",
                    field_path="artifacts",
                )
            )

    root_graph = next((graph for graph in graphs if graph.graph_root == skill_root.resolve()), None)
    if root_graph is not None:
        output_fields = set(root_graph.manifest.io.outputs.get("properties", {}))
        for index, artifact in enumerate(root_graph.manifest.artifacts):
            unknown = sorted(set(artifact.fields) - output_fields)
            if unknown:
                diags.append(
                    _Diag(
                        root_graph.graph_root / "graph.yaml",
                        _frontmatter_key_line(root_graph.graph_root / "graph.yaml", "artifacts"),
                        "[F-v3-artifact-declaration-invalid]",
                        f"artifact {artifact.artifact_id!r} names unknown graph output fields: {', '.join(unknown)}",
                        field_path=f"artifacts.{index}.fields",
                    )
                )

    compiled_registry_ids = {
        graph.manifest.graph_id for graph in graphs if graph.graph_root != skill_root.resolve()
    }
    known_registry_targets = compiled_registry_ids | registry_slots
    adjacency: dict[str, set[str]] = {graph_id: set() for graph_id in by_id}
    edge_sources: dict[tuple[str, str], tuple[Path, str]] = {}
    for graph_id, graph in by_id.items():
        for doc in graph.nodes:
            refs: list[tuple[str, str]] = []
            if isinstance(doc.ast, SubgraphNodeAST):
                refs.append((doc.ast.graph, "graph"))
            elif isinstance(doc.ast, AgentNodeAST):
                refs.extend((item.graph, "subgraphs") for item in doc.ast.subgraphs)
            for target, field_path in refs:
                if target not in known_registry_targets:
                    diags.append(
                        _Diag(
                            doc.path,
                            _frontmatter_key_line(doc.path, field_path),
                            "[F-v3-graph-reference-unknown]",
                            f"graph {graph_id!r} references graph {target!r}, which is not in the flat registry",
                            field_path=field_path,
                        )
                    )
                    continue
                if target not in adjacency:
                    # The directory occupies this registry id but its own graph
                    # failed compilation. Its primary diagnostic already names
                    # that defect; reporting every caller as an unknown graph is
                    # a misleading cascade until the target can be compiled.
                    continue
                adjacency[graph_id].add(target)
                edge_sources[(graph_id, target)] = (doc.path, field_path)

    state: dict[str, str] = {}
    stack: list[str] = []
    reported: set[tuple[str, ...]] = set()

    def visit(graph_id: str) -> None:
        state[graph_id] = "gray"
        stack.append(graph_id)
        for target in sorted(adjacency[graph_id]):
            if state.get(target) == "gray":
                start = stack.index(target)
                cycle = tuple(stack[start:] + [target])
                normalized = tuple(sorted(set(cycle)))
                if normalized not in reported:
                    reported.add(normalized)
                    source_path, field_path = edge_sources[(graph_id, target)]
                    diags.append(
                        _Diag(
                            source_path,
                            _frontmatter_key_line(source_path, field_path),
                            "[F-v3-graph-call-cycle]",
                            "graph call cycle detected: " + " -> ".join(cycle),
                            field_path=field_path,
                        )
                    )
            elif state.get(target) is None:
                visit(target)
        stack.pop()
        state[graph_id] = "black"

    for graph_id in adjacency:
        if state.get(graph_id) is None:
            visit(graph_id)
    return diags


def _validate_agent_resource_paths(
    skill_root: Path,
    phase_docs: list[PhaseDocument],
    diags: list[_Diag],
) -> None:
    root_resolved = skill_root.resolve()
    for doc in phase_docs:
        if not isinstance(doc.ast, AgentNodeAST):
            continue
        for reference in doc.ast.references:
            _validate_declared_resource_path(
                skill_root,
                root_resolved,
                doc.path,
                kind="reference",
                item_id=reference.id,
                value=reference.path,
                field_path="references",
                code="[F-v3-resource-reference-path-invalid]",
                diags=diags,
            )
        for example in doc.ast.examples:
            _validate_declared_resource_path(
                skill_root,
                root_resolved,
                doc.path,
                kind="example",
                item_id=example.id,
                value=example.path,
                field_path="examples",
                code="[F-v3-resource-example-path-invalid]",
                diags=diags,
            )


def _validate_declared_resource_path(
    skill_root: Path,
    root_resolved: Path,
    source_path: Path,
    *,
    kind: str,
    item_id: str,
    value: str,
    field_path: str,
    code: str,
    diags: list[_Diag],
) -> None:
    try:
        relative_parts = _portable_resource_path_parts(
            source_path,
            kind=kind,
            item_id=item_id,
            value=value,
            field_path=field_path,
            code=code,
        )
        if not _declared_resource_file_is_readable(skill_root, relative_parts, code):
            detail = (
                f"{source_path}:{_frontmatter_key_line(source_path, field_path)} "
                f"{kind} {item_id!r} path {value!r} is not a readable file inside the skill root"
            )
            diags.append(
                _Diag(
                    path=source_path,
                    line=_frontmatter_key_line(source_path, field_path),
                    code=code,
                    message=detail,
                    field_path=field_path,
                )
            )
    except SkillLoadError as exc:
        for issue in _issues_of(exc):
            diags.append(
                _Diag(
                    path=source_path,
                    line=issue.line or 1,
                    code=issue.rule_id,
                    message=issue.message,
                    field_path=issue.field_path,
                )
            )


def _declared_resource_file_is_readable(
    skill_root: Path,
    relative_parts: tuple[str, ...],
    code: str,
) -> bool:
    from graph_skill_runtime.tools.builtin.read_reference import read_resource_file

    try:
        read_resource_file(
            root=skill_root,
            relative_path=PurePosixPath(*relative_parts).as_posix(),
            code=code,
        )
    except GraphAgentFatalError:
        return False
    return True


def _portable_resource_path_parts(
    source_path: Path,
    *,
    kind: str,
    item_id: str,
    value: str,
    field_path: str,
    code: str,
) -> tuple[str, ...]:
    if re.fullmatch(r"[A-Za-z0-9._/-]+", value) is None:
        detail = (
            f"{source_path}:{_frontmatter_key_line(source_path, field_path)} "
            f"{kind} {item_id!r} path must use portable characters: A-Z a-z 0-9 . _ - /"
        )
        raise SkillLoadError(
            detail,
            payload=make_error_payload(
                code,
                detail,
                field_path=field_path,
                source_path=_payload_source_path(source_path),
            ),
        )
    path = PurePosixPath(value)
    parts = path.parts
    if (
        not parts
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} or ":" in part for part in parts)
    ):
        detail = (
            f"{source_path}:{_frontmatter_key_line(source_path, field_path)} "
            f"{kind} {item_id!r} path must be a portable relative path inside the skill root"
        )
        raise SkillLoadError(
            detail,
            payload=make_error_payload(
                code,
                detail,
                field_path=field_path,
                source_path=_payload_source_path(source_path),
            ),
        )
    return parts


def _compile_subagent_metadata(
    phase_docs: list[PhaseDocument],
    *,
    skill_resolver: SkillResolverProtocol | None,
    _loading_stack: tuple[str, ...],
    _compilation_cache: dict[str, CompiledSkill],
) -> dict[str, list[CompiledSubagent]]:
    subagents_by_phase: dict[str, list[CompiledSubagent]] = {}
    for doc in phase_docs:
        if not isinstance(doc.ast, AgentNodeAST) or not doc.ast.subagents:
            continue
        resolver = require_skill_resolver(skill_resolver, caller="SkillLoader.compile_skill")
        phase_subagents: list[CompiledSubagent] = []
        for spec in doc.ast.subagents:
            sub_root = resolve_skill_root(resolver, spec.target_skill)
            # `_compile_skill_from_root`, not the public `compile_skill`: this is
            # a recursion INSIDE one compile, not the way out of one. The public
            # entry rebases every diagnostic against the root it was handed, so
            # calling it here spent the one rebase on the CHILD root and handed
            # the parent a rootless `phases/<id>/<file>` — which the parent's own
            # boundary then passes through untouched (a relative path has nothing
            # to rebase), so a consumer resolved it against the PARENT root and
            # opened a different file that happened to share the name.
            # Staying on the internal entry keeps paths absolute until the
            # outermost boundary, which is the only place that knows the root the
            # caller asked about.
            sub_compiled = SkillLoader(validate_context_writes=False)._compile_skill_from_root(
                sub_root,
                skill_resolver=resolver,
                runtime_input_fields=None,
                _loading_stack=_loading_stack,
                _compilation_cache=_compilation_cache,
                allowed_roles=None,
            )
            input_schema = sub_compiled.raw.get("io", {}).get("inputs")
            if not isinstance(input_schema, dict) or not input_schema:
                _fatal(
                    doc.path,
                    _frontmatter_key_line(doc.path, "subagents"),
                    f"subagent {spec.name!r} at {spec.target_skill!r} must declare a non-empty io.inputs schema",
                    code="[F-v3-agent-subagent-invalid]",
                )
            try:
                input_model = build_subagent_input_model(
                    _subagent_input_model_name(doc.phase_name, spec.name),
                    input_schema,
                )
            except ValueError as exc:
                _fatal(
                    doc.path,
                    _frontmatter_key_line(doc.path, "subagents"),
                    f"subagent {spec.name!r} io.inputs schema is unsupported: {exc}",
                    code="[F-v3-agent-subagent-invalid]",
                )
            phase_subagents.append(
                CompiledSubagent(
                    parent_phase_id=doc.phase_name,
                    name=spec.name,
                    target_skill=spec.target_skill,
                    description=spec.description,
                    root=sub_root,
                    input_schema=input_schema,
                    input_model=input_model,
                    expected_schema=input_model.model_json_schema(),
                )
            )
        subagents_by_phase[doc.phase_name] = phase_subagents
    return subagents_by_phase


def _inject_subagent_tools(
    registry: ToolRegistry,
    subagents_by_phase: dict[str, list[CompiledSubagent]],
) -> ToolRegistry:
    by_phase = {phase_id: list(tools) for phase_id, tools in registry.by_phase.items()}
    root_tool_names = {tool.id for tool in registry.root_tools}
    for phase_id, subagents in subagents_by_phase.items():
        phase_tools = by_phase.setdefault(phase_id, [])
        existing_names = root_tool_names | {tool.id for tool in phase_tools}
        for subagent in subagents:
            tool_name = f"call_subagent_{subagent.name}"
            if tool_name in existing_names:
                _actions_fatal(
                    subagent.root,
                    1,
                    f"subagent {subagent.name!r} dynamic tool {tool_name!r} conflicts with an existing tool",
                    code="[F-v3-agent-tool-unknown]",
                )
            existing_names.add(tool_name)
            phase_tools.append(_subagent_tool_def(phase_id, subagent, tool_name))
    return ToolRegistry(root_tools=registry.root_tools, by_phase=by_phase)


def _validate_agent_declared_tools(
    phase_docs: list[PhaseDocument],
    registry: ToolRegistry,
    diags: list[_Diag],
) -> None:
    root_tool_names = {tool.id for tool in registry.root_tools}
    framework_tool_names = {
        "finish_task",
        "read_reference",
        "read_example",
        "log_ambiguity",
        # Migration decision 2026-08-15: ask_clarification/update_working_memory
        # mount unconditionally; query_working_memory/read_artifact mount via
        # context_access opt-in — all four names are framework-owned either way.
        "ask_clarification",
        "update_working_memory",
        "query_working_memory",
        "read_artifact",
    }
    for doc in phase_docs:
        if not isinstance(doc.ast, AgentNodeAST):
            continue
        phase_tool_names = {tool.id for tool in registry.by_phase.get(doc.phase_name, [])}
        available = root_tool_names | phase_tool_names | framework_tool_names
        for tool_name in doc.ast.tools:
            if tool_name in framework_tool_names:
                # Built-in framework tools are mounted unconditionally by the
                # assembler; a declaration adds nothing the engine reads — but
                # it makes Studio render the tool as user-managed, deletable
                # included (decision 2026-08-13 D9). Deleting the line is the fix.
                diags.append(
                    _Diag(
                        doc.path,
                        _frontmatter_key_line(doc.path, "tools"),
                        "[F-v3-agent-tool-reserved]",
                    f"tool {tool_name!r} in AGENT phase {doc.phase_name!r} is a "
                        "built-in framework tool: it is always available and must not "
                        "be declared in `tools`; remove the line",
                        field_path="tools",
                    )
                )
                continue
            if tool_name in available or _is_critic_tool_name(tool_name):
                continue
            diags.append(
                _Diag(
                    doc.path,
                    _frontmatter_key_line(doc.path, "tools"),
                    "[F-v3-agent-tool-unknown]",
                    f"tool {tool_name!r} in AGENT phase {doc.phase_name!r} is not declared",
                    field_path="tools",
                )
            )


def _is_critic_tool_name(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in ("critic", "reviewer", "auditor"))


def _subagent_tool_def(
    phase_id: str,
    subagent: CompiledSubagent,
    tool_name: str,
) -> ToolDef:
    args_model = build_subagent_tool_args_model(
        f"{subagent.input_model.__name__}ToolArgs",
        subagent.input_model,
    )
    return ToolDef(
        id=tool_name,
        phase_id=phase_id,
        path=subagent.root / "graph.yaml",
        func=_pending_call_subagent_tool,
        description=(
            f"{subagent.description}\n\n"
            f"Call subagent {subagent.name!r}. Pass inputs as an array; best practice: "
            "no more than 3 inputs per call."
        ),
        args_schema=args_model,
        metadata={
            "kind": "subagent",
            "subagent_name": subagent.name,
            "target_skill": subagent.target_skill,
            "subagent_path": subagent.target_skill,
            "subagent_root": str(subagent.root),
            "expected_schema": subagent.expected_schema,
        },
    )


def _pending_call_subagent_tool(inputs: list[Any]) -> list[dict[str, Any]]:
    """Placeholder for executor-owned subagent dispatch."""

    del inputs
    raise NotImplementedError("call_subagent runtime requires an AgentExecutor adapter")


def _subagent_input_model_name(phase_id: str, subagent_name: str) -> str:
    safe_phase = "".join(part.title() for part in re.split(r"[^A-Za-z0-9]+", phase_id) if part)
    safe_name = "".join(part.title() for part in subagent_name.split("_") if part)
    return f"{safe_phase or 'Phase'}{safe_name or 'Subagent'}Input"


def _load_action_dir(
    actions_dir: Path,
    phase_id: str,
    declared_actions: list[str],
) -> dict[str, ActionDef]:
    """Bind each DECLARED action name to the same-named function in `actions/*.py`.

    The `actions:` list is the action registry (portable format contract
    `docs/skill-spec/01-PORTABLE-GSKILL-V1.md` §5.1), and it is also the only thing
    `graph_assembler._build_logic_node` ever dispatches. So the declaration decides
    which module-level functions are actions; every other function in the file is an
    ordinary private helper the author is free to write, and the action signature rule
    does not apply to it.

    Purity deliberately keeps a wider, file-level scope: a helper can be impure
    just as easily as an action.
    """
    declared = dict.fromkeys(declared_actions)
    by_id: dict[str, ActionDef] = {}
    for path in sorted(actions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        _raise_on_purity_violations(path)
        module = _load_python_module(path)
        for func in _module_functions(module):
            action_id = func.__name__
            if action_id not in declared:
                continue
            _validate_action_signature(path, func)
            if action_id in by_id:
                _actions_fatal(
                    path,
                    1,
                    f"duplicate action id {action_id!r} in phase {phase_id!r}",
                    code="[F-v3-logic-action-name-invalid]",
                )
            by_id[action_id] = ActionDef(id=action_id, phase_id=phase_id, path=path, func=func)

    for action_id in declared:
        if action_id in by_id:
            continue
        expected_file = actions_dir / f"{action_id}.py"
        _actions_fatal(
            expected_file if expected_file.exists() else actions_dir,
            1,
            f"action {action_id!r} is declared by phase {phase_id!r} but no function "
            f"named {action_id!r} is defined in {actions_dir.name}/",
            code="[F-v3-logic-action-entrypoint-missing]",
        )
    return by_id


def _load_tool_dir(tools_dir: Path, *, phase_id: str | None) -> list[ToolDef]:
    tools: list[ToolDef] = []
    for path in sorted(tools_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        _raise_on_purity_violations(path)
        for violation in scan_tool_imports_context(path):
            _actions_fatal(
                path,
                violation.line,
                violation.reason,
                code="[F-v3-agent-tool-unknown]",
            )
        module = _load_python_module(path)
        for func in _module_functions(module):
            _validate_tool_signature(path, func)
            tools.append(ToolDef(id=func.__name__, phase_id=phase_id, path=path, func=func))
    return tools


def _raise_on_purity_violations(path: Path) -> None:
    for violation in scan_python_purity(path):
        if violation.api == "python":
            _actions_fatal(
                path,
                violation.line,
                f"module load failed: {violation.reason}",
                code="[F-v3-logic-action-purity-violation]",
            )
        _purity_fatal(path, violation.line, f"{violation.api} {violation.reason}")


def _load_python_module(path: Path) -> ModuleType:
    module_name = f"_graph_skill_runtime_v21_{abs(hash(path.resolve()))}"
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            _actions_fatal(
                path,
                1,
                "could not create import spec",
                code="[F-v3-logic-action-entrypoint-missing]",
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        tb = traceback.format_exc()
        line = getattr(exc, "lineno", 1) or 1
        _actions_fatal(
            path,
            line,
            f"module load failed: {exc}\n{tb}",
            code="[F-v3-logic-action-entrypoint-missing]",
        )
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def _module_functions(module: ModuleType) -> list[Callable[..., object]]:
    return [
        func
        for _, func in inspect.getmembers(module, inspect.isfunction)
        if getattr(func, "__module__", None) == module.__name__
    ]


def _validate_action_signature(path: Path, func: Callable[..., object]) -> None:
    signature = inspect.signature(func)
    params = list(signature.parameters.values())
    if (
        len(params) != 1
        or params[0].name != "inputs"
        or params[0].kind
        not in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ):
        _actions_fatal(
            path,
            1,
            f"action {func.__name__!r} must accept exactly one inputs parameter",
            code="[F-v3-logic-action-entrypoint-missing]",
        )
    annotation = params[0].annotation
    if annotation is inspect.Parameter.empty:
        return
    if annotation is dict:
        return
    if get_origin(annotation) is dict:
        return
    if isinstance(annotation, str) and annotation in {"dict", "dict[str, Any]", "Dict[str, Any]"}:
        return
    _actions_fatal(
        path,
        1,
        f"action {func.__name__!r} first parameter must be dict-compatible inputs",
        code="[F-v3-logic-action-entrypoint-missing]",
    )


def _validate_tool_signature(path: Path, func: Callable[..., object]) -> None:
    signature = inspect.signature(func)
    for param in signature.parameters.values():
        if param.name in {"context", "ctx", "state", "blackboard"}:
            _actions_fatal(
                path,
                1,
                f"tool {func.__name__!r} must not accept blackboard parameter {param.name!r}",
                code="[F-v3-agent-tool-unknown]",
            )


def _route_document(file_path: Path) -> RouteKind:
    if file_path.name == "graph.yaml":
        if file_path.parent.name == "phases" or file_path.parent.parent.name == "phases":
            _fatal(
                file_path,
                1,
                "graph.yaml is only allowed at the skill root or graphs/<graph_id>",
                code="[F-v3-graph-root-missing]",
            )
        return "graph"
    if file_path.name in _PHASE_FILE_TO_MODE:
        return _PHASE_FILE_TO_MODE[file_path.name]  # type: ignore[return-value]
    _fatal(
        file_path,
        1,
        "unsupported portable gSkill document filename",
        code="[F-v3-graph-root-missing]",
    )


def _reject_phase_forbidden_metadata(path: Path, frontmatter: dict[str, Any]) -> None:
    for key in ("mode", "schema_version", "graph_skill_id", "phase_id", "raw_blocks", "system_prompt"):
        if key not in frontmatter:
            continue
        domain = _PHASE_FILE_TO_MODE.get(path.name, "graph")
        code = f"[F-v3-{domain}-schema-unknown-field]"
        _fatal(
            path,
            _frontmatter_key_line(path, key),
            f"{code} phase frontmatter field {key!r} is not allowed",
            field_path=key,
        )


def _build_graph_manifest(
    path: Path,
    frontmatter: dict[str, Any],
) -> tuple[GraphManifest, list[_Diag], bool]:
    data = dict(frontmatter)
    try:
        manifest = GraphManifest.model_validate(data)
        return manifest, [], False
    except ValidationError as exc:
        diags: list[_Diag] = []
        for error in exc.errors():
            loc = error.get("loc", ())
            msg = error.get("msg", "")
            type_ = error.get("type", "")
            line = _frontmatter_loc_line(path, frontmatter, loc)
            field_path = _field_path_from_loc(loc)

            code = None
            clean_msg = msg

            if loc == ("schema_version",):
                code = "[F-v3-graph-schema-version-mismatch]"
            elif loc == ("io",):
                if type_ == "missing":
                    code = "[F-v3-graph-io-schema-invalid]"
                else:
                    code = "[F-v3-graph-io-not-object]"
            elif loc == ("graph_id",):
                code = "[F-v3-graph-name-invalid]"
            elif loc == ("phases",):
                code = "[F-v3-graph-phases-missing]"
            elif len(loc) >= 3 and loc[0] == "phases" and loc[2] == "id":
                code = "[F-v3-graph-phase-id-invalid]"
            elif len(loc) >= 3 and loc[0] == "phases" and loc[2] == "depends_on":
                code = "[F-v3-graph-depends-unknown]"
            elif len(loc) >= 3 and loc[0] == "phases" and loc[2] == "output":
                code = "[F-v3-graph-output-phase-invalid]"
            elif loc and loc[0] == "artifacts":
                code = "[F-v3-artifact-declaration-invalid]"
            elif loc == () and "phase ids must be unique" in msg:
                code = "[F-v3-graph-phase-id-duplicate]"
            elif loc == () and "at least one output phase" in msg:
                code = "[F-v3-graph-output-phase-invalid]"
            elif loc == () and "artifact ids must be unique" in msg:
                code = "[F-v3-artifact-declaration-invalid]"

            if code is None:
                match = re.search(r"\[(F-v3-[a-z0-9-]+)\]", msg)
                if match:
                    code = f"[{match.group(1)}]"
                    clean_msg = msg.replace(code, "").strip()
                    if clean_msg.startswith("Value error, "):
                        clean_msg = clean_msg[len("Value error, ") :]

            if code is None:
                code = "[F-v3-graph-schema-unknown-field]"

            diags.append(
                _Diag(
                    path=path,
                    line=line,
                    code=code,
                    message=clean_msg,
                    field_path=field_path,
                )
            )

        placeholder_io = PhaseIOSchema(
            inputs={"type": "object", "properties": {"dummy": {"type": "string"}}},
            outputs={"type": "object", "properties": {"dummy": {"type": "string"}}},
        )
        manifest = GraphManifest.model_construct(
            schema_version="gskill.graph.v1",
            graph_id="invalid-graph",
            description="",
            llm_role=None,
            io=placeholder_io,
            phases=(GraphPhaseRef(id="invalid", depends_on=("input",), output=True),),
            iterate=None,
            artifacts=(),
        )
        return manifest, diags, True


def _phase_refs_from_manifest(graph_path: Path, manifest: GraphManifest) -> list[PhaseTopologyRef]:
    """Adapt typed YAML phase declarations to the characterized topology engine.

    This is a total 1:1 map over ``manifest.phases``: one ref per declared
    phase, no filter and no skip. Every downstream topology check therefore
    sees exactly the ids the validated ``GraphManifest`` already guarantees to
    be present, unique and well-formed — which is why re-checking those three
    facts here would be unreachable rather than defensive.
    """

    lines = read_authored_text(graph_path).splitlines()
    refs: list[PhaseTopologyRef] = []
    for phase in manifest.phases:
        phase_line = _yaml_phase_id_line(lines, phase.id)
        attrs = {
            "depends_on": ",".join(phase.depends_on),
            "output": "true" if phase.output else "false",
        }
        token = PhaseTokenInfo(
            phase_id=phase.id,
            raw_text=yaml.safe_dump(phase.model_dump(mode="json"), sort_keys=False).rstrip(),
            line_start=phase_line,
            line_end=phase_line,
            attrs=attrs,
        )
        refs.append(
            PhaseTopologyRef(
                name=phase.id,
                depends_on=phase.depends_on,
                output=phase.output,
                token=token,
            )
        )
    return refs


def _yaml_phase_id_line(lines: list[str], phase_id: str) -> int:
    pattern = re.compile(rf"^\s*-\s*id\s*:\s*['\"]?{re.escape(phase_id)}['\"]?\s*(?:#.*)?$")
    for index, line in enumerate(lines, start=1):
        if pattern.match(line):
            return index
    return 1


def get_phase_token_info(compiled: CompiledSkill, phase_id: str) -> PhaseTokenInfo | None:
    """Return source token metadata for a phase in a compiled skill.

    The metadata lives on ``CompiledSkill`` so ``GraphManifest`` and
    ``GraphPhaseRef`` remain pure Pydantic business contracts without a global
    id-based registry.
    """

    return compiled.phase_tokens.get(phase_id)


def _validate_graph_topology(
    graph_path: Path,
    phases: list[str],
    phase_refs: list[PhaseTopologyRef],
    skill_root: Path,
    diags: list[_Diag],
) -> dict[str, Any]:
    """Validate the phase DAG, collecting every independent defect into ``diags``.

    This stage never aborts: phase dirs, islands, unknown deps, cycles and
    output markers all accumulate, so one compile reports the whole stage
    (compile-rules §2.1 同阶段尽量聚合). The caller only reaches here with a
    validated ``GraphManifest``, so phase presence, id grammar and id
    uniqueness are already settled facts rather than checks to repeat. When
    ``diags`` is non-empty the returned dict is a placeholder: the caller
    raises at the collect-all barrier before anything consumes it.
    """
    _validate_phase_name_sets(graph_path, phases, skill_root, diags)
    adjacency, input_roots, flagged = _collect_graph_dependencies(
        graph_path,
        phases,
        phase_refs,
        diags,
    )

    # File-absolute graph.yaml line of each phase's own entry, shared by the cycle
    # and island diagnostics so both mark the offending phase (not the file head).
    line_by_name = {ref.name: ref.token.line_start for ref in phase_refs}
    cycle_nodes = _validate_acyclic_graph(graph_path, adjacency, line_by_name, diags)
    # Phases already diagnosed (no depends_on / unknown dep / cycle member) seed
    # the reachability walk instead of re-flagging: their unreachability is the
    # defect already reported, and their downstream is only unreachable as a
    # cascade of it.
    _validate_no_islands(graph_path, adjacency, input_roots, line_by_name, diags, flagged | cycle_nodes)
    _validate_output_phases(graph_path, phase_refs, adjacency, diags)
    return {
        "phases": [
            {
                "name": ref.name,
                "depends_on": list(ref.depends_on),
                "output": ref.output,
            }
            for ref in phase_refs
        ],
        "order": _topological_order(adjacency, phases) if not diags else [],
    }


def _validate_phase_name_sets(
    graph_path: Path,
    phases: list[str],
    skill_root: Path,
    diags: list[_Diag],
) -> None:
    """Report, per id, every disagreement between graph.yaml and phases/ dirs.

    The two sets are independent facts — one is authored text, the other is the
    filesystem — so each side's surplus gets its own located diagnostic instead
    of one set-inequality fatal that names neither id.
    """
    phase_set = set(phases)
    physical_set = {path.name for path in (skill_root / "phases").iterdir() if path.is_dir()}

    missing = sorted(phase_set - physical_set)
    unregistered = sorted(physical_set - phase_set)
    for phase_id in missing:
        diags.append(
            _Diag(
                graph_path,
                _frontmatter_key_line(graph_path, "phases"),
                "[F-v3-graph-phase-name-mismatch]",
                f"graph.yaml phase {phase_id!r} has no matching phase directory",
                field_path="phases",
            )
        )
    for phase_id in unregistered:
        diags.append(
            _Diag(
                skill_root / "phases" / phase_id,
                1,
                "[F-v3-graph-phase-name-mismatch]",
                f"phase directory {phase_id!r} is not registered in graph.yaml",
                field_path="phases",
            )
        )


def _collect_graph_dependencies(
    graph_path: Path,
    phases: list[str],
    phase_refs: list[PhaseTopologyRef],
    diags: list[_Diag],
) -> tuple[dict[str, list[str]], list[str], set[str]]:
    """Build the adjacency map, collecting per-phase/per-edge defects.

    Returns ``(adjacency, input_roots, flagged)`` where ``flagged`` holds the
    phases already diagnosed here (bare / unknown dep / self-dep) so the
    reachability check does not cascade a second diagnostic onto them.
    """
    phase_set = set(phases)
    adjacency: dict[str, list[str]] = {name: [] for name in phases}
    input_roots: list[str] = []
    flagged: set[str] = set()
    for ref in phase_refs:
        if not ref.depends_on:
            # `depends_on` is required (portable gSkill v1 contract §4.2;
            # first node must declare `depends_on: [input]`). A bare phase with no
            # depends_on is a disconnected node — flag it as an island instead of
            # silently treating it as an implicit input root. field_path carries the
            # node locator so Studio's realtime-lint badges the offending node.
            diags.append(
                _make_diag(
                    graph_path,
                    ref.token.line_start,
                    f"[F-v3-graph-phase-island] phase {ref.name!r} declares no depends_on "
                    '(every phase must connect to "input" or an upstream phase)',
                    field_path=f"{ref.name}.depends_on",
                )
            )
            flagged.add(ref.name)
        for dep in ref.depends_on:
            if dep == "input":
                input_roots.append(ref.name)
                continue
            if dep not in phase_set:
                diags.append(
                    _make_diag(
                        graph_path,
                        ref.token.line_start,
                        f"[F-v3-graph-depends-unknown] phase {ref.name!r} depends_on unknown phase {dep!r}",
                        field_path=f"{ref.name}.depends_on",
                    )
                )
                flagged.add(ref.name)
                continue
            if dep == ref.name:
                diags.append(
                    _make_diag(
                        graph_path,
                        ref.token.line_start,
                        f"[F-v3-graph-phase-cycle] phase {ref.name!r} cannot depend on itself",
                        field_path=f"{ref.name}.depends_on",
                    )
                )
                flagged.add(ref.name)
                continue
            adjacency[dep].append(ref.name)
    return adjacency, input_roots, flagged


def _validate_acyclic_graph(
    graph_path: Path,
    adjacency: dict[str, list[str]],
    line_by_name: dict[str, int],
    diags: list[_Diag],
) -> set[str]:
    """Record every multi-node cycle found; return the phases involved."""

    state: dict[str, str] = {}
    stack: list[str] = []
    cycle_nodes: set[str] = set()

    def visit(node: str) -> None:
        state[node] = "gray"
        stack.append(node)
        for nxt in adjacency[node]:
            if state.get(nxt) == "gray":
                start = stack.index(nxt)
                cycle = stack[start:] + [nxt]
                cycle_nodes.update(cycle)
                diags.append(
                    _make_diag(
                        graph_path,
                        line_by_name.get(cycle[0], 1),
                        "[F-v3-graph-phase-cycle] cycle detected: " + " -> ".join(cycle),
                    )
                )
                continue
            if state.get(nxt) is None:
                visit(nxt)
        stack.pop()
        state[node] = "black"

    for node in adjacency:
        if state.get(node) is None:
            visit(node)
    return cycle_nodes


def _validate_no_islands(
    graph_path: Path,
    adjacency: dict[str, list[str]],
    input_roots: list[str],
    line_by_name: dict[str, int],
    diags: list[_Diag],
    suppress: set[str],
) -> None:
    """Flag every phase unreachable from input (minus already-diagnosed ones).

    ``suppress`` phases seed the walk: they already carry their own diagnostic
    (bare / unknown dep / cycle member), so neither they nor their downstream
    should drown the report in cascade islands.
    """
    visited: set[str] = set()
    stack = list(input_roots) + sorted(suppress)
    while stack:
        node = stack.pop()
        if node in visited or node not in adjacency:
            continue
        visited.add(node)
        stack.extend(sorted(set(adjacency[node]) - visited))

    # Point the diagnostic at the offending graph.yaml phase entry and carry
    # its depends_on field path so editor projections can mark the same node.
    # Use the file-absolute diagnostic line shared by sibling topology rules.
    for phase_id in adjacency:
        if phase_id not in visited:
            diags.append(
                _make_diag(
                    graph_path,
                    line_by_name.get(phase_id, 1),
                    f"[F-v3-graph-phase-island] phase {phase_id!r} is unreachable from input",
                    field_path=f"{phase_id}.depends_on",
                )
            )


def _validate_output_phases(
    graph_path: Path,
    phase_refs: list[PhaseTopologyRef],
    adjacency: dict[str, list[str]],
    diags: list[_Diag],
) -> None:
    outputs = {ref.name for ref in phase_refs if ref.output}
    non_terminal = {phase for phase, downstream in adjacency.items() if downstream}
    invalid = sorted(outputs & non_terminal)
    if invalid:
        diags.append(
            _make_diag(
                graph_path,
                1,
                "[F-v3-graph-output-phase-invalid] output phase has downstream edges: " + ", ".join(invalid),
            )
        )


def _topological_order(adjacency: dict[str, list[str]], phases: list[str]) -> list[str]:
    indegree = {phase: 0 for phase in phases}
    for downstream in adjacency.values():
        for phase in downstream:
            indegree[phase] += 1
    queue = [phase for phase in phases if indegree[phase] == 0]
    order: list[str] = []
    while queue:
        phase = queue.pop(0)
        order.append(phase)
        for nxt in adjacency[phase]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return order


#: Values of `io.outputs.<field>.target` that make the runner write a file.
#: Anything else used to compile clean and then silently produce nothing — a
#: session probing the contract with a junk value got `status: ok`, 0 defects,
#: and its junk carried straight into the manifest (exp-b-round3, 2026-08-03).
DECLARED_OUTPUT_TARGETS = frozenset({"file", "artifact"})


def _validate_inline_io_schema(
    path: Path,
    schema: dict[str, Any],
    kind: str,
    *,
    domain: str = "graph",
) -> dict[str, Any]:
    field_path = f"io.{kind}s"
    invalid_code = _io_schema_error_code(domain)
    if not isinstance(schema, dict):
        _io_fatal(
            path,
            1,
            f"inline {kind} schema must be an object",
            field_path=field_path,
            code="[F-v3-graph-io-not-object]" if domain == "graph" else invalid_code,
        )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        _io_fatal(
            path,
            1,
            f"invalid inline {kind} JSON Schema: {exc.message}",
            field_path=field_path,
            code=invalid_code,
        )
    if schema.get("type") != "object":
        _io_fatal(
            path,
            1,
            f"inline {kind} schema must declare type: object",
            field_path=f"{field_path}.type",
            code="[F-v3-graph-io-not-object]" if domain == "graph" else invalid_code,
        )
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        _io_fatal(
            path,
            1,
            f"inline {kind} schema must declare object properties",
            field_path=f"{field_path}.properties",
            code=invalid_code,
        )
    required = schema.get("required", [])
    if required is None:
        required = []
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        _io_fatal(
            path,
            1,
            f"inline {kind} schema required must be a list of field names",
            field_path=f"{field_path}.required",
            code=invalid_code,
        )
    missing_required = sorted(set(required) - set(properties))
    if missing_required:
        _io_fatal(
            path,
            1,
            f"inline {kind} schema required fields are missing from properties: " + ", ".join(missing_required),
            field_path=f"{field_path}.required",
            code=invalid_code,
        )
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(field_schema, dict):
            continue
        target = field_schema.get("target")
        if kind == "output" and target is not None and target not in DECLARED_OUTPUT_TARGETS:
            allowed = ", ".join(sorted(DECLARED_OUTPUT_TARGETS))
            _io_fatal(
                path,
                1,
                f"inline {kind} field {field_name!r} declares target {target!r}; "
                f"a written output must declare one of: {allowed}",
                field_path=f"{field_path}.properties.{field_name}.target",
                code=invalid_code,
            )
        if field_schema.get("source") == "file":
            _io_fatal(
                path,
                1,
                f"inline {kind} field {field_name!r} uses source:file; file imports "
                "must be declared in .workspace/runtime_config.json",
                field_path=f"{field_path}.properties.{field_name}.source",
                code=invalid_code,
            )
    return schema


def _io_schema_error_code(domain: str) -> str:
    return {
        "agent": "[F-v3-agent-io-schema-invalid]",
        "logic": "[F-v3-logic-io-schema-invalid]",
        "subgraph": "[F-v3-subgraph-io-schema-invalid]",
    }.get(domain, "[F-v3-graph-io-schema-invalid]")


def _extract_output_schema_keys(schema: dict[str, Any]) -> set[str] | None:
    properties = schema.get("properties")
    if properties is None:
        return None
    if not isinstance(properties, dict):
        return set()
    return {key for key in properties if isinstance(key, str)}


def _validate_iterate_compile_contracts(
    phase_docs: list[PhaseDocument],
    diags: list[_Diag],
) -> None:
    for doc in phase_docs:
        iterate = getattr(doc.ast, "iterate", None)
        io = getattr(doc.ast, "io", None)
        input_keys = _extract_output_schema_keys(io.inputs) if io is not None else set()

        if iterate is not None and iterate.mode == "loop":
            accumulate = iterate.accumulate
            if accumulate is None:
                diags.append(
                    _Diag(
                        path=doc.path,
                        line=_frontmatter_key_line(doc.path, "iterate"),
                        code="[F-v3-iterate-accumulate-fields-missing]",
                        message="loop iterate io.inputs must declare accumulate",
                        field_path="iterate",
                    )
                )
            else:
                missing = [
                    name
                    for name in (iterate.item_var, accumulate.var)
                    if input_keys is not None and name not in input_keys
                ]
                if missing:
                    diags.append(
                        _Diag(
                            path=doc.path,
                            line=_frontmatter_key_line(doc.path, "iterate"),
                            code="[F-v3-iterate-accumulate-fields-missing]",
                            message=f"loop iterate io.inputs must declare {', '.join(missing)}",
                            field_path="iterate",
                        )
                    )

        batch = getattr(doc.ast, "batch", None)
        if batch is not None:
            if input_keys is not None and batch.item_var not in input_keys:
                diags.append(
                    _Diag(
                        path=doc.path,
                        line=_frontmatter_key_line(doc.path, "batch"),
                        code="[F-v3-iterate-accumulate-fields-missing]",
                        message=f"batch iterate io.inputs must declare {batch.item_var}",
                        field_path="batch",
                    )
                )


def _iterate_fields_fatal(path: Path, missing: str) -> NoReturn:
    _fatal(
        path,
        _frontmatter_key_line(path, "iterate"),
        f"[F-v3-iterate-accumulate-fields-missing] loop iterate io.inputs must declare {missing}",
        code="[F-v3-iterate-accumulate-fields-missing]",
        field_path="iterate",
    )


def _validate_static_dataflow(
    graph_path: Path,
    graph_topology: dict[str, Any],
    phase_docs: list[PhaseDocument],
    root_inputs: dict[str, Any],
    root_outputs: dict[str, Any],
    graph_iterate: IterateSpec | None = None,
    *,
    runtime_input_fields: dict[str, set[str]] | None = None,
    diags: list[_Diag],
    poisoned_phases: set[str],
) -> None:
    docs_by_phase = {doc.phase_name: doc for doc in phase_docs}
    rows = graph_topology.get("phases")
    deps_by_phase: dict[str, list[str]] = {}
    output_phases: set[str] = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            phase_name = row.get("name")
            depends_on = row.get("depends_on")
            if isinstance(phase_name, str) and isinstance(depends_on, list):
                deps_by_phase[phase_name] = [dep for dep in depends_on if isinstance(dep, str)]
            if isinstance(phase_name, str) and row.get("output") is True:
                output_phases.add(phase_name)
    raw_order = graph_topology.get("order")
    order = [name for name in raw_order if isinstance(name, str)] if isinstance(raw_order, list) else []
    if not order:
        order = [doc.phase_name for doc in phase_docs]

    root_input_keys = set(_schema_property_paths(root_inputs))
    available_after: dict[str, set[str]] = {}

    if graph_iterate is not None and not _field_is_supplied(graph_iterate.over, root_input_keys):
        diags.append(
            _Diag(
                graph_path,
                _frontmatter_key_line(graph_path, "iterate"),
                "[F-v3-iterate-over-not-list]",
                f"graph iterate over field {graph_iterate.over!r} is not a root input "
                "field, so it cannot resolve to a list at runtime",
                field_path="iterate.over",
            )
        )

    local_poisoned = set(poisoned_phases)

    for phase_name in order:
        doc = docs_by_phase.get(phase_name)
        if doc is None:
            continue

        io_line = _frontmatter_key_line(doc.path, "io")

        deps = deps_by_phase.get(phase_name, [])
        poisoned_deps = [dep for dep in deps if dep in local_poisoned]

        if phase_name in local_poisoned or poisoned_deps:
            local_poisoned.add(phase_name)
            reason = (
                f"phase {phase_name!r} itself is poisoned"
                if phase_name in poisoned_phases
                else f"upstream dependencies {poisoned_deps} are poisoned"
            )
            diags.append(
                _Diag(
                    doc.path,
                    io_line,
                    "[F-v3-graph-dataflow-source-missing]",
                    f"skipped dataflow check for phase {phase_name!r} "
                    f"due to poisoned upstream or self compile error ({reason})",
                    field_path=f"{phase_name}.io",
                )
            )
            continue

        available = set()
        for dep in deps:
            if dep == "input":
                available.update(root_input_keys)
            else:
                available.update(available_after.get(dep, set()))

        input_schema = _phase_input_schema(doc)
        for input_key in _schema_property_paths(input_schema):
            if (
                _field_is_supplied(input_key, available)
                or _runtime_input_field_is_supplied(runtime_input_fields, phase_name, input_key)
                or _schema_field_has_iterate_source(doc, input_key, graph_iterate)
            ):
                continue
            diags.append(
                _Diag(
                    doc.path,
                    io_line,
                    "[F-v3-graph-dataflow-source-missing]",
                    f"phase {phase_name!r} input {input_key!r} has no root, upstream, "
                    "runtime input, or iterator provider",
                    field_path=f"{phase_name}.io.inputs.properties.{input_key}",
                )
            )
        phase_iterate = getattr(doc.ast, "iterate", None)
        over_field = getattr(phase_iterate, "over", None)
        if (
            isinstance(over_field, str)
            and not _field_is_supplied(over_field, available)
            and not _runtime_input_field_is_supplied(runtime_input_fields, phase_name, over_field)
        ):
            diags.append(
                _Diag(
                    doc.path,
                    _frontmatter_key_line(doc.path, "iterate"),
                    "[F-v3-iterate-over-not-list]",
                    f"iterate over field {over_field!r} of phase {phase_name!r} has no "
                    "root, upstream, or runtime input source, so it cannot resolve to "
                    "a list at runtime",
                    field_path=f"{phase_name}.iterate.over",
                )
            )

        available_after[phase_name] = available | _phase_blackboard_output_keys(doc)

    terminal_output_keys: set[str] = set()
    for phase_name in output_phases:
        if phase_name in local_poisoned:
            continue
        terminal_output_keys.update(available_after.get(phase_name, set()))

    for required_key in _schema_required_keys(root_outputs):
        if _field_is_supplied(required_key, terminal_output_keys):
            continue
        diags.append(
            _Diag(
                graph_path,
                _frontmatter_key_line(graph_path, "io"),
                "[F-v3-graph-dataflow-source-missing]",
                f"required root output {required_key!r} is not produced by an output phase",
                field_path=f"io.outputs.required.{required_key}",
            )
        )


def _phase_blackboard_output_keys(doc: PhaseDocument) -> set[str]:
    """What a phase leaves on the blackboard for phases downstream of it.

    For most phases that is exactly its declared ``io.outputs``. A
    ``iterate.mode=loop`` phase is the exception: its ``io.outputs`` is the
    contract for ONE round of the body — validated on every round, and required
    to carry ``accumulate.from`` — while the only value the phase writes when
    the loop ends is the accumulator (``_build_loop_iterate_phase``). Reading
    ``io.outputs`` as the provided set here would make the compile-time
    dataflow disagree with the runtime in both directions at once, leaving the
    author no way to declare a loop that a downstream phase can consume.
    """
    iterate = getattr(doc.ast, "iterate", None)
    if getattr(iterate, "mode", None) == "loop":
        accumulate = getattr(iterate, "accumulate", None)
        # A loop without accumulate is already fatal from
        # _validate_iterate_compile_contracts, and provides nothing here.
        return {accumulate.var} if accumulate is not None else set()
    return set(_schema_property_paths(_phase_output_schema(doc)))


def _phase_input_schema(doc: PhaseDocument) -> dict[str, Any]:
    io = getattr(doc.ast, "io", None)
    if io is None:
        return {}
    inputs = io.inputs
    return inputs if isinstance(inputs, dict) else {}


def _phase_output_schema(doc: PhaseDocument) -> dict[str, Any]:
    io = getattr(doc.ast, "io", None)
    if io is None:
        return {}
    outputs = io.outputs
    return outputs if isinstance(outputs, dict) else {}


def _schema_property_keys(schema: dict[str, Any]) -> set[str]:
    return set(_schema_property_paths(schema))


def _schema_property_paths(schema: dict[str, Any]) -> list[str]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return _flatten_schema_property_paths(properties)


def _flatten_schema_property_paths(properties: dict[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for key, field_schema in properties.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}{key}"
        paths.append(path)
        if _is_object_schema(field_schema):
            nested = field_schema.get("properties") if isinstance(field_schema, dict) else None
            if isinstance(nested, dict):
                paths.extend(_flatten_schema_property_paths(nested, prefix=f"{path}."))
    return paths


def _is_object_schema(schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    schema_type = schema.get("type")
    if schema_type == "object":
        return True
    if isinstance(schema_type, list) and "object" in schema_type:
        return True
    return isinstance(schema.get("properties"), dict)


def _ancestor_paths(field: str) -> list[str]:
    parts = field.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))][::-1]


def _field_is_supplied(field: str, available: set[str]) -> bool:
    return any(path in available for path in _ancestor_paths(field))


def _runtime_input_field_is_supplied(
    runtime_input_fields: dict[str, set[str]] | None,
    phase_name: str,
    field: str,
) -> bool:
    if not runtime_input_fields:
        return False
    phase_fields = runtime_input_fields.get(phase_name)
    if not phase_fields:
        return False
    return _field_is_supplied(field, phase_fields)


def _schema_required_keys(schema: dict[str, Any]) -> set[str]:
    required = schema.get("required", [])
    if not isinstance(required, list):
        return set()
    return {key for key in required if isinstance(key, str)}


def _schema_field_has_iterate_source(
    doc: PhaseDocument,
    field: str,
    graph_iterate: IterateSpec | None = None,
) -> bool:
    batch = getattr(doc.ast, "batch", None)
    if batch is not None and _field_matches_injected_var(field, batch.item_var):
        return True
    iterate = getattr(doc.ast, "iterate", None)
    return _iterate_spec_supplies_field(iterate, field) or _iterate_spec_supplies_field(graph_iterate, field)


def _iterate_spec_supplies_field(iterate: IterateSpec | None, field: str) -> bool:
    if iterate is None:
        return False
    if _field_matches_injected_var(field, iterate.item_var):
        return True
    return iterate.accumulate is not None and _field_matches_injected_var(field, iterate.accumulate.var)


def _field_matches_injected_var(field: str, var_name: str) -> bool:
    return field == var_name or field.startswith(f"{var_name}.")


class _ActionReturnKeyVisitor(ast.NodeVisitor):
    def __init__(
        self,
        path: Path,
        allowed_return_keys: set[str] | None,
    ) -> None:
        self.path = path
        self.allowed_return_keys = allowed_return_keys

    def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
        value = node.value
        if isinstance(value, ast.Dict):
            for key_node in value.keys:
                if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                    continue
                if self.allowed_return_keys is not None and key_node.value not in self.allowed_return_keys:
                    line = getattr(key_node, "lineno", node.lineno)
                    _actions_keys_fatal(
                        self.path,
                        line,
                        f"action returns undeclared output key {key_node.value!r}",
                    )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            _validate_inputs_not_mutated(self.path, target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        _validate_inputs_not_mutated(self.path, node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        _validate_inputs_not_mutated(self.path, node.target)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:  # noqa: N802
        for target in node.targets:
            _validate_inputs_not_mutated(self.path, target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        mutation = _inputs_mutating_method_name(node)
        if mutation is not None:
            _actions_fatal(
                self.path,
                getattr(node, "lineno", 1),
                f"{mutation} mutates read-only inputs; return declared output keys instead",
                code="[F-v3-logic-action-purity-violation]",
            )
        self.generic_visit(node)


def _validate_inputs_not_mutated(path: Path, target: ast.AST) -> None:
    if not _target_mutates_inputs(target):
        return
    _actions_fatal(
        path,
        getattr(target, "lineno", 1),
        "item_assignment mutates read-only inputs; return declared output keys instead",
        code="[F-v3-logic-action-purity-violation]",
    )


def _target_mutates_inputs(target: ast.AST) -> bool:
    if isinstance(target, ast.Name) and target.id == "inputs":
        return True
    if isinstance(target, ast.Subscript):
        return _target_mutates_inputs(target.value)
    if isinstance(target, ast.Attribute):
        return _target_mutates_inputs(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_mutates_inputs(item) for item in target.elts)
    return False


def _inputs_mutating_method_name(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in {"clear", "pop", "popitem", "set", "setdefault", "update", "__setitem__"}:
        return None
    if isinstance(func.value, ast.Name) and func.value.id == "inputs":
        return func.attr
    return None


def _validate_logic_action_return_keys(
    phase_docs: list[PhaseDocument],
    actions: ActionRegistry,
    input_schema_keys: set[str] | None,
    output_schema_keys: set[str] | None,
    *,
    validate_context_writes: bool,
    diags: list[_Diag],
) -> None:
    del input_schema_keys, output_schema_keys, validate_context_writes
    for doc in phase_docs:
        if not isinstance(doc.ast, LogicNodeAST):
            continue
        phase_output_schema_keys = _extract_output_schema_keys(doc.ast.io.outputs)
        if phase_output_schema_keys is None:
            continue
        for action_name in doc.ast.actions:
            action_def = actions.for_phase(doc.phase_name).get(action_name)
            if action_def is None:
                continue
            try:
                _validate_action_return_keys(action_def.path, phase_output_schema_keys)
            except SkillLoadError as exc:
                for issue in _issues_of(exc):
                    diags.append(
                        _Diag(
                            path=action_def.path,
                            line=issue.line or 1,
                            code=issue.rule_id,
                            message=issue.message,
                            field_path=issue.field_path,
                        )
                    )


def _validate_action_return_keys(
    path: Path,
    output_schema_keys: set[str] | None,
) -> None:
    try:
        tree = ast.parse(read_authored_text(path), filename=str(path))
    except SyntaxError as exc:
        _actions_keys_fatal(path, exc.lineno or 1, f"could not parse action source: {exc.msg}")
    except OSError as exc:
        _actions_keys_fatal(path, 1, f"could not read action source: {exc}")
    _ActionReturnKeyVisitor(path, output_schema_keys).visit(tree)


def build_phase_document(
    phase_name: str,
    path: Path,
    mode: str,
    frontmatter: dict[str, Any],
    body: str,
) -> PhaseDocument:
    allowed = [
        "role",
        "goal",
        "step",
        "protocol",
        "example",
        "action",
    ]
    blocks = extract_raw_blocks(body, allowed)
    data = dict(frontmatter)
    data["raw_blocks"] = blocks
    data["mode"] = mode
    is_agent = path.name == "AGENT.md"
    if is_agent:
        data = _normalize_skill_node_frontmatter(path, data)

    # Body-structure diagnostics (missing <goal>, empty <action>, deprecated
    # target_skill, ...) and frontmatter schema diagnostics (pydantic
    # model_validate) used to be two sequential steps that could each abort
    # this file's compile independently — whichever ran first won, and the
    # other's defect in the SAME file only surfaced on the NEXT compile after
    # the first was fixed. That is the exact host-product complaint F6 names
    # ("将role 补上,goal的报错才出现"); F6 belongs to the host product's
    # compile-lint design, not to this repository, so it is named rather than
    # linked. Each branch below collects its own body-structure
    # diagnostics instead of raising them immediately, then hands them to
    # ``_validate_phase_ast`` to merge with any schema diagnostics from the
    # SAME model_validate call before raising once.
    if mode == "logic":
        actions, action_diags = _extract_logic_actions_collecting(path, body)
        # An empty/absent <action> defect is already reported via
        # action_diags; feed the schema a non-empty placeholder so its own
        # min_length=1 check does not ALSO flag it under a generic code.
        data.setdefault("actions", actions or ["(no action tags)"])
        logic_ast = _validate_phase_ast(LogicNodeAST, data, path, mode, frontmatter, action_diags)
        _validate_logic_actions_declared(path, logic_ast, body)
        ast: PhaseAST = logic_ast
    elif mode == "subgraph":
        ast = _validate_phase_ast(SubgraphNodeAST, data, path, mode, frontmatter, [])
    elif is_agent:
        body_fields, body_diags = _parse_agent_body(path, body, blocks)
        data.update(body_fields)
        ast = _validate_phase_ast(AgentNodeAST, data, path, mode, frontmatter, body_diags)
        _validate_agent_mentions(path, ast, body)
    else:
        _fatal(
            path,
            1,
            f"unsupported phase file {path.name}",
            code="[F-v3-graph-phase-node-missing]",
        )

    _validate_phase_io_schemas(path, mode, ast)
    return PhaseDocument(
        phase_name=phase_name,
        path=path,
        mode=mode,
        frontmatter=frontmatter,
        raw_blocks=blocks,
        ast=ast,
    )


def _validate_phase_io_schemas(path: Path, mode: str, ast: PhaseAST) -> None:
    io = getattr(ast, "io", None)
    if io is None:
        return
    _validate_inline_io_schema(path, io.inputs, "input", domain=mode)
    _validate_inline_io_schema(path, io.outputs, "output", domain=mode)


def _normalize_skill_node_frontmatter(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    if "phase_config" not in data:
        return data
    _fatal(
        path,
        _frontmatter_key_line(path, "phase_config"),
        "[F-v3-agent-schema-unknown-field] phase_config is not supported; declare Agent fields at top level",
        code="[F-v3-agent-schema-unknown-field]",
        field_path="phase_config",
    )


_PhaseModelT = TypeVar("_PhaseModelT", bound=BaseModel)


def _validate_phase_ast(
    model_cls: type[_PhaseModelT],
    data: dict[str, Any],
    path: Path,
    mode: str,
    frontmatter: dict[str, Any],
    pre_diags: list[_Diag],
) -> _PhaseModelT:
    """Run one phase file's frontmatter schema validation, merged with any
    body-structure diagnostics the caller already collected for the SAME
    file (``pre_diags``) — so neither kind of defect hides the other (F6).
    """
    try:
        validated = model_cls.model_validate(data)
    except ValidationError as exc:
        _raise_diags(pre_diags + _phase_validation_diags(path, mode, frontmatter, exc))
    if pre_diags:
        _raise_diags(pre_diags)
    return validated


def _phase_validation_diags(
    path: Path,
    mode: str,
    frontmatter: dict[str, Any],
    exc: ValidationError,
) -> list[_Diag]:
    diags: list[_Diag] = []
    domain = {"agent": "agent", "logic": "logic", "subgraph": "subgraph"}.get(mode, "graph")
    for error in exc.errors():
        loc = error.get("loc", ())
        msg = error.get("msg", "")
        type_ = error.get("type", "")

        line = _frontmatter_loc_line(path, frontmatter, loc)
        field_path = _field_path_from_loc(loc)

        code = None
        clean_msg = msg

        if loc == ("io",):
            code = f"[F-v3-{domain}-io-schema-invalid]"
        elif mode == "subgraph" and loc == ("name",):
            code = "[F-v3-subgraph-name-invalid]"
        elif type_ == "missing":
            if loc == ("role",):
                code = "[F-v3-agent-role-missing]"
            elif loc == ("goal",):
                code = "[F-v3-agent-goal-missing]"

        if code is None and mode == "logic" and any(isinstance(seg, str) and "validator" in seg for seg in loc):
            code = "[F-v3-logic-validator-type-invalid]"
            clean_msg = "validator must be boolean"

        if code is None:
            match = re.search(r"\[(F-v3-[a-z0-9-]+)\]", msg)
            if match:
                code = f"[{match.group(1)}]"
                # Strip pydantic's "Value error, " wrapper BEFORE removing the
                # code substring. The code sits between a leading and a
                # trailing space in the raw message, so removing it first
                # leaves two adjacent spaces; the fixed-length prefix strip
                # then only eats 13 of them, leaving clean_msg starting with
                # a stray space (real symptom: the message column in the
                # compile drawer showed " max_iterations must be...").
                clean_msg = msg
                if clean_msg.startswith("Value error, "):
                    clean_msg = clean_msg[len("Value error, ") :]
                clean_msg = clean_msg.replace(code, "").strip()

        if code is None:
            code = f"[F-v3-{domain}-schema-unknown-field]"

        diags.append(
            _Diag(
                path=path,
                line=line,
                code=code,
                message=clean_msg,
                field_path=field_path,
            )
        )

    return diags


def _extract_logic_actions_collecting(path: Path, body: str) -> tuple[list[str], list[_Diag]]:
    """Like ``_extract_logic_actions`` but collects defects instead of
    raising, so a body-structure defect (empty/absent ``<action>``) can be
    merged with an independent frontmatter schema defect from the SAME file
    into one compile report (F6 aggregation completeness) instead of
    aborting before the schema ever gets checked.
    """
    actions: list[str] = []
    diags: list[_Diag] = []
    pattern = re.compile(r"<action\b[^>]*>(.*?)</action>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(body):
        action = match.group(1).strip()
        if not action:
            # Mirror the agent's strict role/goal check: an empty <action></action>
            # is itself a defect even when other actions are filled.
            diags.append(
                _make_diag(
                    path,
                    _body_file_line(path, body, match.start()),
                    "[F-v3-logic-actions-empty] LOGIC.md <action> tags must not be empty",
                )
            )
            continue
        actions.append(action)
    if not actions:
        diags.append(
            _make_diag(
                path,
                _body_file_line(path, body, 0),
                "[F-v3-logic-actions-empty] LOGIC.md requires <action> tags",
            )
        )
    return actions, diags


def _extract_logic_actions(path: Path, body: str) -> list[str]:
    actions, diags = _extract_logic_actions_collecting(path, body)
    if diags:
        _raise_diags(diags)
    return actions


def _validate_logic_actions_declared(path: Path, ast: LogicNodeAST, body: str) -> None:
    body_actions = _extract_logic_actions(path, body)
    if ast.actions != body_actions:
        _fatal(
            path,
            _frontmatter_key_line(path, "actions"),
            "[F-v3-logic-actions-empty] LOGIC.md frontmatter actions must match body <action> order",
        )


def _parse_agent_body(
    path: Path,
    body: str,
    blocks: dict[str, str],
) -> tuple[dict[str, Any], list[_Diag]]:
    """Extract Agent body fields, collecting (not raising) role/goal-missing
    defects so the caller (``_build_phase_document``) can merge them with any
    frontmatter schema defect from the SAME file into one compile report
    (F6 aggregation completeness) instead of aborting before the schema is
    ever checked.

    Genuinely unreadable markup (unknown top-level tag, the deprecated steps
    wrapper tag, ``<exit_contract>``) still aborts immediately: unlike a
    missing block, a malformed tag soup gives ``extract_raw_blocks`` no
    reliable body to keep parsing from.
    """
    allowed_tags = {"role", "goal", "step", "protocol", "example"}
    for match in re.finditer(r"</?([A-Za-z_][\w:-]*)\b", body):
        tag = match.group(1).lower()
        if tag not in allowed_tags:
            _fatal(
                path,
                _body_file_line(path, body, match.start()),
                f"[F-v3-agent-body-tag-unknown] unknown top-level tag {tag}",
            )
    if "<steps" in body.lower() or "</steps" in body.lower():
        _fatal(
            path,
            _body_file_line(path, body, body.lower().find("<steps")),
            "[F-v3-agent-body-tag-unknown] unknown top-level tag steps",
        )
    role = blocks.get("role")
    goal = blocks.get("goal")
    if "<exit_contract" in body.lower() or "</exit_contract" in body.lower():
        _fatal(
            path,
            _body_file_line(path, body, body.lower().find("<exit_contract")),
            "[F-v3-agent-body-tag-unknown] unknown top-level tag exit_contract",
        )
    # Role and goal are independent presence checks: collect both so a single
    # compile reports them together rather than aborting after role.
    block_diags: list[_Diag] = []
    if not role:
        block_diags.append(
            _make_diag(
                path,
                _missing_block_line(path, body, "role"),
                "[F-v3-agent-role-missing] Agent body requires <role>",
            )
        )
        # AgentNodeAST.role has its own min_length=1 check; feed it a
        # placeholder so it does not ALSO flag the same defect under a
        # generic code. The placeholder never reaches a caller: a non-empty
        # block_diags always ends this phase file's compile in a raise
        # (see _validate_phase_ast).
        role = "(missing role)"
    if not goal:
        block_diags.append(
            _make_diag(
                path,
                _missing_block_line(path, body, "goal"),
                "[F-v3-agent-goal-missing] Agent body requires <goal>",
            )
        )
        goal = "(missing goal)"
    return {
        "role": role,
        "goal": goal,
        "steps": _extract_agent_steps(path, body),
        "protocols": _extract_agent_protocols(path, body),
        "examples_inline": _extract_agent_examples(path, body),
    }, block_diags


def _extract_agent_steps(path: Path, body: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    pattern = re.compile(r"<step\b([^>]*)>(.*?)</step>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(body):
        attrs = _parse_attrs(match.group(1))
        step_id = attrs.get("id")
        name = attrs.get("name")
        if not step_id or not name:
            _fatal(
                path,
                _body_file_line(path, body, match.start()),
                "[F-v3-agent-step-invalid] step requires id and name",
            )
        steps.append({"id": step_id, "name": name, "content": match.group(2).strip()})
    return steps


def _extract_agent_protocols(path: Path, body: str) -> list[dict[str, str]]:
    protocols: list[dict[str, str]] = []
    pattern = re.compile(r"<protocol\b([^>]*)>(.*?)</protocol>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(body):
        attrs = _parse_attrs(match.group(1))
        protocol_id = attrs.get("id")
        if not protocol_id:
            _fatal(
                path,
                _body_file_line(path, body, match.start()),
                "[F-v3-agent-protocol-invalid] protocol requires id",
            )
        protocols.append({"id": protocol_id, "content": match.group(2).strip()})
    return protocols


def _extract_agent_examples(path: Path, body: str) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"<example\b([^>]*)>(.*?)</example>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(body):
        attrs = _parse_attrs(match.group(1))
        example_id = attrs.get("id")
        content = match.group(2).strip()
        if not example_id or not content or example_id in seen:
            _fatal(
                path,
                _body_file_line(path, body, match.start()),
                "[F-v3-agent-example-invalid] example requires unique id and non-empty content",
            )
        seen.add(example_id)
        examples.append({"id": example_id, "content": content})
    return examples


def _validate_agent_mentions(path: Path, ast: AgentNodeAST, body: str) -> None:
    broken = first_broken_mention(body)
    if broken is not None:
        _fatal(
            path,
            _body_file_line(path, body, broken.start()),
            "[F-v3-mention-syntax-invalid] malformed @-mention",
        )
    domains = {
        "subagent": {item.name for item in ast.subagents},
        "subgraph": {item.name for item in ast.subgraphs},
        "reference": {item.id for item in ast.references},
        "example": {item.id for item in ast.examples} | {item.id for item in ast.examples_inline},
        "step": {item.id for item in ast.steps},
        "protocol": {item.id for item in ast.protocols},
        "tool": set(ast.tools) | {"finish_task", "read_reference", "read_example", "log_ambiguity"},
    }
    for mention in scan_mentions(body):
        if mention.name not in domains.get(mention.kind, set()):
            _fatal(
                path,
                _body_file_line(path, body, mention.start),
                f"[F-v3-mention-target-not-found] @{mention.kind}:{mention.name}",
            )


def _xml_line(body: str, offset: int) -> int:
    return body[: max(0, offset)].count("\n") + 1


def _body_file_line(path: Path, body: str, offset: int) -> int:
    """Map a 0-based offset into the frontmatter-stripped ``body`` to a 1-based
    FILE line.

    Body diagnostics must share the file-absolute axis that frontmatter errors
    use (``_frontmatter_key_line`` / ``locate_line_for_pydantic_loc``): the editor
    marks the whole file (frontmatter included) and Studio forwards the engine's
    line verbatim, so a body-relative ``_xml_line`` value would land too high by
    the frontmatter length. ``body`` is a suffix of the file content (parser
    ``_strip_frontmatter`` removes the frontmatter), so its start anchors exactly.
    """
    try:
        content = read_authored_text(path)
    except OSError:
        return _xml_line(body, offset)
    if body:
        body_index = content.rfind(body)
        if body_index >= 0:
            return content[: body_index + max(0, offset)].count("\n") + 1
    # Empty / unlocatable body: fall back to the first line after the frontmatter.
    match = re.match(r"^---\r?\n.*?\r?\n---", content, re.DOTALL)
    if match:
        return content[: match.end()].count("\n") + 2
    return _xml_line(body, offset)


def _missing_block_line(path: Path, body: str, tag: str) -> int:
    """File line for a required-but-absent/empty agent block.

    When the ``<tag>`` exists (e.g. an empty ``<role></role>``) point at the tag;
    when it is missing entirely point at the body start, never the hardcoded
    line 1 (which lands on the frontmatter ``---``).
    """
    index = body.lower().find(f"<{tag}")
    return _body_file_line(path, body, index if index >= 0 else 0)


_ATTR_RE = re.compile(r"([A-Za-z_][\w:-]*)\s*=\s*(['\"])(.*?)\2", re.DOTALL)


def _parse_attrs(raw: str) -> dict[str, str]:
    return {match.group(1): match.group(3) for match in _ATTR_RE.finditer(raw)}


def _phase_ancestor_sets(
    phase_refs: list[PhaseTopologyRef],
) -> dict[str, set[str]]:
    """Transitive dependency closure per phase (excluding the 'input' pseudo-node)."""
    depends_on_map = {ref.name: list(ref.depends_on) for ref in phase_refs}

    def get_ancestors(phase_name: str) -> set[str]:
        ancestors: set[str] = set()
        queue = list(depends_on_map.get(phase_name, []))
        while queue:
            curr = queue.pop(0)
            if curr != "input" and curr not in ancestors:
                ancestors.add(curr)
                queue.extend(depends_on_map.get(curr, []))
        return ancestors

    return {ref.name: get_ancestors(ref.name) for ref in phase_refs}


def _phase_declared_output_keys(phase_docs: list[PhaseDocument]) -> dict[str, set[str]]:
    phase_output_keys: dict[str, set[str]] = {}
    for doc in phase_docs:
        keys = set()
        if doc.ast and doc.ast.io and doc.ast.io.outputs:
            props = doc.ast.io.outputs.get("properties", {})
            if isinstance(props, dict):
                keys = {k for k in props if isinstance(k, str)}
        phase_output_keys[doc.phase_name] = keys
    return phase_output_keys


def _validate_parallel_writers(
    graph_path: Path,
    phase_refs: list[PhaseTopologyRef],
    phase_docs: list[PhaseDocument],
    diags: list[_Diag],
) -> None:
    """Reject two dependency-independent phases declaring the same output field.

    Phases with no dependency path between them can execute in the same
    superstep; both writing one business field would race on the reducer
    channel with nondeterministic last-writer-wins. The illegal state is made
    unrepresentable at compile time instead (parallel-fanout decision,
    2026-08-15).
    """
    ancestor_sets = _phase_ancestor_sets(phase_refs)
    phase_output_keys = _phase_declared_output_keys(phase_docs)
    docs_by_name = {doc.phase_name: doc for doc in phase_docs}
    names = [ref.name for ref in phase_refs]

    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if first in ancestor_sets.get(second, set()):
                continue
            if second in ancestor_sets.get(first, set()):
                continue
            overlap = phase_output_keys.get(first, set()) & phase_output_keys.get(
                second, set()
            )
            report_doc = docs_by_name.get(second) or docs_by_name.get(first)
            if report_doc is None:
                continue
            for key in sorted(overlap):
                detail = (
                    f"Phases '{first}' and '{second}' have no dependency path between "
                    f"them (they may run in parallel) but both declare output field "
                    f"'{key}'. Parallel writers of one field race nondeterministically; "
                    f"give the field a single owner or order the phases with depends_on."
                )
                diags.append(
                    _Diag(
                        path=report_doc.path,
                        line=1,
                        code="[F-v3-parallel-write-conflict]",
                        message=detail,
                        field_path=f"io.outputs.properties.{key}",
                    )
                )


def _validate_sequential_overwrites(
    graph_path: Path,
    phase_refs: list[PhaseTopologyRef],
    phase_docs: list[PhaseDocument],
    diags: list[_Diag],
) -> None:
    ancestor_sets = _phase_ancestor_sets(phase_refs)
    phase_output_keys = _phase_declared_output_keys(phase_docs)

    for doc in phase_docs:
        phase_name = doc.phase_name
        current_outputs = phase_output_keys.get(phase_name, set())
        if not current_outputs:
            continue

        ancestors = ancestor_sets.get(phase_name, set())
        allowed_overwrites = set(getattr(doc.ast, "allow_sequential_overwrite", []) or [])

        for ancestor_name in ancestors:
            ancestor_outputs = phase_output_keys.get(ancestor_name, set())
            overlap = current_outputs & ancestor_outputs
            if overlap:
                for key in overlap:
                    if key not in allowed_overwrites:
                        detail = (
                            f"Phase '{phase_name}' sequentially overwrites field '{key}' "
                            f"outputted by upstream phase '{ancestor_name}'. "
                            f"Declare '{key}' in allow_sequential_overwrite in {doc.path.name} to allow this."
                        )
                        diags.append(
                            _Diag(
                                path=doc.path,
                                line=1,
                                code="[F-v3-sequential-overwrite-unauthorized]",
                                message=detail,
                                # The subject is the colliding field, not the key that
                                # authorizes it — same locator its sibling rule
                                # [F-v3-parallel-write-conflict] uses for the same
                                # "one field, two writers" family.
                                field_path=f"io.outputs.properties.{key}",
                                conflicting_phase=ancestor_name,
                            )
                        )


def _frontmatter_key_line(path: Path, key: str) -> int:
    try:
        for index, line in enumerate(read_authored_text(path).splitlines(), start=1):
            if re.match(rf"\s*{re.escape(key)}\s*:", line):
                return index
    except OSError:
        return 1
    return 1


__all__ = [
    "CompiledSkill",
    "PhaseDocument",
    "PhaseTokenInfo",
    "SkillLoader",
    "build_phase_document",
    "get_phase_token_info",
]
