---
doc: studio-minimal-editor-basis
role: design-basis
status: superseded
updated: 2026-10-08
---

# Minimal Studio editor: basis and evidence

Historical basis, superseded by the [Graph Skill agent plugin basis](./graph-skill-agent-plugin-basis.md). The original reasoning and observations below remain preserved under their original scope.

This file supports the [design proposal](./studio-minimal-editor.md). It preserves requirement interpretation, engineering choices and evidence limits. The proposal owns the planned behavior; existing runtime specifications own current product facts.

## Effective sources and baseline

The selected goal is `shared-graph-ui-feasibility`: make the user's graph UI objective concrete through a minimal, reviewable same-repository design. This design responsibility shares that goal and its root coordinator's acceptance boundary. The authorized bootstrap is `build/studio-design-2026-10-08/writer-brief.md`; the coordinator transcribed the following user statements there. The writer read that brief and the applicable source files on 2026-10-08. Direct access to the originating chat is outside the writer's evidence.

| Source, in conversation order | Effective requirement and interpretation |
| --- | --- |
| “调研一下codex和claude有没有统一的插件界面？MCP？我需要模拟一个类似graph-skill-studio的界面显式graph节点图，各种配置” — investigate a shared Codex/Claude plugin interface and show graph nodes/configuration | Establishes the graph UI objective. Host rendering is background motivation; the later scope specifies the immediate deliverable. |
| “D:\\coding\\agent-harness，这里面已经有完整的studio内容，从这里面扒，我现在要做的是简化” — extract and simplify the existing Studio | Reuse inspected source from that repository, with deliberate removal of unrelated product behavior. |
| “当前只需要保留graph节点 和 节点属性配置页面，从最简化的开始” — begin with graph nodes and node properties | The two surfaces define the minimal product slice. Exact form coverage and topology mutation scope are proposed engineering choices. |
| “不要，就做在这个仓库里，单独建一个模块就可以了” — use one separate module in this repository | Replaces the coordinator's earlier sibling-repository suggestion. The existing runtime module boundary still applies. |
| “写设计方案，按照当前的模块化规范，需要新增哪些模块，需要改哪些模块” — write the design and identify added/changed modules | Authorizes design documents, source inspection and verification. Implementation and external publication remain separate work. |

[Project rules](../../AGENTS.md), especially sections 2, 4, 6–10 and the language/authoring policies, govern runtime separation, current-format use, packaging, verification and independent authorship. The installed `task-contract/SKILL.md` and `references/profile.md` were explicitly read at `C:/Users/test/AppData/Local/Microsoft/WinGet/Packages/OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe/node-v24.18.0-win-x64/node_modules/prime-agent/dist/skills/task-contract/`. Their clauses C01/C04 permit this compact authorized bootstrap; C03/C11/C16 govern review, changes and acceptance. No published current goal file was supplied or found by the coordinator. This Markdown brief is assessed by source/reference/content review; the JSON goal checker supplies no validation claim for it.

The writer owns the two design files and one drafted navigation row. The coordinator owns acceptance. English follows the repository language rule; the coordinator explicitly withdrew its inferred Chinese-writing instruction after the writer identified that conflict. Existing unrelated working-tree changes are outside this responsibility.

## Goal review

Confidence values express current judgment on [0,1]; they are neither calibrated probabilities nor authorization thresholds. The design outcome is assessed separately from an operational editor.

| Dimension | Judgment, evidence and change trigger |
| --- | --- |
| Source support: 0.98 | The quoted latest instructions directly support same-repository design and the two surfaces. The writer relies on the coordinator's transcription; a conflicting original message would require revision. |
| Interpretation: 0.94 | Module changes, extraction and minimal UI are covered. Root-only editing and existing-phase-only mutation are proposals, because the user did not explicitly decide those details. A need to create nodes immediately would widen the initial slice. |
| Effectiveness: 0.93 | A concrete module/ownership/data/save/acceptance design answers the current architecture question. It does not itself deliver a usable editor or host plugin; acceptance must remain scoped to design. |
| Decomposition: 0.92 | Module plan, source extraction, document lifecycle and integration acceptance jointly cover the requested design. An extraction trial and source-preservation tests are still needed to establish implementation feasibility. |

