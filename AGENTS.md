# Graph Skill Runtime Project Rules

This file is the canonical project rule entry for contributors and coding agents working in this repository. Read it before planning or changing code, tests, specifications, CI, dependencies, or authoritative documentation.

## 1. Contract status and sources of truth

Phase 0 has two deliberately separate contract lines.

### Current implementation line

The code that exists today is the `graph-agent` 0.3.1 distribution, imported as `graph_agent`. Its skill root is `GRAPH.md`; phase files are `LOGIC.md`, `SUBGRAPH.md`, or `SKILL.md` according to phase type.

The current line has these authoritative sources:

- [`pyproject.toml`](pyproject.toml) owns the installed distribution identity, Python requirement, dependencies, and build configuration.
- [`src/graph_agent`](src/graph_agent) owns executable runtime behavior and the `graph_agent` import.
- [`docs/skill-spec/00-FORMAT-GROUND-TRUTH.md`](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md) is the FROZEN current file-format source of truth.
- [`docs/mvp1/INDEX.md`](docs/mvp1/INDEX.md) routes current engine design and module contracts.
- [`spec`](spec) and its validator own feature-to-source, test, event, and error-code traceability.

### Drafted target line

[`docs/design/README.md`](docs/design/README.md) routes the standalone design. [`docs/design/v1-alignment.md`](docs/design/v1-alignment.md) owns the drafted target names and contracts: `graph-skill-runtime`, `graph_skill_runtime`, `gskill`, and the root `SKILL.md` plus `graph.yaml` format. [`docs/design/baseline.md`](docs/design/baseline.md) records the pre-extraction source baseline used to derive that target.

The design directory is not the current runtime or format source of truth. A drafted target must never be described in code, tests, release metadata, or user documentation as an implemented feature.

### Explicit cutover

This project is pre-release and has no external compatibility commitment. A contract change replaces the old design once its implementation, converter or regeneration path, tests, cross-platform evidence, contract maps, examples, and documentation are ready together. The cutover must name the new current source of truth and delete the displaced reader and contract in the same change.

Do not add permanent compatibility shims, dual-format readers, legacy aliases, deprecated fields, or version-sniffing branches. Before cutover, preserve the current FROZEN contract. After cutover, preserve only the newly declared current contract.

## 2. Runtime boundary

This repository is a pure Python runtime and SDK. It compiles and executes user-provided graph skills. It owns compilation, typed dataflow, execution and prediction, checkpoints and resume, events and traces, artifacts, golden evaluation, resolution, and structured runtime errors.

It does not own Studio UI or native filesystem behavior, Studio HTTP routes, Gateway credential or route truth, or a host application's global state. The core package must not import Studio or Gateway modules. Host-, provider-, storage-, process-, operating-system-, and network-specific behavior belongs behind narrow ports and adapters.

A business gSkill is a user-owned asset. A runtime wheel may contain runtime implementation resources, but it must not bundle, register, discover globally, copy, or mutate user business skills. The caller supplies the business skill path explicitly.

Keep pure computation separate from I/O and state mutation. Important state and side effects have one owner. Validate external inputs at the boundary, make invalid states unrepresentable where practical, and return complete structured diagnostics rather than hiding bad state with fallback behavior.

## 3. Repository workflow

The intended repository workflow is branch to pull request to `main`:

1. Refresh `main` and create one task branch from it.
2. Keep one coherent concern in the branch and pull request.
3. Run all required local gates.
4. Open a pull request to `main`; do not directly push ordinary changes to `main`.
5. Merge only after required checks pass, normally as a squash merge.

This is a project policy and a target repository rule. The initial Phase 0 repository has not yet supplied evidence that GitHub branch protection or remote CI has run. Do not claim that `main` is technically protected until the GitHub settings and an actual pull-request run have been verified. Establishing initial remote protection is an owner-controlled bootstrap action, not general authorization for direct pushes.

