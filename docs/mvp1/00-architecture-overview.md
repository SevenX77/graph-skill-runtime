---
doc: 00-architecture-overview
role: summary
status: living
authority: ./INDEX.md
updated: 2026-08-27
---

# Graph Skill Runtime MVP1 架构总览

本文是一页导航摘要，权威模块地图与 Phase 2 状态表是 [`INDEX.md`](./INDEX.md)。独立 runtime 已完成 Phase 1 typed facade 与 Phase 2 portable format；被取代的 Graph Agent 模块文档只作历史证据。完整 v1 设计仍为 `drafted`，因为 Phase 3+ executor、installer 和产品 integration 尚未实现。

Engine MVP1 文档按三层组织：

1. Contract layer: 声明式文件、编译规则、数据契约。
2. Mechanism layer: compile / resolve / assemble / runtime 的实现机制。
3. API contract layer: engine 与 Studio 的操作边界。

完整模块列表见 [`INDEX.md`](./INDEX.md)。

完整 standalone v1 设计见 [`design/v1-alignment.md`](../design/v1-alignment.md)。当前 58-symbol facade 见 [`public-api-contract.md`](../public-api-contract.md)。

## Format SSOT

当前 portable gSkill 文件格式与 bundle compile 的唯一契约是：

[`skill-spec/01-PORTABLE-GSKILL-V1.md`](../skill-spec/01-PORTABLE-GSKILL-V1.md)

[`skill-spec/00-FORMAT-GROUND-TRUTH.md`](../skill-spec/00-FORMAT-GROUND-TRUTH.md) 已是 `superseded` 的 v0.3 converter 输入与历史证据。MVP1 alignment 文档不重复 portable 模板；被 Phase 2 反转的模块状态见 [`INDEX.md` §2](./INDEX.md#2-phase-2-已取代的模块文档)。

## Migration Source

历史迁移目录 `docs/engine/mvp1/_migration-src/` 已删除。当前 owner 从 [`INDEX.md`](./INDEX.md) 进入；历史迁移细节通过 git 历史和标为 `superseded` 的正文追溯。