Three challenges shaped the baseline. A design could satisfy a directory checklist while leaving editing behavior unspecified; sections 3–7 therefore define actual fields, writes, failure behavior and observed acceptance. Reusing the full Studio could preserve the requested visuals while defeating simplification; extraction is bounded by the two surfaces. Restricting topology edits could accidentally become a permanent product rule; the proposal explicitly identifies that restriction as sequencing and records the condition for revisiting it.

## Engineering choices and alternatives

| Choice | Feasibility judgment and rationale | Missing evidence, counterexample and reversal condition |
| --- | --- | --- |
| One `studio/` Node/TypeScript package with local service and public compile CLI — selected proposal | 0.85. It keeps browser/filesystem concerns together and avoids adding HTTP dependencies to the Python runtime. The CLI already provides typed compile results; source documents provide editable content. | Source-preserving YAML edits and real process lifecycle are untested. If a clean extraction or safe text edit requires substantial new machinery, narrow the form slice; if CLI process integration becomes disproportionate, reconsider a product-owned Python service. |
| Product-owned Python service consuming the public SDK | 0.82. It can reuse typed runtime results directly and still preserve the runtime boundary when isolated under Studio. | Adds a second product language/dependency environment beside the frontend. Reconsider if SDK-only capability becomes necessary or measured CLI integration cost exceeds that extra ownership. |
| Expand public `inspect` for authoring | 0.72. A typed public projection could serve several consumers. Current `InspectResult` contains graph identities/call edges, so expansion requires contract, implementation and test work. | A compiled-only view cannot preserve invalid source drafts or formatting. Adopt only for an independently justified shared inspection requirement, with explicit ownership of source editing. |
| Transplant the existing Studio application | 0.30 for this minimal objective. Existing visuals and interactions are present. | Inspected imports couple the application to workspace, Gateway, execution, Tauri and legacy representations. It becomes appropriate only if the intended product scope includes those systems. |
| Save source, then explicit validation — selected proposal | 0.89. Incremental repair needs incomplete files to remain editable. It allows a single-file save contract and existing compiler use. | Users may later require every save to compile successfully. That requirement would change the save contract and require coherent staged bundle validation. |
| Compile a temporary bundle before each save | 0.67. It can reject an invalid candidate before replacing the edited file. | Complete resource/import copying, external mutations and side effects complicate equivalence to the actual skill. It obstructs incremental repair and requires more lifecycle ownership. Reconsider only for a stated validated-save requirement. |

The remaining uncertainty permits a design proposal because acceptance explicitly requires the missing implementation evidence. It does not authorize claims that source roundtripping, safe writes, host rendering or an operational Studio already work. No fixed score threshold determines the choice.

## Verified source coordinates

Observations describe the working tree read on 2026-10-08. Runtime HEAD was `205b34d34b9354deae5fe1f095f2ba62180a9c52`, with unrelated modifications already present. HEAD alone does not identify the inspected bytes.

