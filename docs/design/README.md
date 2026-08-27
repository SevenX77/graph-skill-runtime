---
doc: graph-skill-runtime-index
role: index
status: living
updated: 2026-08-27
---

# Standalone Design Documentation

This directory owns the design for turning the extracted engine into a standalone runtime. It separates the contract implemented in Phase 0 from the drafted target so that future names and formats are not mistaken for current capabilities.

## Authority map

| Question | Authoritative source | Status and use |
| --- | --- | --- |
| What package and API can be used in this checkout? | [Repository README](../../README.md) and [`pyproject.toml`](../../pyproject.toml) | Current Phase 0 package: `graph-agent` 0.3.1, imported as `graph_agent` |
| What skill files does the current implementation accept? | [FROZEN format ground truth](../skill-spec/00-FORMAT-GROUND-TRUTH.md) | Current format source of truth; root `GRAPH.md` and type-specific phase files |
| Where are the current engine responsibilities and contracts indexed? | [MVP1 documentation index](../mvp1/INDEX.md) | Current design line for the implemented engine |
| What source facts motivated the standalone design? | [`baseline.md`](./baseline.md) | `drafted` evidence snapshot of the pre-extraction monorepo at `origin/main@3564b49e`; not a description of every post-extraction repository path |
| What should the standalone runtime, SDK, CLI, portable format, executors, and integrations become? | [`v1-alignment.md`](./v1-alignment.md) | `drafted` target design; authoritative for intended future work, not current behavior |
| What platform rules apply to this repository? | [Cross-platform policy](../CROSS_PLATFORM.md) | Current Windows, macOS, and Linux engineering policy |

## Current implementation line

Phase 0 still runs as the `graph-agent` distribution and `graph_agent` import. The current skill root is `GRAPH.md`; phase files are `LOGIC.md`, `SUBGRAPH.md`, or `SKILL.md`; nested graphs use the current `subgraph/` layout. The FROZEN skill specification and current MVP1 documentation remain authoritative until cutover.

The baseline document records the monorepo source state from which this repository was extracted. References in that evidence snapshot can point to source-repository locations that were outside the extracted package. They remain historical evidence and must not be interpreted as runtime dependencies or as the current standalone directory map.

## Drafted target line

The target design uses the working distribution name `graph-skill-runtime`, Python import `graph_skill_runtime`, console command `gskill`, Agent Skills entry `SKILL.md`, machine graph definition `graph.yaml`, and agent phase file `AGENT.md`. These names and contracts are drafted. They are not implemented, published, reserved, or available merely because the repository carries the target name.

The target also keeps business gSkills user-owned. A runtime wheel may ship runtime implementation resources and optional integration assets, but it does not bundle, register, copy, or mutate user business skills.

## Cutover rule

The target line can replace the current line only after implementation, migration or regeneration, cross-platform verification, contract-map updates, examples, and documentation are complete together. The cutover must retarget every active reference and delete the displaced reader in the same change. Before that point, do not add a dual reader, legacy alias, or version-guessing fallback.

## Status vocabulary

- **Current fact**: directly observable in this checkout's code, package metadata, tests, or current contract documents.
- **Drafted target**: an accepted direction for future implementation that is not yet a current capability.
- **Recommendation**: an implementation option that still requires acceptance evidence.
- **Open question**: a decision that lacks evidence or an owner ruling and cannot be treated as a default.
