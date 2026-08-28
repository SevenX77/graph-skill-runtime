# Graph Skill Runtime Project Rules

This file is the canonical project-rule entry for contributors and coding agents working in this repository. Read it before planning or changing code, tests, specifications, CI, dependencies, or authoritative documentation.

## 1. Current implementation and sources of truth

The current checkout contains the implemented Phase 1 typed runtime foundation and the Phase 2 portable gSkill format cutover.

- The distribution is `graph-skill-runtime` version `0.1.0a1`.
- The Python import is `graph_skill_runtime`.
- The console command is `gskill`.
- The top-level typed contract contains exactly the symbols in [`graph_skill_runtime.__all__`](src/graph_skill_runtime/__init__.py); [`docs/public-api-contract.md`](docs/public-api-contract.md) documents that executable set.
- SDK, CLI, and MCP calls converge on [`RuntimeApplication`](src/graph_skill_runtime/application/service.py). [`create_application`](src/graph_skill_runtime/composition.py) is the explicit composition root; there is no global application singleton.
- [`spec/features.yaml`](spec/features.yaml), [`spec/source_file_map.yaml`](spec/source_file_map.yaml), and [`spec/contract_map.yaml`](spec/contract_map.yaml) own feature, source, event, error-code, and public-contract traceability.

The current skill-file contract is the portable format in [`docs/skill-spec/01-PORTABLE-GSKILL-V1.md`](docs/skill-spec/01-PORTABLE-GSKILL-V1.md). Callers provide one explicit business skill root containing the Agent Skills discovery entry `SKILL.md`, the machine topology `graph.yaml`, and phase directories whose type file is exactly one of `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`. Reusable graphs form one flat `graphs/<graph_id>/graph.yaml` registry; graph ids are explicit and bundle-wide unique. Only the root `SKILL.md` is an Agent Skills discovery target. The former v0.3 contract in [`docs/skill-spec/00-FORMAT-GROUND-TRUTH.md`](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md) is `superseded` and remains only as converter input and historical evidence.

[`docs/design/v1-alignment.md`](docs/design/v1-alignment.md) remains `drafted` because the complete v1 design is not implemented. Its Section 2 naming, Phase 1 typed facade/configuration/SDK-CLI-MCP boundary, and Phase 2 portable format are implemented. Durable host-native handoff, vendor CLI executors, the MoirAI installer, and Gateway/Studio integrations remain Phase 3 through Phase 6 targets. [`docs/design/README.md`](docs/design/README.md) routes current facts versus drafted targets. [`docs/design/baseline.md`](docs/design/baseline.md) is historical pre-extraction evidence, not a current path map.

The project is not published on PyPI. [`.github/workflows/release.yml`](.github/workflows/release.yml) defines separate build and publish jobs for a published GitHub Release whose tag equals `v<pyproject version>`; it validates the built wheel and uses PyPI Trusted Publishing through OpenID Connect (OIDC). The workflow is only prepared automation. The owner must configure the PyPI project and trusted publisher before the first release, and repository metadata, workflow presence, or a successful local build does not prove registry publication.

## 2. Runtime boundary

This repository is a Python runtime and SDK. It owns compilation, typed dataflow, prediction and execution, request snapshots, checkpoint-domain contracts, events and traces, artifacts, inspection, golden evaluation, local skill resolution, and structured runtime errors.

The application boundary is organized as follows:

- [`domain/models.py`](src/graph_skill_runtime/domain/models.py) owns closed, frozen, versioned public data contracts;
- [`application/config.py`](src/graph_skill_runtime/application/config.py) owns configuration precedence and provenance;
- [`application/service.py`](src/graph_skill_runtime/application/service.py) owns use-case ordering;
- [`ports/runtime.py`](src/graph_skill_runtime/ports/runtime.py) owns provider-neutral protocols;
- [`adapters`](src/graph_skill_runtime/adapters) owns engine, local persistence, CLI, and MCP translation;
- [`sdk.py`](src/graph_skill_runtime/sdk.py) is the thin Python facade.

Core and application code must not import Studio or Gateway modules. Studio UI, native filesystem behavior, HTTP routes, Gateway credential and route truth, host session state, vendor processes, operating-system integration, and network behavior belong behind explicit adapters or integrations.

A business gSkill is a user-owned asset. A runtime wheel may contain runtime implementation resources, but it must not bundle, register, discover globally, copy, or mutate user business skills. Callers provide the skill path explicitly.

Keep pure computation separate from I/O and state mutation. Important state and side effects have one owner. Validate external inputs at the boundary, make invalid states unrepresentable where practical, and return complete structured diagnostics rather than hiding bad state with fallback behavior.

## 3. Phase 1 execution semantics

Configuration precedence is fixed, from highest to lowest: invocation, project `<skill_root>/gskill.toml`, operating-system user config, portable defaults, and built-in defaults. User config contains only a machine `RuntimeProfile`; named `RunPreset` values come only from project or explicitly supplied portable defaults. `RuntimeProfile` contains executor, checkpoint store, state directory, permissions, capabilities, and fallback declarations. Business inputs and run controls belong to `RunPreset`, `RunInvocation`, and the resolved `RunRequest`.

Resolved requests contain absolute skill and state roots plus field-level provenance. Public Pydantic contracts are closed and frozen, and nested JSON dicts and lists remain immutable after construction. Literal values under structurally secret-shaped keys are rejected; secret values are represented only through `SecretReference` and `SecretBinding`. A runtime cannot infer whether every arbitrary business string is secret, so callers must classify values that do not have secret-shaped keys.

The default executor is `host-native`. Phase 1 has no host-native handoff implementation, so `run` must first persist the request snapshot and then return `GSKILL_EXECUTOR_UNAVAILABLE`. The local snapshot owner writes `<state_root>/runs/<run_id>/request.json` with create-if-absent semantics: identical content is idempotent and different content must never overwrite the existing run id.