Do not commit, push, open a pull request, merge, or change repository settings unless the user or task owner explicitly requests that external state change.

## 4. Python and dependency workflow

This repository is one `uv` package, not a workspace. Run commands from the repository root.

```bash
uv sync --extra dev
```

Change dependency declarations in `pyproject.toml`, then let `uv` update `uv.lock`. Never hand-edit the lockfile. Do not use monorepo commands such as `uv sync --all-packages`.

New dependencies require a current need and a clear owner. Runtime core must not acquire Studio, Gateway, web-server, UI, or provider-specific dependencies merely to simplify an adapter. Optional dependencies still require an explicit boundary and tests proving the core import remains independent.

## 5. Required local gates

Before proposing a change, run all gates from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build
uv run pip-audit
```

The manifest validator is a separate required gate; a green pytest run does not replace it. Build success must produce both the wheel and source distribution. `pip-audit` checks resolved third-party distributions; the local `graph-agent` project is skipped when no matching PyPI project exists, and that skip must not be reported as an audit of this repository's own source.

CI configuration currently defines Linux quality gates, tests on Python 3.11/3.12/3.13, and Python 3.12 smoke tests on Windows and macOS. Configuration is not execution evidence. Record actual results before claiming a platform or remote gate is green.

## 6. Test and contract ownership

Executable behavior belongs to the nearest coherent source module; regression evidence belongs to the corresponding test area. A root-cause fix adds or updates a test that fails for the cause, not only an end-to-end symptom. Add an integration test when the changed contract crosses a real module or process boundary.

Tests are evidence, not an alternate product specification. Do not weaken, skip, or delete a test merely to make a change pass. When an intentional current-contract change invalidates a test, update the owning current specification, source, contract manifests, and tests together.

The files under `spec/` are the traceability source of truth. Every callback event class and every registered error code needs exactly one primary owning feature, and source/test references must resolve. Update the manifests when ownership changes; do not satisfy the validator with invented or unrelated references.

Drafted target tests must be clearly scoped to implementation work. Their existence does not authorize changing current `GRAPH.md` behavior before the explicit cutover.

## 7. Cross-platform and text rules

[`docs/CROSS_PLATFORM.md`](docs/CROSS_PLATFORM.md) is the authoritative Windows, macOS, and Linux policy for this runtime.

Repository text is UTF-8 with LF line endings. Human-authored inputs enter through `graph_agent.core.authored_text.read_authored_text`, which uses `utf-8-sig` to remove one leading UTF-8 byte-order mark. Runtime-owned text uses explicit `encoding="utf-8"`. Text subprocesses use explicit UTF-8 decoding and replacement behavior. Use `pathlib`, avoid case-only paths, and give Windows and POSIX implementations the same observable timeout, locking, replacement, and failure semantics.

## 8. Safe editing

Inspect `git status` before editing and preserve changes you do not own. Use `apply_patch` for targeted source and documentation edits. Formatting tools may perform mechanical rewrites when their scope is known. Do not use destructive Git commands, broad recursive deletion, or checkout/reset operations to erase a dirty tree.

Resolve exact paths before moving or deleting files. Never target a repository root, home directory, unresolved environment variable, or broad glob with a destructive command. Prefer recoverable operations and report material deletions.

Keep generated output out of source edits. Do not manually edit build artifacts, caches, coverage output, `.venv`, or `dist/`. Do not add secrets, credentials, machine-local paths, or user business skills to the repository.

## 9. Documentation rules

Authoritative documentation must be self-contained. State the goal, terms, observable facts, constraints, and acceptance evidence in the document; do not rely on chat history or temporary context. Define the supported behavior positively before listing prohibited misuse.

Separate facts, drafted targets, recommendations, and unresolved questions. Use stable relative links to the owning source instead of copying parallel versions of a contract. If the implementation and documentation disagree, first identify which contract line owns the subject; do not rewrite a current source of truth to match a future draft or present historical evidence as a current capability.
