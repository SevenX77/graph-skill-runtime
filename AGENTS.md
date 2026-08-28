# Graph Skill Runtime Project Rules

This file is the canonical project-rule entry for contributors and coding agents working in this repository. Read it before planning or changing code, tests, specifications, CI, dependencies, or authoritative documentation.

## 1. Current implementation and sources of truth

The current checkout contains the implemented Phase 1 typed runtime foundation, the Phase 2 portable gSkill format cutover, the Phase 3 durable host-native handoff subset for explicitly serializable Agent wait points in a root DAG, and the Phase 4 direct vendor CLI executor.

- The distribution is `graph-skill-runtime` version `0.1.0a1`.
- The Python import is `graph_skill_runtime`.
- The console command is `gskill`.
- The top-level typed contract contains exactly the symbols in [`graph_skill_runtime.__all__`](src/graph_skill_runtime/__init__.py); [`docs/public-api-contract.md`](docs/public-api-contract.md) documents that executable set.
- SDK, CLI, and MCP calls converge on [`RuntimeApplication`](src/graph_skill_runtime/application/service.py). [`create_application`](src/graph_skill_runtime/composition.py) is the explicit composition root; there is no global application singleton.
- [`spec/features.yaml`](spec/features.yaml), [`spec/source_file_map.yaml`](spec/source_file_map.yaml), and [`spec/contract_map.yaml`](spec/contract_map.yaml) own feature, source, event, error-code, and public-contract traceability.

The current skill-file contract is the portable format in [`docs/skill-spec/01-PORTABLE-GSKILL-V1.md`](docs/skill-spec/01-PORTABLE-GSKILL-V1.md). Callers provide one explicit business skill root containing the Agent Skills discovery entry `SKILL.md`, the machine topology `graph.yaml`, and phase directories whose type file is exactly one of `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`. Reusable graphs form one flat `graphs/<graph_id>/graph.yaml` registry; graph ids are explicit and bundle-wide unique. Only the root `SKILL.md` is an Agent Skills discovery target. The former v0.3 contract in [`docs/skill-spec/00-FORMAT-GROUND-TRUTH.md`](docs/skill-spec/00-FORMAT-GROUND-TRUTH.md) is `superseded` and remains only as converter input and historical evidence.

[`docs/design/v1-alignment.md`](docs/design/v1-alignment.md) remains `drafted` because the complete v1 design is not implemented. Its Section 2 naming, Phase 1 typed facade/configuration/SDK-CLI-MCP boundary, Phase 2 portable format, bounded Phase 3 host-native handoff, and Phase 4 direct vendor CLI executor are implemented. Phase 3b still owns richer host-native wait-point shapes, standalone human/breakpoint resume, and host acknowledgment. Phase 5 owns the MoirAI installer, and Phase 6 owns cross-platform package/release acceptance. Gateway and Studio plugins are not deliverables in this release line; the design retains only their future Port/Adapter ownership boundaries. [`docs/design/README.md`](docs/design/README.md) routes current facts versus drafted targets. [`docs/design/baseline.md`](docs/design/baseline.md) is historical pre-extraction evidence, not a current path map.

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

## 3. Execution and handoff semantics

Configuration precedence is fixed, from highest to lowest: invocation, project `<skill_root>/gskill.toml`, operating-system user config, portable defaults, and built-in defaults. User config contains only a machine `RuntimeProfile`; named `RunPreset` values come only from project or explicitly supplied portable defaults. `RuntimeProfile` contains executor, checkpoint store, state directory, permissions, capabilities, and fallback declarations. Business inputs and run controls belong to `RunPreset`, `RunInvocation`, and the resolved `RunRequest`.

Resolved requests contain absolute skill and state roots plus field-level provenance. Public Pydantic contracts are closed and frozen, and nested JSON dicts and lists remain immutable after construction. Literal values under structurally secret-shaped keys are rejected; secret values are represented only through `SecretReference` and `SecretBinding`. A runtime cannot infer whether every arbitrary business string is secret, so callers must classify values that do not have secret-shaped keys.

The default executor is `host-native`. Every run first persists the immutable request snapshot. The local snapshot owner writes `<state_root>/runs/<run_id>/request.json` with create-if-absent semantics: identical content is idempotent and different content must never overwrite the existing run id.

For a supported root-DAG `AGENT` phase, host-native execution durably pauses the graph in the LangGraph SQLite checkpoint store before persisting the public `AgentTask` in `<state_root>/agent-handoffs.sqlite3`. It then returns `RunResult(status="agent_required")` with a public `gskill-handoff-v1:<task-id>` reference. The host, not the runtime, creates a fresh clean-context native subagent and submits its `AgentResult` through the Python SDK, MCP, or `gskill submit`. The runtime validates task identity and output JSON Schema, applies one external phase completion to the same graph state, and continues the same run. It does not invoke a model or silently select `embedded` or `cli` on this path. A host-native graph with no Agent phases runs directly to completion.