The extracted engine runs only when the resolved primary executor is explicitly `embedded`. Provider clients remain isolated in the optional `embedded` dependency extra. The current adapter has verified a real portable-format `LOGIC` skill compile/run path. Do not describe agent-provider execution as generally complete from that logic-only evidence.

Typed `resume` and `submit_agent_result` request/result contracts exist, but durable handoff is Phase 3. Their current implementation returns `GSKILL_NOT_IMPLEMENTED`. Fallback executor declarations are preserved in the snapshot; Phase 1 does not silently select them. Host-native, vendor CLI, MoirAI, Gateway, and Studio adapters must not be described as implemented until their own causal tests exist.

## 4. Contract cutovers

This project is pre-release and has no external compatibility commitment. A contract change replaces the previous design once implementation, regeneration or conversion, tests, cross-platform evidence, contract maps, examples, and documentation are ready together.

Do not add permanent compatibility shims, dual-format readers, legacy aliases, deprecated fields, or version-sniffing branches. Phase 2 replaced the v0.3 production reader with the root `SKILL.md` plus `graph.yaml` format in one explicit cutover. Production compile, predict, run, inspect, SDK, CLI, and MCP paths accept only the portable format. Legacy v0.3 parsing is confined to the explicit `gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]` converter boundary; it must never become a fallback after a portable-format failure.

The historical files under [`docs/mvp0`](docs/mvp0) are a frozen archive. Do not update them to describe current behavior. Update the active root documents and manifests instead.

## 5. Repository workflow

`main` is protected and pull-request-only. The repository has completed a green six-job CI run on `main`; ordinary work still follows branch to pull request to squash merge:

1. refresh `main` and create one task branch from it;
2. keep one coherent concern in the branch and pull request;
3. run all required local gates;
4. open a pull request to `main`; do not push ordinary changes directly to `main`;
5. merge only after required checks pass.

Do not commit, push, open a pull request, merge, tag, create or publish a GitHub Release, publish a distribution, configure the PyPI trusted publisher, or change repository settings unless the user or task owner explicitly requests that external state change.

## 6. Python and dependency workflow

This repository is one `uv` package, not a workspace. Run commands from the repository root.

```bash
uv sync --extra dev
```

Change dependency declarations in `pyproject.toml`, then let `uv` update `uv.lock`. Never hand-edit the lockfile. Do not use monorepo commands such as `uv sync --all-packages`.

Provider client packages belong in the `embedded` extra, not base runtime dependencies. New dependencies require a current need and a clear owner. Runtime core must not acquire Studio, Gateway, web-server, UI, host, or provider-specific dependencies merely to simplify an adapter.

## 7. Required local gates

Before proposing a change, run all gates from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build
uv run pip-audit
```

The manifest validator is a separate required gate; a green pytest run does not replace it. Build success must produce both the wheel and source distribution. `pip-audit` checks resolved third-party distributions. Because this project is not published on PyPI, a local-project skip must not be reported as a security audit of this repository's own source.

CI configuration and a past green run do not prove a new change is green. Record the new run's results before claiming that change passed a platform or remote gate.

## 8. Tests and traceability ownership

Executable behavior belongs to the nearest coherent source module; regression evidence belongs to the corresponding test area. A root-cause fix adds or updates a test that fails for the cause, not only an end-to-end symptom. Add an integration test when a changed contract crosses a real module or process boundary.

Tests are evidence, not an alternate product specification. Do not weaken, skip, or delete a test merely to make a change pass. When an intentional current-contract change invalidates a test, update the owning current specification, source, contract manifests, generated compliance view, and tests together.

The files under `spec/` are the traceability source of truth. Every callback event class and every registered error code needs exactly one primary owning feature. Public API headings must match `graph_skill_runtime.__all__` and the contract map. Source and test references must resolve. Do not satisfy the validator with invented, stale, or unrelated references.

[`docs/feature-compliance-checklist.md`](docs/feature-compliance-checklist.md) is the FROZEN generated view of `spec/features.yaml`; change the manifest first, then regenerate the view in manifest order. Do not manually create a parallel feature inventory.

## 9. Cross-platform and text rules

[`docs/CROSS_PLATFORM.md`](docs/CROSS_PLATFORM.md) is the authoritative Windows, macOS, and Linux policy for this runtime.

Repository text is UTF-8 with LF line endings. Human-authored inputs enter through [`read_authored_text`](src/graph_skill_runtime/core/authored_text.py), which accepts a leading UTF-8 byte-order mark through `utf-8-sig`. Runtime-owned text uses explicit `encoding="utf-8"`. Text subprocesses use explicit UTF-8 decoding and replacement behavior. Use `pathlib`, avoid case-only paths, and give Windows and POSIX implementations the same observable timeout, locking, replacement, and failure semantics.

## 10. Safe editing and documentation

Inspect `git status` before editing and preserve changes you do not own. Use `apply_patch` for targeted source and documentation edits. Formatting tools may perform mechanical rewrites when their scope is known. Do not use destructive Git commands, broad recursive deletion, or checkout/reset operations to erase a dirty tree.

Resolve exact paths before moving or deleting files. Never target a repository root, home directory, unresolved environment variable, or broad glob with a destructive command. Keep generated output, caches, coverage data, `.venv`, `dist/`, credentials, machine-local paths, and user business skills out of source edits.

Authoritative documentation must be self-contained. State goals, terms, observable facts, constraints, and acceptance evidence in the document; do not depend on chat history. Define supported behavior positively before listing prohibited misuse. Separate current facts, drafted targets, recommendations, and unresolved questions. Link to the owning source instead of copying parallel versions of a contract.
