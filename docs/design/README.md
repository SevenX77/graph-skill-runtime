---
doc: graph-skill-runtime-index
role: index
status: living
updated: 2026-08-27
---

# Standalone Design Documentation

This directory routes current Graph Skill Runtime facts, historical evidence, and the still-drafted complete v1 target. Phase 1 implemented the standalone identity and typed runtime boundary. Phase 2 implemented the portable file format, flat graph registry, and explicit legacy converter. Phase 3 and later host, executor, installer, and product integrations remain unimplemented.

## Authority map

| Question | Authoritative source | Current status and use |
| --- | --- | --- |
| What distribution, import, command, and SDK can this checkout use? | [Repository README](../../README.md), [`pyproject.toml`](../../pyproject.toml), and [`graph_skill_runtime.__all__`](../../src/graph_skill_runtime/__init__.py) | Phase 1 current: `graph-skill-runtime` `0.1.0a1`, `graph_skill_runtime`, and `gskill`; not published on PyPI |
| What are the exact public Python symbols and typed contracts? | [Public API contract](../public-api-contract.md) plus [`domain/models.py`](../../src/graph_skill_runtime/domain/models.py) | Phase 1 current: 58 top-level symbols; closed, frozen, versioned models |
| Which service owns SDK, CLI, and MCP use-case behavior? | [`RuntimeApplication`](../../src/graph_skill_runtime/application/service.py), [`sdk.py`](../../src/graph_skill_runtime/sdk.py), and [`adapters`](../../src/graph_skill_runtime/adapters) | Phase 1 current: one application service; eight same-named SDK and MCP use cases |
| How is current configuration resolved and snapshotted? | [`application/config.py`](../../src/graph_skill_runtime/application/config.py) and [`adapters/snapshots.py`](../../src/graph_skill_runtime/adapters/snapshots.py) | Phase 1 current: invocation > project > user > portable > built-in, with immutable provenance and create-once snapshots |
| What skill files does the current implementation accept? | [Portable gSkill v1 format contract](../skill-spec/01-PORTABLE-GSKILL-V1.md) | Phase 2 current: root `SKILL.md` and `graph.yaml`; phase `LOGIC.md`, `AGENT.md`, or `SUBGRAPH.md`; one flat `graphs/<graph_id>/` registry |
| What does the explicit legacy converter accept? | [Superseded v0.3 format](../skill-spec/00-FORMAT-GROUND-TRUTH.md) and [portable migration contract](../skill-spec/01-PORTABLE-GSKILL-V1.md) | Converter input and historical evidence only; production compile/run does not read or fall back to v0.3 |
| Where is the current error-code catalog? | [Error-code specification](../skill-spec/11-error-code-spec.md) | `living` unique catalog kept in bijection with `ERROR_REGISTRY`; other documents link rather than copy the table |
| Where are current extracted-engine responsibilities indexed? | [MVP1 documentation index](../mvp1/INDEX.md) | Current design line for the engine behind `CurrentEngineAdapter` |
| Which features own sources, events, errors, and tests? | [`spec/features.yaml`](../../spec/features.yaml) and the [generated compliance view](../feature-compliance-checklist.md) | The manifest is the mutable SSOT; the root checklist is its FROZEN generated view |
| What source facts motivated the standalone design? | [`baseline.md`](./baseline.md) | Historical pre-extraction evidence at `origin/main@3564b49e`; not a current directory map |
| What should the complete standalone v1 become? | [`v1-alignment.md`](./v1-alignment.md) | Overall status remains `drafted`; its implementation-status section distinguishes completed Phase 0/1/2 work from Phase 3+ targets |
| What platform rules apply? | [Cross-platform policy](../CROSS_PLATFORM.md) | Current Windows, macOS, and Linux engineering policy |

## Current Phase 1 and Phase 2 line

The standalone naming cutover is complete in source and package metadata. Public callers use the typed `graph_skill_runtime` facade, not the extracted engine's former top-level ABI. The `gskill` CLI and MCP server are transport adapters over the same `RuntimeApplication`, and `create_application` composes replaceable engine and snapshot ports without a singleton.

The current reader accepts only the portable contract in [`01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md). A business gSkill is always supplied by path and remains user-owned; installing or importing the runtime does not register, discover globally, copy, or mutate it. The root `SKILL.md` is the sole Agent Skills discovery target, while `graph.yaml` owns machine topology and root-only artifact declarations. Reusable graphs live in one flat `graphs/<graph_id>/` registry.

Legacy v0.3 parsing is isolated behind `gskill migrate studio-skill SOURCE DESTINATION [--runtime-config PATH] [--preset-id ID]`. The converter does not modify source or overwrite an existing destination. Production compile, predict, run, inspect, SDK, CLI, and MCP paths neither sniff formats nor fall back after a portable-format failure.

The default executor declaration is `host-native`, but no host-native handoff adapter exists in Phase 1. A default run persists its request and returns `GSKILL_EXECUTOR_UNAVAILABLE`. Explicit `embedded` execution reaches the extracted engine; a real current-format `LOGIC` skill compile/run path is covered. Durable `resume` and `submit_agent_result` remain Phase 3 work and currently return `GSKILL_NOT_IMPLEMENTED`.

## Drafted Phase 3 and later line

Host-native durable handoff is Phase 3. Vendor CLI executors are Phase 4. MoirAI canonical assets and installer are Phase 5. Gateway and Studio adapters plus final cutover are Phase 6. These targets remain authoritative design direction in `v1-alignment.md`, but they are not current capabilities.

## Publication and cutover rules

The GitHub repository exists and uses pull-request-only protection. The distribution name is present in local package metadata, but the project has not been published to PyPI. [The release workflow](../../.github/workflows/release.yml) separates build and publish jobs, checks a GitHub Release tag against the package version, validates wheel contents, and is wired for PyPI Trusted Publishing through OIDC. The owner still has to configure the PyPI project and trusted publisher; workflow presence is not registry or release evidence.

Each future contract cutover replaces its predecessor only after implementation, regeneration or conversion, cross-platform verification, contract-map updates, examples, and documentation are complete together. The Phase 2 source cutover follows this atomic shape: one production reader plus one explicit converter boundary, with the old format retained only as `superseded` evidence. Do not add a dual reader, legacy alias, deprecated field, or version-guessing fallback. Historical evidence stays historical; current facts move to the current owner.

## Status vocabulary

- **Current fact**: directly observable in this checkout's code, package metadata, tests, current contract documents, or recorded repository settings.
- **Drafted target**: an accepted direction whose remaining implementation and causal evidence are incomplete.
- **Recommendation**: an implementation option that still requires a design decision or acceptance evidence.
- **Open question**: a decision lacking evidence or an owner ruling and therefore not usable as a default.
