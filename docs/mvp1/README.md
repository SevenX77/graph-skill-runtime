---
milestone: MVP1
status: living
updated: 2026-08-27
---

# Graph Skill Runtime MVP1 文档入口

模块状态与当前 owner 的权威入口是 [`INDEX.md`](INDEX.md)。[`00-architecture-overview.md`](00-architecture-overview.md) 是一页导航摘要，不独立持有格式或实现契约。

## Phase 2 后的当前权威

- Portable 文件布局、语法、flat graph registry、bundle compile、artifact-by-id 和一次性 converter：[`../skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md)。
- 唯一 error catalog：[`../skill-spec/11-error-code-spec.md`](../skill-spec/11-error-code-spec.md)。
- 当前 parser/loader/compiler/resolver：[`../../src/graph_skill_runtime/core/`](../../src/graph_skill_runtime/core/)。
- Typed facade：[`../public-api-contract.md`](../public-api-contract.md)。

Production runtime 只读取 portable 格式。[`../skill-spec/00-FORMAT-GROUND-TRUTH.md`](../skill-spec/00-FORMAT-GROUND-TRUTH.md) 已是 `superseded` 的 v0.3 converter 输入和历史证据。

## 结构

- `01-contract/`: 声明式契约层。
- `02-mechanism/`: 引擎实现机制层。
- `03-api-contract/`: engine 与 Studio 的操作 API 契约。

## Superseded 模块文档

Phase 2 已取代 physical-layout、skill-syntax、compile-rules、invalidation baseline、compile mechanism 和 resolver mechanism 的指定 baseline/alignment 文档。它们保留为 v0.3 pre-cutover evidence；完整清单和准确链接见 [`INDEX.md` §2](INDEX.md#2-phase-2-已取代的模块文档)。正文中的现在时不再描述当前 runtime。

## 迁移源状态

`docs/engine/mvp1/_migration-src/` 已在 2026-06-28 删除。当前事实从 [`INDEX.md`](INDEX.md) 的 owner map 进入；需要旧迁移细节时查看标为 `superseded` 的正文和 git 历史。
