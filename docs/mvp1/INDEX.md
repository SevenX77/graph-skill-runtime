---
doc: INDEX
role: index
status: living
updated: 2026-08-28
---

# Graph Skill Runtime MVP1 文档索引

本文是提取后 engine 的 MVP1 导航和 cutover 状态索引。当前运行事实由 standalone runtime 的 portable contract 与当前源码拥有；被 Phase 2 反转的 v0.3 模块文档保留为 pre-cutover 证据，不再作为当前契约。历史迁移目录 `docs/engine/mvp1/_migration-src/` 已在 2026-06-28 删除，需要更早记录时查看 git 历史。

## 1. Phase 2 后的当前所有权

| 事实 | 当前 owner | 边界 |
| --- | --- | --- |
| Portable 目录、`SKILL.md`、`graph.yaml`、phase schema、flat registry、artifact declaration/request、bundle compile 与 converter | [`skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md) | `FROZEN` 当前 contract（2026-09-01 由 `audited-ready` 转入：owner 盖章 + SHA-256 seal 记录落入 [`tests/contract-seals.yaml`](../../tests/contract-seals.yaml)）；此后修订只有一条路——改正文并在同一 PR 内追加一条带 `pm_approval` 的 seal 记录，没有记录的改动被哈希锁拦下。不复制第二套模板 |
| Error code、level、stage、正向定义、原因、修复与 owning spec | [`skill-spec/11-error-code-spec.md`](../skill-spec/11-error-code-spec.md) | `living` 唯一 catalog，与 `ERROR_REGISTRY` 双射 |
| Parser、loader、bundle inventory、compile 聚合与 flat graph call resolution | [`parser.py`](../../src/graph_skill_runtime/core/parser.py)、[`loader.py`](../../src/graph_skill_runtime/core/loader.py)、[`compiler.py`](../../src/graph_skill_runtime/core/compiler.py) | 当前可执行行为；格式与错误语义仍分别回到 `01` 与 `11` |
| Graph/phase typed manifest 与本地 resolver | [`manifest.py`](../../src/graph_skill_runtime/core/manifest.py)、[`local_workspace_resolver.py`](../../src/graph_skill_runtime/core/local_workspace_resolver.py) | 当前可执行结构与解析；内部 graph id 由 portable flat registry 拥有 |
| Typed SDK/CLI/MCP facade | [Public API contract](../public-api-contract.md) 与 [`graph_skill_runtime.__all__`](../../src/graph_skill_runtime/__init__.py) | 当前精确为 77 个 top-level symbols 与 14 个 top-level Python functions：9 个 runtime/application entry points 加 5 个 integration functions；MCP 仍只有 8 个 runtime tools。Phase 4 增加 `AgentResource`，Phase 5 增加 18 个 integration exports |
| Optional MoirAI host integration | [`integration.json`](../../src/graph_skill_runtime/integrations/assets/moirai/integration.json) 与 [完整 v1 设计](../design/v1-alignment.md) | Phase 5 当前 owner：canonical inventory、六 renderer、显式 installer 与 scoped discovery；不在本索引复制 inventory 或验收证据 |
| Cross-platform release-candidate acceptance | [Cross-platform policy](../CROSS_PLATFORM.md) 与 [`accept_release_artifacts.py`](../../scripts/accept_release_artifacts.py) | Phase 6 当前 owner：同一 manifest-bound wheel/sdist 的三平台安装验收；它是 pre-publication evidence，不是 registry publication |

Production compile、predict、run、inspect、SDK、CLI 与 MCP 只读取 portable contract。Legacy v0.3 parser 只在显式 `gskill migrate studio-skill` converter 中可达；[`skill-spec/00-FORMAT-GROUND-TRUTH.md`](../skill-spec/00-FORMAT-GROUND-TRUTH.md) 是 `superseded` converter 输入与历史证据。

## 2. Phase 2 已取代的模块文档

下列文档的正文保留 v0.3 pre-cutover 描述，状态统一为 `superseded`。其中的现在时、路径、owner 和“唯一真相源”陈述都不是当前 runtime 事实：

| 模块 | Superseded 文档 |
| --- | --- |
| Physical layout | [`baseline`](./01-contract/01-physical-layout/baseline.md)、[`alignment`](./01-contract/01-physical-layout/mvp1-alignment.md) |
| Skill syntax | [`baseline`](./01-contract/02-skill-syntax/baseline.md)、[`alignment`](./01-contract/02-skill-syntax/mvp1-alignment.md) |
| Compile rules | [`baseline`](./01-contract/03-compile-rules/baseline.md)、[`alignment`](./01-contract/03-compile-rules/mvp1-alignment.md) |
| Invalidation baseline | [`baseline`](./01-contract/05-invalidation/baseline.md) |
| Compile mechanism | [`baseline`](./02-mechanism/01-compile/baseline.md)、[`alignment`](./02-mechanism/01-compile/mvp1-alignment.md) |
| Resolver mechanism | [`baseline`](./02-mechanism/02-resolver/baseline.md)、[`alignment`](./02-mechanism/02-resolver/mvp1-alignment.md) |

## 3. 历史三层结构与未反转模块导航

| Layer | Scope | Directory |
| --- | --- | --- |
| A. Contract | skill 文件格式、编译规则、数据契约、失效规则 | `01-contract/` |
| B. Mechanism | compile / resolve / assemble / run outer / run inner / seam / runtime | `02-mechanism/` |
| C. API Contract | engine 与 Studio 的操作边界 | `03-api-contract/` |

## 4. Contract Modules

| Module | Purpose | Phase 2 status |
| --- | --- | --- |
| `01-contract/01-physical-layout` | 文件树、`.workspace`、运行产物位置 | superseded；当前格式见 portable `01` |
| `01-contract/02-skill-syntax` | skill 语法在 MVP1 中的职责边界 | superseded；当前格式见 portable `01` |
| `01-contract/03-compile-rules` | 编译/装配/运行生命周期规则与错误诊断 | superseded；当前 compile 规则见 portable `01`，错误目录见 `11` |
| `01-contract/04-data-contracts` | WorkflowState / result / error payload 等数据形状 | 未在本次 format cutover 中退役；消费前仍须核对当前 public models |
| `01-contract/05-invalidation` | source change 到 golden/checkpoint/cache 的失效模型 | baseline superseded；其余内容须在消费前核对当前源码 |

## 5. Mechanism Modules

| Module | Purpose |
| --- | --- |
| `02-mechanism/01-compile` | loader/parser/validator/cache/purity scanner；旧文 superseded，当前实现见本页 §1 |
| `02-mechanism/02-resolver` | 旧 path resolver 文档 superseded；当前 flat registry 解析见 portable `01` 与本页 §1 |
| `02-mechanism/03-assemble` | AST 到 runnable graph / prompt assembly |
| `02-mechanism/04-run-outer/01-graph-exec` | graph-level execution, StateMapper, LOGIC/SUBGRAPH dispatch |
| `02-mechanism/04-run-outer/02-iterate` | batch/loop/graph-level iterate runtime |
| `02-mechanism/04-run-outer/03-checkpoint` | shared checkpoint base and outer blackboard persistence |
| `02-mechanism/05-run-inner/01-agent-loop` | Agent loop |
| `02-mechanism/05-run-inner/02-middleware` | middleware slots and order |
| `02-mechanism/05-run-inner/03-cognitive` | cognitive flow and finish_task |
| `02-mechanism/05-run-inner/04-tools` | tools and tool error behavior |
| `02-mechanism/05-run-inner/05-exit-control` | explicit exit gate |
| `02-mechanism/05-run-inner/06-golden-eval` | golden evaluation |
| `02-mechanism/05-run-inner/07-subagent` | runtime subagent dispatch |
| `02-mechanism/05-run-inner/08-messages-state` | inner messages state and resume |
| `02-mechanism/06-seam/01-models` | model gateway seam and predict mocks |
| `02-mechanism/06-seam/02-observability` | typed events, traces, metrics |
| `02-mechanism/07-runtime` | public SDK runtime entrypoints |

## 6. API Contract

| Module | Purpose |
| --- | --- |
| `03-api-contract` | compile/run/predict/resume/golden API signatures, event protocol, Studio HTTP contract |

## 7. Current SSOT Notes

- Current skill format and bundle compile: [`skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md).
- Current error catalog: [`skill-spec/11-error-code-spec.md`](../skill-spec/11-error-code-spec.md).
- Superseded v0.3 converter input: [`skill-spec/00-FORMAT-GROUND-TRUTH.md`](../skill-spec/00-FORMAT-GROUND-TRUTH.md).
- MVP1 historical syntax and mechanism documents must not duplicate or override portable `01`.
- `_migration-src` is no longer part of the live doc set.
- Complete v1 design: [`design/v1-alignment.md`](../design/v1-alignment.md). Bounded Phase 3、Phase 4、Phase 5 与 pre-publication Phase 6 已按各自范围验收；Phase 3b、首次发布前命名裁决与真实 release/registry publication 仍未闭合，因此完整设计保持 `drafted`。
