---
doc: graph-skill-runtime-index
role: index
status: living
updated: 2026-08-27
---

# Standalone Design Documentation

This directory routes current Graph Skill Runtime facts, historical evidence, and the still-drafted complete v1 target. Phase 1 implemented the standalone identity and typed runtime boundary. Phase 2 implemented the portable file format, flat graph registry, and explicit legacy converter. Phase 3 implements durable cooperative host-native handoff for explicitly serializable Agent wait points in a root DAG. Phase 4 implements capability-probed direct vendor CLI execution over that same bounded wait-point contract. Phase 3b host-native expansion, Phase 5 installation, and Phase 6 cross-platform release acceptance remain drafted.

## Authority map

| Question | Authoritative source | Current status and use |
| --- | --- | --- |
| What distribution, import, command, and SDK can this checkout use? | [Repository README](../../README.md), [`pyproject.toml`](../../pyproject.toml), and [`graph_skill_runtime.__all__`](../../src/graph_skill_runtime/__init__.py) | Phase 1 current: `graph-skill-runtime` `0.1.0a1`, `graph_skill_runtime`, and `gskill`; not published on PyPI |
| What are the exact public Python symbols and typed contracts? | [Public API contract](../public-api-contract.md) plus [`domain/models.py`](../../src/graph_skill_runtime/domain/models.py) | Current: 59 top-level symbols; closed, frozen, versioned models; 44 closed runtime event discriminators |
| Which service owns SDK, CLI, and MCP use-case behavior? | [`RuntimeApplication`](../../src/graph_skill_runtime/application/service.py), [`sdk.py`](../../src/graph_skill_runtime/sdk.py), and [`adapters`](../../src/graph_skill_runtime/adapters) | Current: one application service; eight same-named SDK and MCP use cases, including durable host-native result submission |
| How is current configuration resolved and snapshotted? | [`application/config.py`](../../src/graph_skill_runtime/application/config.py) and [`adapters/snapshots.py`](../../src/graph_skill_runtime/adapters/snapshots.py) | Phase 1 current: invocation > project > user > portable > built-in, with immutable provenance and create-once snapshots |
| What skill files does the current implementation accept? | [Portable gSkill v1 format contract](../skill-spec/01-PORTABLE-GSKILL-V1.md) | Phase 2 current: root `SKILL.md` and `graph.yaml`; phase `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`; one flat `graphs/<graph_id>/` registry |
| What does the explicit legacy converter accept? | [Superseded v0.3 format](../skill-spec/00-FORMAT-GROUND-TRUTH.md) and [portable migration contract](../skill-spec/01-PORTABLE-GSKILL-V1.md) | Converter input and historical evidence only; production compile/run does not read or fall back to v0.3 |
| Where is the current error-code catalog? | [Error-code specification](../skill-spec/11-error-code-spec.md) | `living` unique catalog kept in bijection with `ERROR_REGISTRY`; other documents link rather than copy the table |
| Where are current extracted-engine responsibilities indexed? | [MVP1 documentation index](../mvp1/INDEX.md) | Current design line for the engine behind `CurrentEngineAdapter` |
| Which features own sources, events, errors, and tests? | [`spec/features.yaml`](../../spec/features.yaml) and the [generated compliance view](../feature-compliance-checklist.md) | The manifest is the mutable SSOT; the root checklist is its FROZEN generated view |
| What source facts motivated the standalone design? | [`baseline.md`](./baseline.md) | Historical pre-extraction evidence at `origin/main@3564b49e`; not a current directory map |
| What should the complete standalone v1 become? | [`v1-alignment.md`](./v1-alignment.md) | Overall status remains `drafted`; its implementation-status section distinguishes completed Phase 0/1/2, bounded Phase 3, and Phase 4 from the remaining Phase 3b/5/6 targets |
| What platform rules apply? | [Cross-platform policy](../CROSS_PLATFORM.md) | Current Windows, macOS, and Linux engineering policy, process-tree design, and verified-versus-configured evidence boundary |

## Current Phase 1 through Phase 4 line

The standalone naming cutover is complete in source and package metadata. Public callers use the typed `graph_skill_runtime` facade, not the extracted engine's former top-level ABI. The `gskill` CLI and MCP server are transport adapters over the same `RuntimeApplication`, and `create_application` composes replaceable engine and snapshot ports without a singleton.