Current host-native Agent handoff requires `SqliteCheckpointStoreConfig`. Registry-subgraph Agent phases, graph-level iterate containing Agent, Agent phase iterate, and Agent phases on incomparable parallel branches fail before execution instead of falling back. `resume(checkpoint_ref)` only reads the durable current wait or terminal response; Agent output advances the graph only through `submit_agent_result`. Standalone typed human/breakpoint resume is not complete. Exact duplicate submissions return the cached causal `RunResult`; a different result conflicts, and invalid schema output does not consume the task.

The extracted engine also runs when the resolved primary executor is explicitly `embedded`. Provider clients remain isolated in the optional `embedded` dependency extra. The current adapter has verified a real portable-format `LOGIC` skill compile/run path; do not describe provider-backed embedded Agent execution as generally complete from that evidence.

An explicit `executor=cli` selects `CliRuntimeAdapter`; the default remains `host-native`, and fallback declarations are never silently selected. A `LOGIC`-only graph completes without constructing or probing a vendor executor even under a CLI profile. An Agent graph must still satisfy the Phase 3 root-DAG, serial wait-point restrictions. Before creating a durable handoff, the CLI path probes the selected executable, version, required flags, and any authentication status the vendor exposes, and it rejects portable Agent tools, subagents, subgraphs, or framework context access because those capabilities are not bridged in Phase 4.

Six direct protocol adapters ship: Claude, Codex, GitHub Copilot, Cursor, Gemini, and OpenCode. Every Agent task uses a new process and temporary working directory without a resume, continue, or session id. This is a fresh vendor-native top-level session, not a native child of the current host conversation and not a promise of blank vendor user configuration. Claude and Codex explicitly disable session persistence; Copilot, Cursor, Gemini, and OpenCode report `session_persistence=vendor-default`. Claude, Codex, and Cursor have CLI-exposed auth probes; the other three report `auth_probe=not-exposed` and surface login failure from a structured nonzero execution result.

`CliExecutorConfig` owns `vendor`, optional `agent_profile`, optional `model_override`, optional `executable`, and `timeout_seconds`. Agent profiles are valid only for Copilot, Gemini, and OpenCode: Copilot/OpenCode use direct `--agent`, while Gemini asks its main CLI agent to broker `@<name>`. A configured executable is a PATH basename or absolute path; relative paths containing a separator fail fast. The timeout defaults to 600 seconds and is bounded to `(0, 86400]`.

`AgentTask.resources` carries public `AgentResource` values. Host-native tasks keep absolute paths structurally for the host, while rendered instructions list only resource handles and summaries. The CLI materializer reads a declared resource only when its resolved file is within `allowed_paths`, then inlines the handle, summary, and content without the original path. On the CLI path, `allowed_paths` governs runtime materialization; it is not a cross-vendor filesystem sandbox. The complete business prompt never enters argv, output is always runtime-validated against Draft 2020-12 JSON Schema, byte limits apply to resources, prompts, schemas, process output, and bounded output files, and unsafe rejected output is represented only by its SHA-256.

The process Port is shell-free, uses an explicit temporary cwd, a minimal allowlisted environment, UTF-8, cancellation and deadlines, and bounded temporary-file capture. Windows launches a stdin-blocked Python supervisor, assigns that process-tree root to a `KILL_ON_JOB_CLOSE` Win32 Job Object, and only then sends vendor argv; assignment failure closes the attempt rather than degrading to direct-child cleanup. POSIX uses `start_new_session` and group-wide `SIGTERM` then `SIGKILL` as the primary owner. If `killpg` raises `PermissionError`, the adapter runs only `/bin/ps` or `/usr/bin/ps` under a two-second/1-MiB bound, selects only exact-PGID members whose UID equals the runtime effective UID, and signals those PIDs individually; it never broadens cleanup to a guessed tree. Success, failure, timeout, cancellation, and parent exit all clean up lingering descendants. `AgentStartedEvent.process_id` is the owned supervisor/process-tree root PID on Windows and need not be the direct vendor PID.

Adapter existence is distinct from an operational support claim. Current real evidence supports only Codex CLI `0.144.1` on Windows `10.0.26200` x64 with Python `3.11.15`. Claude Code `2.1.222` passed executable/version/help probing on that host but failed the auth probe; Copilot, Cursor, Gemini, and OpenCode were not installed. On commit `8928d13b32c800a2ad303d02e1bd96551f969ab5`, GitHub Actions run `33140732333` passed quality gates, Python 3.11/3.12/3.13 runtime tests, and Windows/macOS cross-platform smoke; CodeQL and Analyze Python also passed. Those jobs execute the source checkout and prove the tested platform contracts, including the macOS SIGTERM-ignoring descendant cleanup case. They do not execute real vendor CLIs, so macOS and Linux direct-CLI operation remains unverified; they also do not complete Phase 6 packaged install/release acceptance. MoirAI installation remains unavailable. Gateway and Studio integrations remain future external Port/Adapter concerns and are outside this release line.

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