| Source | Decisive observation and its design effect |
| --- | --- |
| [v1 alignment §3.1](./v1-alignment.md), [project rules §2](../../AGENTS.md) | Runtime core/application own no Studio UI, HTTP or product state. Same-repository placement therefore uses a separate product module. Historical Phase 1–6 acceptance remains unchanged. |
| [Portable specification §§2, 4, 5](../skill-spec/01-PORTABLE-GSKILL-V1.md) | Root `SKILL.md`/`graph.yaml`, typed phase files, `{id, depends_on, output}` topology, phase `name`, and flat `subgraphs/` registry define the authoring projection. Agent body and `system_prompt` ownership prevent copying an internal runtime model into frontmatter. |
| [`domain/models.py`](../../src/graph_skill_runtime/domain/models.py), `InspectResult` and `CompileResult`; [`adapters/engine.py`](../../src/graph_skill_runtime/adapters/engine.py), `inspect` | Inspection returns graph-level identities/calls after compilation. It provides neither editable phase documents nor phase dependencies. |
| [`core/topology_projection.py`](../../src/graph_skill_runtime/core/topology_projection.py), `load_graph_topology_projection` | Internal partial projection can return empty data or skip malformed rows. Studio needs visible authoring errors and retained source, so this helper is evidence rather than its public authoring API. |
| [`adapters/cli.py`](../../src/graph_skill_runtime/adapters/cli.py), `build_parser`, `_dispatch`, `main` | `compile --no-cache` emits structured JSON without a `--json` flag. Exit 2 can carry either compile failure or a runtime error payload; Adapter discrimination is required. |
| [`core/loader.py`](../../src/graph_skill_runtime/core/loader.py), `_load_python_module` | Compilation reaches `spec.loader.exec_module(module)` for business modules. Explicit Validate is an operation on trusted local code; opening the editor remains document reading. |
| [`pyproject.toml`](../../pyproject.toml), wheel target/import checker; [distribution tests](../../tests/test_distribution_contract.py) | Wheel selection is `src/graph_skill_runtime`; Python boundary enforcement has no coverage of a new Node package. Packaging and Studio boundary evidence require explicit checks. |
| `D:/coding/agent-harness/apps/studio/frontend/` at `4693764e3489efdf21694dabd7b492c270d4121a` | Canvas and properties imports establish the coupling described in the extraction matrix. `phase-frontmatter.ts` uses old Agent `SKILL.md` and subgraph `path`; `canvas-authoring.ts` uses `src`/`mode`. `layout.ts` has explicit cycle detection. Source status showed only untracked `pip/`; its root license identifies Apache-2.0. |

Selected SHA-256 identities preserve which mutable source bytes supported this review: portable specification `8742ce1bb6b4d694a529eeaf0537bbd925068dd9b54ca925acf58581a9306d1d`; CLI `c2f5ad7f968bb3ff9f378de2bfef0f385ea18e7852fa66971febdaacad22bf62`; loader `55c59986afc09d0eb9566d673923c3fdb8c6de0bc5aeb89965685dd223b11951`. Future edits require review of the affected premise rather than reliance on these old identities.

## Verification scope and handoff

The writer performed source/document inspection and independent requirement/choice review. No Studio code, browser interaction, source-edit roundtrip or local service execution exists from this design task. The coordinator reviews actual files and reference coverage before accepting the design.

The coordinator reports that Ruff, strict mypy over 149 files, nine import contracts, the manifest validator and `git diff --check` passed. The full runtime suite passed with `1814 passed, 1 skipped in 101.45s` after setting this process's `TEMP`/`TMP` to the short workspace path `build/st-42e0ba`; raw output is retained in `build/studio-design-2026-10-08/pytest-short-temp.log`. Earlier invocations encountered system temporary-directory access and long-path conditions. Those observations and the successful controlled rerun establish an invocation limitation, rather than a demonstrated source defect. They supply regression evidence for the inspected working tree, not Studio acceptance.

The dependency audit remains non-green: the tool reported 26 known-vulnerability entries across four packages, with a repeated virtualenv entry. This is not a claim of 26 distinct vulnerabilities. The unpublished local package was skipped. Dependency changes are outside this design task. A build after document creation and any final artifact identity remain the coordinator's verification responsibility; an existing runtime test result cannot establish a new packaged candidate or the proposed UI.

The design is ready for coordinator review when its module plan, extraction mapping, read/write/validate contract and acceptance jointly answer the latest request. Implementation must obtain its own observed evidence and register actual sources/tests. A need for immediate node creation, stronger external-editor concurrency guarantees or host UI embedding returns to scope/choice review before dependent implementation.