The current reader accepts only the portable contract in [`01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md). A business gSkill is always supplied by path and remains user-owned; installing or importing the runtime does not register, discover globally, copy, or mutate it. The root `SKILL.md` is the sole Agent Skills discovery target, while `graph.yaml` owns machine topology and root-only artifact declarations. Reusable graphs live in one flat `graphs/<graph_id>/` registry.

Legacy v0.3 parsing is isolated behind `gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]`. The converter does not modify source or overwrite an existing destination. Production compile, predict, run, inspect, SDK, CLI, and MCP paths neither sniff formats nor fall back after a portable-format failure.

The default executor is `host-native`. A root graph without an Agent phase runs directly. For a supported root-DAG Agent wait point, the runtime first persists a LangGraph SQLite checkpoint, then persists a provider-neutral `AgentTask` in a separate handoff database, and only then returns `RunResult(status="agent_required")`. The host creates a fresh clean-context native subagent and submits the typed result through the Python SDK, MCP, or `gskill submit`; the runtime validates and applies that result to the same graph run. `resume(checkpoint_ref)` is a read-only view of the durable wait or terminal response, not a result-submission shortcut.

The current Phase 3 address is deliberately narrow: Agent phases in registry subgraphs, graph-level or phase-level iterate, and incomparable parallel branches fail fast. Host-native Agent handoff requires SQLite checkpoint storage. Ordinary human/breakpoint resume and host-native lifecycle acknowledgment remain Phase 3b work. Explicit `embedded` execution still reaches the extracted engine.

Explicit `cli` execution now uses the same durable Agent task/result transition through one fresh vendor process per task. Claude, Codex, GitHub Copilot, Cursor, Gemini, and OpenCode protocol adapters probe their executable, version, required flags, and any exposed authentication state before handoff creation. Pure `LOGIC` graphs do not construct or probe a vendor executor. The path rejects unbridged portable tools, subagents, subgraphs, and framework context access; it never silently chooses `embedded`. `agent_dispatched` records a built immutable CLI attempt, `agent_started` records the owned process-tree root, and a successful `agent_completed` shares their `attempt_id`. A post-dispatch execution failure emits non-terminal `agent_failed` evidence and leaves the durable task retryable.

POSIX process groups remain the primary process-tree owner. Hosted Darwin established that group-wide `killpg` can return `EPERM`; the current narrow fallback enumerates bounded `ps` output and individually signals only exact-PGID members owned by the runtime effective UID. It does not broaden cleanup into a guessed descendant tree.

All six adapters have fake-process contract coverage, but only Codex CLI `0.144.1` on Windows `10.0.26200` x64 with Python `3.11.15` has a successful real operational smoke. Claude Code `2.1.222` passed executable/version/help probes there but lacked authentication; the other four CLIs were absent. On the same Phase 4 commit, [GitHub Actions run 33140732333](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33140732333) passed quality gates, Python 3.11/3.12/3.13 runtime tests, and Windows/macOS cross-platform smoke; CodeQL and Analyze Python passed as well. This is source-checkout platform evidence, not real macOS/Linux vendor execution or Phase 6 packaged install/release acceptance.

## Drafted Phase 3b, Phase 5, and Phase 6 line

Phase 3b expands host-native wait-point addressing, standalone human/breakpoint typed resume, and host acknowledgment or capability negotiation. MoirAI canonical assets and installer are Phase 5. Cross-platform packaging and release acceptance are Phase 6. These targets remain authoritative design direction in `v1-alignment.md`, but they are not current capabilities. Gateway and Studio plugins are outside this release line; the design retains only the ownership rule that any future integration uses public Port/Adapter boundaries and does not move product-specific truth into runtime core.

## Publication and cutover rules

The GitHub repository exists and uses pull-request-only protection. The distribution name is present in local package metadata, but the project has not been published to PyPI. [The release workflow](../../.github/workflows/release.yml) separates build and publish jobs, checks a GitHub Release tag against the package version, validates wheel contents, and is wired for PyPI Trusted Publishing through OIDC. The owner still has to configure the PyPI project and trusted publisher; workflow presence is not registry or release evidence.

Each future contract cutover replaces its predecessor only after implementation, regeneration or conversion, cross-platform verification, contract-map updates, examples, and documentation are complete together. The Phase 2 source cutover follows this atomic shape: one production reader plus one explicit converter boundary, with the old format retained only as `superseded` evidence. Do not add a dual reader, legacy alias, deprecated field, or version-guessing fallback. Historical evidence stays historical; current facts move to the current owner.

## Status vocabulary

- **Current fact**: directly observable in this checkout's code, package metadata, tests, current contract documents, or recorded repository settings.
- **Drafted target**: an accepted direction whose remaining implementation and causal evidence are incomplete.
- **Recommendation**: an implementation option that still requires a design decision or acceptance evidence.
- **Open question**: a decision lacking evidence or an owner ruling and therefore not usable as a default.
